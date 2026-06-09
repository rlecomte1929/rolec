"""French NIR recognizer (INSEE social-security number, mod-97 key) — AI-I.3d.

The Numéro d'Inscription au Répertoire is 15 characters: a 13-character number
(sex 1, year 2, month 2, department 2, commune 3, order 3) + a 2-digit control
key = 97 − (number mod 97). Corsican departments ``2A``/``2B`` are mapped to
``19``/``18`` before the modulus. Validating the key keeps false positives far
below a bare ``\\d{15}`` match.

Two layers (mirrors ``iban.py``):
  - ``is_valid_nir`` / ``nir_key`` — pure-Python, presidio-free, unit-testable.
  - ``get_recognizers`` — lazy-imports presidio; ``validate_result`` runs the
    mod-97 key check.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

FR_NIR_ENTITY = "FR_NIR"

# Structured NIR with optional single separators between the official groups.
# sex(1) year(2) month(2) dept(2 | 2A/2B) commune(3) order(3) key(2).
_NIR_RE = re.compile(
    r"(?<![0-9A-Z])"
    r"[12]"
    r"[ .]?\d{2}"
    r"[ .]?\d{2}"
    r"[ .]?(?:\d{2}|2[AB])"
    r"[ .]?\d{3}"
    r"[ .]?\d{3}"
    r"[ .]?\d{2}"
    r"(?![0-9])"
)


def nir_key(nir13: str) -> Optional[int]:
    """Return the mod-97 control key (1–97) for the 13-character NIR body, or
    ``None`` if it is malformed."""
    s = (nir13 or "").upper()
    if len(s) != 13:
        return None
    if s[5:7] == "2A":
        s = s[:5] + "19" + s[7:]
    elif s[5:7] == "2B":
        s = s[:5] + "18" + s[7:]
    if not s.isdigit():
        return None
    return 97 - (int(s) % 97)


def is_valid_nir(candidate: str) -> bool:
    """True iff ``candidate`` (separators allowed) is a structurally valid French
    NIR. Never raises."""
    nir = re.sub(r"[ .]", "", (candidate or "").upper())
    if len(nir) != 15:
        return False
    if nir[0] not in "12":
        return False
    body, key_str = nir[:13], nir[13:15]
    if not key_str.isdigit():
        return False
    key = nir_key(body)
    return key is not None and int(key_str) == key


def get_recognizers() -> "List[EntityRecognizer]":
    """Return the presidio NIR recognizer. Lazy-imports presidio."""
    from presidio_analyzer import Pattern, PatternRecognizer

    class FrNirRecognizer(PatternRecognizer):
        def __init__(self) -> None:
            super().__init__(
                supported_entity=FR_NIR_ENTITY,
                name="FrNirRecognizer",
                patterns=[Pattern(name="nir", regex=_NIR_RE.pattern, score=0.4)],
                context=["numéro de sécurité sociale", "sécurité sociale", "nir",
                         "insee", "securite sociale", "social security"],
            )

        def validate_result(self, pattern_text: str) -> Optional[bool]:
            return is_valid_nir(pattern_text)

    return [FrNirRecognizer()]
