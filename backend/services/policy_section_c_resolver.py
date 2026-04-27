"""
Section C of HR Policy — override resolution for benefit rows.

Each base row in policy_config_benefits can have zero or more override rows
in policy_benefit_jurisdiction_overrides that customize the benefit for a
specific (jurisdiction × employee_level × assignment_type) slice.

Resolution semantics:

    employee_ctx = {country, employee_level, assignment_type}

    1. From all overrides attached to a base row, keep only those whose
       jurisdiction_countries list contains employee_ctx.country.
    2. Score each candidate by specificity:
         - employee_level matches employee_ctx.employee_level ........ +2
         - employee_level is NULL (wildcard) ......................... +0
         - employee_level is set but doesn't match ................... drop
         - assignment_type matches employee_ctx.assignment_type ...... +1
         - assignment_type is NULL (wildcard) ........................ +0
         - assignment_type is set but doesn't match .................. drop
    3. Highest score wins. Tie -> highest display_order. Tie ->
       most-recent updated_at.
    4. If a winner exists, fold its non-NULL fields onto the base row;
       NULL fields inherit from the base. This lets HR override only the
       markdown clauses for a region without redefining the cap.
    5. If no override matches, return the base row untouched.

Public surface:
    resolve_effective_benefit(base_row, overrides, employee_ctx) ->
        (effective_row, applied_override_id_or_none)

This module is intentionally pure — no DB, no Pydantic, no logging side
effects. The caller fetches the override list and feeds it in. Tests at
backend/tests/test_policy_section_c_resolver.py exercise the full matrix.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple


# --- Country list normalization ----------------------------------------------

def _coerce_countries(raw: Any) -> List[str]:
    """
    jurisdiction_countries is text[] in Postgres, JSON-encoded TEXT in
    SQLite, and might arrive from the DB driver as either a Python list or
    a string. Normalize to a list of upper-case ISO-3166 alpha-2 codes.
    Unknown shapes return [].
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(c).strip().upper() for c in raw if str(c).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        # JSON-encoded array (SQLite mirror).
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(c).strip().upper() for c in parsed if str(c).strip()]
            except Exception:
                return []
        # Postgres array literal "{SG,MY}" — defensive.
        if s.startswith("{") and s.endswith("}"):
            inner = s[1:-1]
            return [c.strip().upper() for c in inner.split(",") if c.strip()]
        # Single bare country.
        return [s.upper()]
    return []


# --- Specificity scoring -----------------------------------------------------

def _score(
    override: Dict[str, Any],
    *,
    employee_level: Optional[str],
    assignment_type: Optional[str],
) -> Optional[int]:
    """
    Returns the specificity score for an override given the employee
    context, or None if the override is disqualified (a non-wildcard axis
    doesn't match the employee).

    NULL axis is a wildcard: it matches any employee value but contributes
    zero to the score, so a more-specific row wins on tie-break.
    """
    score = 0

    ov_level = override.get("employee_level")
    if ov_level is not None and str(ov_level).strip():
        if employee_level is None or str(ov_level).strip() != str(employee_level).strip():
            return None
        score += 2

    ov_atype = override.get("assignment_type")
    if ov_atype is not None and str(ov_atype).strip():
        if assignment_type is None or str(ov_atype).strip() != str(assignment_type).strip():
            return None
        score += 1

    return score


def _tiebreak_key(override: Dict[str, Any]) -> Tuple[int, str]:
    """
    For ties on specificity score: prefer higher display_order, then
    most-recent updated_at. Returns a key suitable for max(..., key=...).
    """
    display_order = int(override.get("display_order") or 0)
    updated = override.get("updated_at") or ""
    return (display_order, str(updated))


# --- Public resolver ---------------------------------------------------------

def resolve_effective_benefit(
    base_row: Dict[str, Any],
    overrides: Iterable[Dict[str, Any]],
    employee_ctx: Dict[str, Optional[str]],
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Apply Section C resolution to a single base benefit row.

    Args:
      base_row:       row dict from policy_config_benefits (must contain
                      at minimum 'id', 'amount_value', 'currency_code',
                      'cap_rule_json'; markdown fields if present).
      overrides:      iterable of override row dicts attached to this base
                      row. May be empty.
      employee_ctx:   dict with keys 'country' (ISO alpha-2 string),
                      'employee_level' (one of entry/manager/director/vp/
                      c_suite or None), 'assignment_type' (string or None).

    Returns:
      (effective_row, applied_override_id)
        - effective_row: a copy of base_row with non-NULL override fields
                         folded in. Adds two diagnostic keys:
                            'override_applied': bool,
                            'override_id': str | None.
        - applied_override_id: same as effective_row['override_id'].

    A None or empty country in employee_ctx skips override evaluation
    entirely — without a country, jurisdiction overrides cannot match.
    """
    country = (employee_ctx.get("country") or "").strip().upper() if employee_ctx else ""
    employee_level = employee_ctx.get("employee_level") if employee_ctx else None
    assignment_type = employee_ctx.get("assignment_type") if employee_ctx else None

    effective = dict(base_row)
    effective["override_applied"] = False
    effective["override_id"] = None

    if not country:
        return effective, None

    # Filter to overrides that include the employee's country and pass the
    # axis-match gate.
    candidates: List[Tuple[int, Dict[str, Any]]] = []
    for ov in overrides:
        countries = _coerce_countries(ov.get("jurisdiction_countries"))
        if country not in countries:
            continue
        score = _score(
            ov,
            employee_level=employee_level,
            assignment_type=assignment_type,
        )
        if score is None:
            continue
        candidates.append((score, ov))

    if not candidates:
        return effective, None

    # Highest score wins. Ties resolved by display_order then updated_at.
    max_score = max(s for s, _ in candidates)
    top = [ov for s, ov in candidates if s == max_score]
    winner = max(top, key=_tiebreak_key)

    # Fold non-NULL winner fields onto the base. NULL means "inherit from
    # base" — HR can override markdown only without redefining the cap.
    overridable = (
        "amount_value",
        "currency_code",
        "cap_rule_json",
        "reimbursement_md",
        "repayment_md",
    )
    for key in overridable:
        val = winner.get(key)
        if val is not None and val != "":
            effective[key] = val

    effective["override_applied"] = True
    effective["override_id"] = str(winner.get("id")) if winner.get("id") is not None else None

    return effective, effective["override_id"]


# --- Bulk helper -------------------------------------------------------------

def resolve_many(
    base_rows: Iterable[Dict[str, Any]],
    overrides_by_benefit_id: Dict[str, List[Dict[str, Any]]],
    employee_ctx: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    """
    Apply resolve_effective_benefit across a list of base rows. The caller
    is responsible for grouping overrides by benefit_row_id beforehand
    (typically a single SQL query: SELECT * FROM
    policy_benefit_jurisdiction_overrides WHERE benefit_row_id = ANY(:ids)
    then group in Python).

    Returns the list in the same order as base_rows, each enriched with
    override_applied / override_id diagnostic fields.
    """
    out: List[Dict[str, Any]] = []
    for row in base_rows:
        bid = str(row.get("id") or "")
        ovs = overrides_by_benefit_id.get(bid, [])
        eff, _ = resolve_effective_benefit(row, ovs, employee_ctx)
        out.append(eff)
    return out
