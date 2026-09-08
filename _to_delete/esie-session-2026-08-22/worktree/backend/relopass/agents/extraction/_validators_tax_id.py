"""Tax-ID format validators (C2-02b, standalone).

Per-country format + checksum validators for the tax-identification numbers
that appear on TAX_CERT documents (and also on CRIMINAL_RECORD documents
issued in some jurisdictions). Pure-stdlib helper for the same reason as
:mod:`_validators_freshness` — lands independently of the C1-05a runtime
merge state and slots in cleanly once the agent files are wired.

Covered IDs:
    FR  numéro fiscal de référence (SPI)         13 digits, no checksum standard
    DE  Steuer-Identifikationsnummer (IdNr)      11 digits, no checksum at v1
    NO  fødselsnummer (FNR)                      11 digits, Mod-11 on positions 10 + 11

Why Mod-11 matters for NO: every Norwegian tax cert (skattemelding), every
Norwegian payslip, and every Norwegian residence permit application carries
the holder's fødselsnummer. A Mod-11 failure is a strong signal of OCR
corruption or document tampering. UDI rejects applications with malformed
FNRs at intake.

Architecture Report references:
    §3.3 — personal-document field-set table (tax_id row).
    §3.4 — entity normalization.

Public surface:
    is_valid_fr_spi(s)              — FR 13-digit format check
    is_valid_de_steuer_idnr(s)      — DE 11-digit format check
    is_valid_no_fodselsnummer(s)    — NO Mod-11 + format check
    tax_id_format_finding(...)      — returns Finding when malformed
"""

from __future__ import annotations

import re
from typing import Final, Literal, Optional

from ._validators_freshness import Finding


# ─────────────────────────────────────────────────────────────────────────────
# FR — numéro fiscal de référence (SPI)
# ─────────────────────────────────────────────────────────────────────────────

#: SPI is exactly 13 digits, no separators, no leading zero stripped. The
#: official DGFiP documentation does not publish a checksum algorithm for
#: the SPI, so v1 verifies format only. A future iteration could add the
#: undocumented Luhn-style checks some private tools use.
_FR_SPI_RE: Final = re.compile(r"^\d{13}$")


def is_valid_fr_spi(s: str) -> bool:
    """Return True if ``s`` is a syntactically-valid FR SPI (13 digits)."""
    return bool(_FR_SPI_RE.match(s or ""))


# ─────────────────────────────────────────────────────────────────────────────
# DE — Steuer-Identifikationsnummer (IdNr, "Steuer-IdNr")
# ─────────────────────────────────────────────────────────────────────────────

#: The Steuer-IdNr is exactly 11 digits. The Bundeszentralamt für Steuern
#: spec includes a checksum (ISO 7064 MOD 11,10 variant) that we don't yet
#: implement — format-only check at v1. A future iteration should add it.
_DE_STEUER_RE: Final = re.compile(r"^\d{11}$")


def is_valid_de_steuer_idnr(s: str) -> bool:
    """Return True if ``s`` is a syntactically-valid DE Steuer-IdNr (11 digits)."""
    return bool(_DE_STEUER_RE.match(s or ""))


# ─────────────────────────────────────────────────────────────────────────────
# NO — fødselsnummer (FNR)
# ─────────────────────────────────────────────────────────────────────────────

#: Skatteetaten Mod-11 weights — first 9 digits → check digit 1
_FNR_WEIGHTS_1: Final = (3, 7, 6, 1, 8, 9, 4, 5, 2)

#: Mod-11 weights — first 10 digits → check digit 2
_FNR_WEIGHTS_2: Final = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

_FNR_FORMAT_RE: Final = re.compile(r"^\d{11}$")


def is_valid_no_fodselsnummer(fnr: str) -> bool:
    """Return True if ``fnr`` is a Mod-11-valid Norwegian fødselsnummer.

    The algorithm (per the Skatteetaten reference at
    https://www.skatteetaten.no/en/person/national-registry/identitetsnummer/):

      1. Format: exactly 11 digits, no separators.
      2. Compute check digit 1 = 11 - (sum_i (weights1[i] * digits[i]) mod 11)
         over digits 0-8. If 11 → 0; if 10 → invalid.
      3. Verify check digit 1 matches digits[9].
      4. Compute check digit 2 = 11 - (sum_i (weights2[i] * digits[i]) mod 11)
         over digits 0-9 (i.e. including the first check digit).
         If 11 → 0; if 10 → invalid.
      5. Verify check digit 2 matches digits[10].

    Examples:
        >>> is_valid_no_fodselsnummer("14058510131")  # Mod-11-valid synthetic
        True
        >>> is_valid_no_fodselsnummer("14058510132")  # last digit flipped
        False
        >>> is_valid_no_fodselsnummer("1405851013")   # only 10 digits
        False
        >>> is_valid_no_fodselsnummer("14058510X31")  # non-digit
        False
        >>> is_valid_no_fodselsnummer("")             # empty
        False
    """
    if not _FNR_FORMAT_RE.match(fnr or ""):
        return False

    digits = [int(d) for d in fnr]

    s1 = sum(w * d for w, d in zip(_FNR_WEIGHTS_1, digits[:9]))
    k1 = 11 - (s1 % 11)
    if k1 == 11:
        k1 = 0
    if k1 == 10 or k1 != digits[9]:
        return False

    s2 = sum(w * d for w, d in zip(_FNR_WEIGHTS_2, digits[:10]))
    k2 = 11 - (s2 % 11)
    if k2 == 11:
        k2 = 0
    return k2 != 10 and k2 == digits[10]


# ─────────────────────────────────────────────────────────────────────────────
# Unified finding emitter — used by TAX_CERT agents at extraction time
# ─────────────────────────────────────────────────────────────────────────────

#: ISO 3166-1 alpha-3 country codes the validator family covers.
Country = Literal["FRA", "DEU", "NOR"]


def tax_id_format_finding(
    *,
    country: Country,
    tax_id: Optional[str],
) -> Optional[Finding]:
    """Return a WARN-severity :class:`Finding` if ``tax_id`` is malformed.

    Routes to the per-country validator based on ``country``. Returns None
    when the tax_id is valid OR when it's None (a missing tax_id is a
    different finding — emitted by the prompt's REQUIRED_FIELDS check, not
    here).

    Args:
        country: ISO 3166-1 alpha-3 code. FRA / DEU / NOR only — other
            countries return None (deferred validators).
        tax_id: The extracted tax_id string. None bypasses the check.

    Returns:
        Finding with severity="WARN" if malformed, else None.

    Examples:
        >>> tax_id_format_finding(country="NOR", tax_id="14058510131") is None
        True
        >>> tax_id_format_finding(country="NOR", tax_id="14058510132").code
        'TAX_ID_FORMAT_INVALID_NO'
        >>> tax_id_format_finding(country="FRA", tax_id="0123456789012").code  # only 13 digits, this one is valid
        None
    """
    if tax_id is None:
        return None

    if country == "FRA":
        if is_valid_fr_spi(tax_id):
            return None
        return Finding(
            severity="WARN",
            code="TAX_ID_FORMAT_INVALID_FR",
            message=(
                f"Extracted FR numéro fiscal {tax_id!r} does not match the 13-digit SPI format. "
                f"Likely OCR error on a digit; flag for HR review."
            ),
        )

    if country == "DEU":
        if is_valid_de_steuer_idnr(tax_id):
            return None
        return Finding(
            severity="WARN",
            code="TAX_ID_FORMAT_INVALID_DE",
            message=(
                f"Extracted DE Steuer-IdNr {tax_id!r} does not match the 11-digit format. "
                f"Likely OCR error; flag for HR review."
            ),
        )

    if country == "NOR":
        if is_valid_no_fodselsnummer(tax_id):
            return None
        return Finding(
            severity="WARN",
            code="TAX_ID_FORMAT_INVALID_NO",
            message=(
                f"Extracted NO fødselsnummer {tax_id!r} failed the Skatteetaten Mod-11 check. "
                f"Strong signal of OCR corruption or document tampering — block submission to UDI."
            ),
        )

    return None  # Unknown country, skip silently
