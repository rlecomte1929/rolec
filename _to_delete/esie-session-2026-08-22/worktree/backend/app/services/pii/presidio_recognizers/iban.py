"""IBAN recognizer (mod-97 checksum validation) — AI-I.3b.

Detects International Bank Account Numbers and validates them with the
ISO 13616 / ISO 7064 mod-97 checksum so the registry only flags structurally
real IBANs (keeps false positives low — bank IBANs are the highest-leverage
PII in the immigration flows).

Two layers:
  - ``is_valid_iban`` — pure-Python format + length + mod-97 validation. No
    presidio import, so this is unit-testable without the ML stack (mirrors how
    the rest of the backend gates heavy optional deps).
  - ``get_recognizers`` — lazy-imports presidio and wraps the validator in a
    ``PatternRecognizer`` whose ``validate_result`` runs the mod-97 check, so a
    regex candidate that fails the checksum is rejected rather than redacted.
    The candidate regexes reuse the compact + 4-char-group spaced shapes already
    vetted in ``backend/app/services/pii_masker.py``.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

# Presidio's canonical entity name for IBANs — reuse it so this recognizer
# composes with the predefined set instead of inventing a parallel label.
IBAN_ENTITY = "IBAN_CODE"

# Official IBAN length per ISO 3166 country code (ISO 13616 registry). Used to
# reject right-checksum-wrong-length candidates before the mod-97 step, which
# meaningfully lowers the false-positive rate vs. a generic 15–34 range.
_IBAN_COUNTRY_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16,
    "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28,
    "CZ": 24, "DE": 22, "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18,
    "GR": 27, "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23,
    "IS": 26, "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "LY": 25, "MC": 27, "MD": 24,
    "ME": 22, "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18, "NO": 15,
    "PK": 24, "PL": 28, "PS": 29, "PT": 25, "QA": 29, "RO": 24, "RS": 22,
    "SA": 24, "SC": 31, "SD": 18, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
    "ST": 25, "SV": 28, "TL": 23, "TN": 24, "TR": 26, "UA": 29, "VA": 22,
    "VG": 24, "XK": 20,
}

# An IBAN is 2 country letters + 2 check digits + up to 30 BBAN alphanumerics
# (total 15–34). Anchored full-string check used by ``is_valid_iban`` after
# normalising spaces out.
_IBAN_FULL_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")


def _normalise(candidate: str) -> str:
    """Strip spaces and uppercase — IBANs are printed in 4-char groups but
    validated as a contiguous uppercase string."""
    return re.sub(r"\s+", "", candidate or "").upper()


def _mod97(iban: str) -> int:
    """ISO 7064 mod-97-10: move the first 4 chars to the end, map letters to
    two-digit numbers (A=10 … Z=35), and take the big integer mod 97."""
    rearranged = iban[4:] + iban[:4]
    digits = "".join(
        str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged
    )
    return int(digits) % 97


def is_valid_iban(candidate: str) -> bool:
    """True iff ``candidate`` is a structurally valid IBAN: correct format,
    a length matching its country (when known), and a passing mod-97 checksum.
    Never raises."""
    iban = _normalise(candidate)
    if not _IBAN_FULL_RE.match(iban):
        return False
    if not (15 <= len(iban) <= 34):
        return False
    expected = _IBAN_COUNTRY_LENGTHS.get(iban[:2])
    if expected is not None and len(iban) != expected:
        return False
    try:
        return _mod97(iban) == 1
    except ValueError:  # pragma: no cover - regex already guards the charset
        return False


def get_recognizers() -> "List[EntityRecognizer]":
    """Return the presidio IBAN recognizer. Lazy-imports presidio so the
    package stays import-safe without the ML stack installed."""
    from presidio_analyzer import Pattern, PatternRecognizer

    class IbanRecognizer(PatternRecognizer):
        """Regex-anchored IBAN recognizer with a mod-97 checksum gate.

        The patterns alone are permissive (any CC + check digits + alnum), so
        they start at a low score; ``validate_result`` runs the ISO-7064
        checksum and promotes a match to certain (True) or rejects it (False).
        Compact and 4-char-group spaced shapes mirror the proven regexes in
        ``pii_masker.py`` to avoid greedy over-grabbing of neighbouring words."""

        def __init__(self) -> None:
            super().__init__(
                supported_entity=IBAN_ENTITY,
                patterns=[
                    Pattern(
                        name="IBAN (compact)",
                        regex=r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
                        score=0.3,
                    ),
                    Pattern(
                        name="IBAN (4-char groups)",
                        regex=r"\b[A-Z]{2}\d{2}(?:\s[A-Z0-9]{2,4}){2,7}\b",
                        score=0.3,
                    ),
                ],
                context=["iban", "bank", "account", "swift", "bic"],
                supported_language="en",
            )

        def validate_result(self, pattern_text: str) -> Optional[bool]:
            return is_valid_iban(pattern_text)

    return [IbanRecognizer()]
