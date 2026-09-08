"""Runtime finding assembly shared by the three TAX_CERT agents (C2-02b).

The FR / DE / NO tax-cert agents are separate modules (separate prompts,
separate canonical field sets), but their post-extraction finding logic is
identical: take the findings the prompt emitted, then layer on the three
runtime cross-checks that the prompt cannot perform because they need case
context the LLM never sees:

1. ``freshness_finding``       — is the cert too old to submit?
2. ``tax_id_format_finding``   — does the extracted tax_id pass the
                                  per-country format / checksum?
3. ``residency_mismatch_finding`` — does the cert's residence country match
                                  the case employee's current residence?

This helper is the one place that logic lives, so the three agents stay in
lockstep. It is pure-stdlib (no SDK, no DB) like the ``_validators_*``
modules it composes.

Issue-date note (deviation, intentional):
    The TAX_CERT prompts emit ``issue_year`` (an integer), NOT a full
    ``issue_date``. The freshness validator wants a ``date``. We derive the
    most-generous date — 31 December of ``issue_year`` — so a cert is never
    falsely flagged stale on the strength of a coarse year-only signal. A
    later iteration that captures the full "Délivré le" / "Ausgestellt am" /
    "Utstedt" date should pass it through directly instead.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional, Tuple

from ._validators_freshness import Finding, freshness_finding
from ._validators_residency import residency_mismatch_finding
from ._validators_tax_id import Country, tax_id_format_finding

#: Finding code emitted when a tax cert exceeds the freshness threshold.
TAX_CERT_FRESHNESS_CODE = "TAX_CERT_STALE"


def issue_date_from_year(issue_year: Any) -> Optional[date]:
    """Derive a ``date`` from the prompt's integer ``issue_year``.

    Returns 31 December of the year (the most-generous reading — see the
    module docstring). Returns None when ``issue_year`` is absent or not a
    plausible 4-digit year.
    """
    try:
        year = int(issue_year)
    except (TypeError, ValueError):
        return None
    if year < 1900 or year > 2999:
        return None
    return date(year, 12, 31)


def llm_findings(payload: Mapping[str, Any]) -> Tuple[Finding, ...]:
    """Convert the prompt's ``findings`` array into :class:`Finding` objects.

    The prompt's finding shape is ``{severity, code, text_verbatim, bbox}``;
    ``text_verbatim`` maps to the Finding ``message``. Malformed entries are
    skipped rather than raising — a bad finding must never sink an otherwise
    good extraction.
    """
    out = []
    raw = payload.get("findings")
    if not isinstance(raw, (list, tuple)):
        return ()
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        severity = item.get("severity")
        code = item.get("code")
        if severity not in ("INFO", "WARN", "ERROR") or not code:
            continue
        bbox = item.get("bbox")
        out.append(
            Finding(
                severity=severity,
                code=str(code),
                message=item.get("text_verbatim") or str(code),
                bbox=tuple(bbox) if isinstance(bbox, (list, tuple)) and len(bbox) == 4 else None,
            )
        )
    return tuple(out)


def runtime_findings(
    *,
    country: Country,
    payload: Mapping[str, Any],
    case_employee_country_iso3: Optional[str],
    reference_date: date,
    freshness_code: str = TAX_CERT_FRESHNESS_CODE,
) -> Tuple[Finding, ...]:
    """Assemble the three runtime cross-check findings for one tax cert.

    None of these come from the LLM — they are computed at persist time
    against case context. Each is appended only when it fires.

    Args:
        country: ISO 3166-1 alpha-3 of the issuing country (FRA / DEU / NOR).
        payload: The parsed LLM JSON.
        case_employee_country_iso3: The case employee's current residence
            country. None when the case doesn't carry it yet (skips the
            residency check).
        reference_date: Freshness reference — usually ``case.created_at``.
        freshness_code: Override for the staleness finding code.

    Returns:
        Tuple of the findings that fired (possibly empty).
    """
    out = []

    issue_dt = issue_date_from_year(payload.get("issue_year"))
    if issue_dt is not None:
        f = freshness_finding(issue_dt, reference_date=reference_date, code=freshness_code)
        if f is not None:
            out.append(f)

    f = tax_id_format_finding(country=country, tax_id=payload.get("tax_id"))
    if f is not None:
        out.append(f)

    f = residency_mismatch_finding(
        tax_cert_country_iso3=payload.get("residence_country_iso3"),
        case_employee_country_iso3=case_employee_country_iso3,
    )
    if f is not None:
        out.append(f)

    return tuple(out)


def all_findings(
    *,
    country: Country,
    payload: Mapping[str, Any],
    case_employee_country_iso3: Optional[str],
    reference_date: date,
    freshness_code: str = TAX_CERT_FRESHNESS_CODE,
) -> Tuple[Finding, ...]:
    """LLM-emitted findings followed by the runtime cross-check findings."""
    return llm_findings(payload) + runtime_findings(
        country=country,
        payload=payload,
        case_employee_country_iso3=case_employee_country_iso3,
        reference_date=reference_date,
        freshness_code=freshness_code,
    )
