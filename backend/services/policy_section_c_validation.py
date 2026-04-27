"""
Validation for Section C jurisdiction overrides.

Two layers:
  1. Country code: ISO-3166 alpha-2, validated against an inline static set
     so we don't hit a service. Front-end will pre-validate, but the API
     enforces too — security boundary, not just UX hint.
  2. Tier ordering inside cap_rule_json: the same monotonic-non-decreasing
     rule that base benefit rows must satisfy. Mirrors the Python side of
     frontend/src/features/policy-config/benefitRowValidation.ts so HR
     can't sneak a SG override with caps that decrease across tiers
     where the base row enforces ordering.

Public surface:
  validate_jurisdiction_override(payload) -> None  (raises ValueError)
  detect_override_collisions(overrides) -> Optional[Dict]
        Returns the colliding tuple as a structured error, or None if all
        (employee_level, assignment_type) tuples are unique. The DB also
        enforces this via UNIQUE; doing it in Python first lets us return
        a 422 with a useful message instead of a 500 IntegrityError.

Country list intentionally lives in this module rather than a JSON file —
the list is short, rarely changes, and keeping it inline means tests
have no IO. If it grows past ~250 entries (it won't), refactor.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


# ISO-3166 alpha-2 country codes. Source: en.wikipedia.org/wiki/ISO_3166-1
# Maintained inline. Includes commonly-relocated-to-and-from territories.
_ISO_ALPHA2: Set[str] = frozenset({
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT",
    "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI",
    "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS", "BT", "BV", "BW", "BY",
    "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN",
    "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK",
    "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL",
    "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GW", "GY", "HK", "HM",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR",
    "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
    "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS",
    "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK",
    "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS", "MT", "MU", "MV", "MW",
    "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP",
    "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
    "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW",
    "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM",
    "SN", "SO", "SR", "SS", "ST", "SV", "SX", "SY", "SZ", "TC", "TD", "TF",
    "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW",
    "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW",
})


def is_valid_country_code(code: Any) -> bool:
    """True iff `code` is a non-empty string that matches an ISO alpha-2."""
    if not isinstance(code, str):
        return False
    s = code.strip().upper()
    return bool(s) and s in _ISO_ALPHA2


def normalize_country_codes(raw: List[Any]) -> List[str]:
    """
    Normalize a list of country codes: strip, upper-case, deduplicate while
    preserving order. Does NOT filter unknown codes — the validator below
    is the gatekeeper, so we want unknowns to surface in the error message
    rather than being silently dropped (which would confuse HR who'd see a
    different downstream error like "empty list").
    """
    seen: Set[str] = set()
    out: List[str] = []
    for c in raw or []:
        if not isinstance(c, str):
            continue
        s = c.strip().upper()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


# --- cap_rule_json tier ordering --------------------------------------------

def _extract_tier_amounts(cap_rule_json: Dict[str, Any]) -> Optional[List[float]]:
    """
    cap_rule_json shapes seen in this codebase:
      {"tiers": [{"max": 1000}, {"max": 5000}]}     # multi-tier
      {"max": 5000}                                  # flat single cap
      {}                                             # no cap defined
    For ordering validation we only care about the multi-tier case; flat
    or empty caps are vacuously valid (return None to signal skip).
    """
    if not isinstance(cap_rule_json, dict):
        return None
    tiers = cap_rule_json.get("tiers")
    if not isinstance(tiers, list) or len(tiers) < 2:
        return None
    out: List[float] = []
    for t in tiers:
        if not isinstance(t, dict):
            return None
        v = t.get("max")
        if v is None:
            return None
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            return None
    return out


def is_tier_ordering_valid(cap_rule_json: Dict[str, Any]) -> bool:
    """
    Tier caps must be monotonically non-decreasing. Same rule the frontend
    enforces in benefitRowValidation.ts. Empty / single-tier / non-tiered
    caps pass.
    """
    amounts = _extract_tier_amounts(cap_rule_json)
    if amounts is None:
        return True
    return all(amounts[i] <= amounts[i + 1] for i in range(len(amounts) - 1))


# --- Public validation surface ----------------------------------------------

def validate_jurisdiction_override(payload: Dict[str, Any]) -> None:
    """
    Validate one override payload (already shape-validated by Pydantic).

    Raises ValueError with a json-encoded structured error matching the
    format used by policy_config_matrix_service.validate_put_body so the
    HTTP layer renders consistent 422 bodies.
    """
    countries = payload.get("jurisdiction_countries") or []
    if not isinstance(countries, list) or len(countries) == 0:
        _raise_validation(
            "jurisdiction_countries",
            "Pick at least one country for this override.",
        )
    bad: List[str] = []
    for c in countries:
        if not is_valid_country_code(c):
            bad.append(str(c) if c is not None else "")
    if bad:
        _raise_validation(
            "jurisdiction_countries",
            f"Unknown country code(s): {', '.join(bad)}. Use ISO-3166 alpha-2 (e.g. SG, US).",
        )

    cap = payload.get("cap_rule_json")
    if cap and not is_tier_ordering_valid(cap):
        _raise_validation(
            "cap_rule_json",
            "Tier caps must be non-decreasing across tiers.",
        )


def detect_override_collisions(
    overrides: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Return a structured collision descriptor if two overrides share the
    same (employee_level, assignment_type) tuple, else None. The DB has
    a UNIQUE constraint on this; we check first so the API returns 422
    with a useful payload instead of a 500.
    """
    seen: Dict[tuple, int] = {}
    for i, ov in enumerate(overrides):
        key = (
            (ov.get("employee_level") or None),
            (ov.get("assignment_type") or None),
        )
        if key in seen:
            return {
                "field": "jurisdiction_overrides",
                "message": (
                    f"Duplicate override for (level={key[0] or 'any'}, "
                    f"assignment_type={key[1] or 'any'}). Each combination "
                    "must be unique per benefit; merge their countries into "
                    "one row instead."
                ),
                "duplicate_indices": [seen[key], i],
            }
        seen[key] = i
    return None


# --- Internal ---------------------------------------------------------------

def _raise_validation(field: str, message: str) -> None:
    """
    Raise the structured ValueError shape that
    policy_config_matrix_service._policy_matrix_validation_http unpacks
    into a 422 detail body.
    """
    import json as _json
    raise ValueError(
        _json.dumps(
            {
                "code": "validation_error",
                "errors": [{"field": field, "message": message}],
            }
        )
    )
