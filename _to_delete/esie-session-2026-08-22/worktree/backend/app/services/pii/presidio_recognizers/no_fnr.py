"""Norwegian fødselsnummer recognizer (MOD-11 check digits) — AI-I.3d.

The fødselsnummer is an 11-digit national identity number: DDMMYY + a 3-digit
individual number + two MOD-11 control digits. Validating both control digits
keeps false positives far below a bare ``\\d{11}`` match.

Two layers (mirrors ``iban.py``):
  - ``is_valid_fnr`` / ``fnr_control_digits`` — pure-Python, presidio-free,
    unit-testable.
  - ``get_recognizers`` — lazy-imports presidio and wraps a ``PatternRecognizer``
    whose ``validate_result`` runs the control-digit check.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

NO_FNR_ENTITY = "NO_FNR"

_K1_WEIGHTS = (3, 7, 6, 1, 8, 9, 4, 5, 2)
_K2_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

# Compact 11 digits, or DDMMYY[ ]NNNNN (one optional separator before the
# individual+control block, the common printed form).
_FNR_RE = re.compile(r"(?<!\d)\d{6}[ .]?\d{5}(?!\d)")


def fnr_control_digits(first9: str) -> Optional[Tuple[int, int]]:
    """Return the two MOD-11 control digits for the first 9 digits, or ``None``
    if the number is structurally impossible (a control digit would be 10)."""
    if len(first9) != 9 or not first9.isdigit():
        return None
    d = [int(c) for c in first9]
    k1 = 11 - (sum(w * x for w, x in zip(_K1_WEIGHTS, d)) % 11)
    if k1 == 11:
        k1 = 0
    if k1 == 10:
        return None
    d10 = d + [k1]
    k2 = 11 - (sum(w * x for w, x in zip(_K2_WEIGHTS, d10)) % 11)
    if k2 == 11:
        k2 = 0
    if k2 == 10:
        return None
    return k1, k2


def _date_plausible(fnr: str) -> bool:
    """Light DDMMYY sanity (accepts D-numbers +40 on day and H-numbers +40 on
    month). Keeps the control-digit check as the primary FP guard."""
    day = int(fnr[0:2])
    month = int(fnr[2:4])
    if day > 40:
        day -= 40  # D-number
    if month > 40:
        month -= 40  # H-number
    return 1 <= day <= 31 and 1 <= month <= 12


def is_valid_fnr(candidate: str) -> bool:
    """True iff ``candidate`` (separators allowed) is a structurally valid
    Norwegian fødselsnummer. Never raises."""
    fnr = re.sub(r"[ .]", "", candidate or "")
    if len(fnr) != 11 or not fnr.isdigit():
        return False
    if not _date_plausible(fnr):
        return False
    ctrl = fnr_control_digits(fnr[:9])
    if ctrl is None:
        return False
    k1, k2 = ctrl
    return fnr[9] == str(k1) and fnr[10] == str(k2)


def get_recognizers() -> "List[EntityRecognizer]":
    """Return the presidio fødselsnummer recognizer. Lazy-imports presidio."""
    from presidio_analyzer import Pattern, PatternRecognizer

    class NoFnrRecognizer(PatternRecognizer):
        def __init__(self) -> None:
            super().__init__(
                supported_entity=NO_FNR_ENTITY,
                name="NoFnrRecognizer",
                patterns=[Pattern(name="fodselsnummer", regex=_FNR_RE.pattern, score=0.3)],
                context=["fødselsnummer", "fodselsnummer", "personnummer", "f.nr", "fnr", "national id"],
            )

        def validate_result(self, pattern_text: str) -> Optional[bool]:
            return is_valid_fnr(pattern_text)

    return [NoFnrRecognizer()]
