"""German Steuer-ID recognizer (ISO 7064 MOD 11,10) — AI-I.3d.

The Steuerliche Identifikationsnummer is an 11-digit identifier: 10 data digits
+ 1 ISO 7064 MOD 11,10 check digit. It also obeys a digit-uniqueness rule —
within the first 10 digits exactly one digit repeats (twice, or thrice) and the
first digit is non-zero. Enforcing both keeps false positives well below a bare
``\\d{11}`` match.

Two layers (mirrors ``iban.py``):
  - ``is_valid_steuer_id`` / ``steuer_id_check_digit`` — pure-Python, presidio-
    free, unit-testable.
  - ``get_recognizers`` — lazy-imports presidio; ``validate_result`` runs the
    uniqueness + checksum gate.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

DE_STEUER_ID_ENTITY = "DE_STEUER_ID"

# 11 digits, optionally printed as 2/3/3/3 or 3/3/3/2 space groups.
_STEUER_RE = re.compile(r"(?<!\d)\d{2,3}(?:[ ]?\d{3}){2}[ ]?\d{2,3}(?!\d)")


def steuer_id_check_digit(first10: str) -> Optional[int]:
    """ISO 7064 MOD 11,10 check digit for the first 10 digits, or ``None``."""
    if len(first10) != 10 or not first10.isdigit():
        return None
    product = 10
    for ch in first10:
        s = (int(ch) + product) % 10
        if s == 0:
            s = 10
        product = (s * 2) % 11
    return (11 - product) % 10


def _uniqueness_ok(first10: str) -> bool:
    """Within the first 10 digits exactly one digit repeats (2× or 3×); no digit
    occurs more than 3 times."""
    counts = Counter(first10)
    repeated = [d for d, n in counts.items() if n >= 2]
    return len(repeated) == 1 and counts[repeated[0]] in (2, 3) and max(counts.values()) <= 3


def is_valid_steuer_id(candidate: str) -> bool:
    """True iff ``candidate`` (spaces allowed) is a structurally valid German
    Steuer-ID. Never raises."""
    sid = re.sub(r"\s", "", candidate or "")
    if len(sid) != 11 or not sid.isdigit():
        return False
    if sid[0] == "0":  # the first digit is never 0
        return False
    if not _uniqueness_ok(sid[:10]):
        return False
    check = steuer_id_check_digit(sid[:10])
    return check is not None and sid[10] == str(check)


def get_recognizers() -> "List[EntityRecognizer]":
    """Return the presidio Steuer-ID recognizer. Lazy-imports presidio."""
    from presidio_analyzer import Pattern, PatternRecognizer

    class DeSteuerIdRecognizer(PatternRecognizer):
        def __init__(self) -> None:
            super().__init__(
                supported_entity=DE_STEUER_ID_ENTITY,
                name="DeSteuerIdRecognizer",
                patterns=[Pattern(name="steuer-id", regex=_STEUER_RE.pattern, score=0.3)],
                context=["steueridentifikationsnummer", "steuer-id", "steuer id",
                         "steuerid", "idnr", "identifikationsnummer", "tax id"],
            )

        def validate_result(self, pattern_text: str) -> Optional[bool]:
            return is_valid_steuer_id(pattern_text)

    return [DeSteuerIdRecognizer()]
