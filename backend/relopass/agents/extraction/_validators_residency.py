"""Residency cross-check validator (C2-02b, standalone).

Emits a WARN-severity Finding when a TAX_CERT's stated country of
residence diverges from the case employee's current residence country.
This is the canonical Cohort 2 cross-document check for the FR→NO
corridor (Marc Bouchard scenario: tax cert shows France, employee profile
says Norway, → likely an out-of-date tax cert that the receiving
authority will reject).

Pure-stdlib helper — same convention as :mod:`_validators_freshness` and
:mod:`_validators_tax_id`. Independent of the C1-05a runtime merge state.

Architecture Report references:
    §3.3 — TAX_CERT validation rule ("matches stated current country of residence").
    §3.6 — the CONTRADICTION_RESIDENCE family of cross-document checks.

Public surface:
    residency_mismatch_finding(...) — returns Finding when countries diverge
"""

from __future__ import annotations

from typing import Optional

from ._validators_freshness import Finding


def residency_mismatch_finding(
    *,
    tax_cert_country_iso3: Optional[str],
    case_employee_country_iso3: Optional[str],
    code: str = "TAX_CERT_RESIDENCE_MISMATCH",
) -> Optional[Finding]:
    """Return a WARN-severity Finding if the two countries diverge.

    Behaviour matrix:

    +-------------------------------+----------------------------+-------------+
    | tax_cert_country              | case_employee_country      | result      |
    +===============================+============================+=============+
    | None                          | any                        | None        |
    +-------------------------------+----------------------------+-------------+
    | any                           | None                       | None        |
    +-------------------------------+----------------------------+-------------+
    | "FRA" (case-insens.)          | "FRA"                      | None        |
    +-------------------------------+----------------------------+-------------+
    | "FRA"                         | "NOR"                      | WARN        |
    +-------------------------------+----------------------------+-------------+

    The check is case-insensitive on the ISO codes (so "fra" matches "FRA")
    but does NOT attempt to normalise "France" → "FRA"; that's the
    extraction layer's job before this validator runs.

    Args:
        tax_cert_country_iso3: ISO 3166-1 alpha-3 code from the tax cert.
            None means the extraction didn't yield a residence country
            (often because the issuer is missing or unreadable).
        case_employee_country_iso3: ISO 3166-1 alpha-3 from the case's
            employee.current_residence_country. None means the case
            record doesn't carry this fact yet.
        code: Override the finding code if you want a corridor-specific
            label (e.g. "FR_NO_RESIDENCE_DRIFT" from the FR→NO corridor
            agent). Default fires the generic TAX_CERT code.

    Returns:
        Finding with severity="WARN" if both countries are present and
        differ, else None.

    Examples:
        >>> residency_mismatch_finding(
        ...     tax_cert_country_iso3="FRA",
        ...     case_employee_country_iso3="NOR"
        ... ).code
        'TAX_CERT_RESIDENCE_MISMATCH'
        >>> residency_mismatch_finding(
        ...     tax_cert_country_iso3="NOR",
        ...     case_employee_country_iso3="NOR"
        ... ) is None
        True
        >>> residency_mismatch_finding(
        ...     tax_cert_country_iso3=None,
        ...     case_employee_country_iso3="NOR"
        ... ) is None
        True
    """
    if not tax_cert_country_iso3 or not case_employee_country_iso3:
        return None

    a = tax_cert_country_iso3.strip().upper()
    b = case_employee_country_iso3.strip().upper()

    if a == b:
        return None

    return Finding(
        severity="WARN",
        code=code,
        message=(
            f"Tax certificate states residence in {a}, but case employee's current "
            f"residence on file is {b}. Tax cert is likely out of date or pertains to "
            f"a prior tax year before the relocation. HR should request an updated "
            f"document from the destination country's tax authority."
        ),
    )
