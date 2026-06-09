"""EU passport recognizer (ICAO 9303 MRZ format) — AI-I.3c.

Detects passport / travel-document numbers across the EU corridors ReloPass
serves, with two layers (mirrors ``iban.py``):

  - Pure-Python detection (``find_passports`` / ``is_valid_mrz_document_number``)
    with **no presidio import**, so recall/false-positive behaviour is
    unit-testable without the ML stack.
  - ``get_recognizers`` lazy-imports presidio and wraps the same patterns in a
    ``PatternRecognizer`` whose ``validate_result`` runs the ICAO 9303 7-3-1
    check-digit so an MRZ candidate that fails the checksum is rejected.

Detection strategy (tuned for recall ≥ 95 %, FP ≤ 1 %)
-----------------------------------------------------
* **Strong** (matched regardless of surrounding text — the shape is distinctive
  enough to keep false positives low):
    - FR booklet number: 2 digits + 2 letters + 5 digits (e.g. ``19AB54321``)
    - IT booklet number: 2 letters + 7 digits (e.g. ``AA1234567``)
    - Any 9-char document field + trailing check digit whose ICAO 9303 checksum
      validates (this is what an MRZ document-number field looks like).
* **Context-gated** (matched only when a passport keyword sits nearby, because
  the shape alone is too generic to flag safely):
    - DE booklet number: 9 alphanumerics starting with a letter
    - NO booklet number: 8 digits

The check-digit primitive is reused from the C1-02 MRZ parser
(``backend.relopass.docs.mrz.compute_check_digit``) rather than reimplemented.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, NamedTuple, Optional

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

# Custom entity label for passport numbers. Distinct from presidio's built-in
# ``US_PASSPORT`` so the two compose rather than collide.
PASSPORT_ENTITY = "PASSPORT"

# Keywords (any language we serve) that license the context-gated shapes.
# Word-boundary matched so "password"/"passenger" do NOT trigger.
_CONTEXT_WORDS = (
    "passport", "passeport", "reisepass", "passaporto", "pasaporte",
    "passnummer", "passnr", "travel document", "mrz", "document number",
    "pass no", "passport no", "passport number",
)
_CONTEXT_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in _CONTEXT_WORDS) + r")(?![a-z])",
    re.IGNORECASE,
)
_CONTEXT_WINDOW = 40  # chars on either side of a candidate

# ── Candidate shapes ─────────────────────────────────────────────────────────
# Strong: distinctive enough to stand alone.
_FR_RE = re.compile(r"(?<![A-Za-z0-9])\d{2}[A-Z]{2}\d{5}(?![A-Za-z0-9])")
_IT_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![A-Za-z0-9])")
# MRZ document field (9 chars, '<' filler allowed) + its trailing check digit.
_MRZ_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9<])[A-Z0-9<]{9}\d(?![A-Za-z0-9])")
# Context-gated: too generic without a nearby passport keyword.
_DE_RE = re.compile(r"(?<![A-Za-z0-9])[C-HJ-NP-Z][0-9A-Z]{8}(?![A-Za-z0-9])")
_NO_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")

# All candidate regexes, used to seed the presidio PatternRecognizer.
_ALL_PATTERNS = {
    "FR": _FR_RE, "IT": _IT_RE, "MRZ": _MRZ_TOKEN_RE, "DE": _DE_RE, "NO": _NO_RE,
}
_STRONG = {"FR", "IT", "MRZ"}


class PassportMatch(NamedTuple):
    start: int
    end: int
    value: str
    country: str   # 'FR' | 'IT' | 'DE' | 'NO' | 'MRZ'
    score: float


def _compute_check_digit(s: str) -> int:
    """ICAO 9303 7-3-1 check digit. Reuses the C1-02 MRZ primitive; falls back
    to a local implementation if that package is unavailable at runtime."""
    try:
        from backend.relopass.docs.mrz import compute_check_digit
        return compute_check_digit(s)
    except Exception:  # pragma: no cover - import fallback
        weights = (7, 3, 1)
        total = 0
        for i, ch in enumerate(s):
            if ch == "<":
                v = 0
            elif ch.isdigit():
                v = ord(ch) - ord("0")
            elif ch.isalpha():
                v = ord(ch.upper()) - ord("A") + 10
            else:
                v = 0
            total += v * weights[i % 3]
        return total % 10


def is_valid_mrz_document_number(token: str) -> bool:
    """True iff ``token`` is a 10-char MRZ document field (9 chars + 1 check
    digit) whose ICAO 9303 checksum is consistent. Never raises."""
    if token is None or len(token) != 10 or not token[9].isdigit():
        return False
    field = token[:9]
    if not re.fullmatch(r"[A-Z0-9<]{9}", field):
        return False
    return _compute_check_digit(field) == int(token[9])


def _has_context(text: str, start: int, end: int) -> bool:
    lo = max(0, start - _CONTEXT_WINDOW)
    hi = min(len(text), end + _CONTEXT_WINDOW)
    return _CONTEXT_RE.search(text[lo:hi]) is not None


def find_passports(text: str) -> List[PassportMatch]:
    """Pure detector: return de-duplicated passport-number matches in ``text``.

    Strong shapes (FR/IT/checksum-valid MRZ token) match anywhere; generic
    shapes (DE/NO) only when a passport keyword is within ``_CONTEXT_WINDOW``.
    On overlap the higher score wins. Never raises."""
    if not text:
        return []
    raw: List[PassportMatch] = []

    for country, rx in _ALL_PATTERNS.items():
        for m in rx.finditer(text):
            value = m.group(0)
            if country == "MRZ":
                if not is_valid_mrz_document_number(value):
                    continue
                score = 0.95
            elif country in _STRONG:
                score = 0.6
            else:  # DE / NO — require nearby passport context
                if not _has_context(text, m.start(), m.end()):
                    continue
                score = 0.55
            raw.append(PassportMatch(m.start(), m.end(), value, country, score))

    # De-overlap: keep the highest-scoring match for any overlapping span.
    raw.sort(key=lambda x: (-x.score, x.start))
    kept: List[PassportMatch] = []
    for cand in raw:
        if any(cand.start < k.end and k.start < cand.end for k in kept):
            continue
        kept.append(cand)
    kept.sort(key=lambda x: x.start)
    return kept


def get_recognizers() -> "List[EntityRecognizer]":
    """Return the presidio EU-passport recognizer. Lazy-imports presidio so the
    package stays import-safe without the ML stack installed."""
    from presidio_analyzer import Pattern, PatternRecognizer

    class EuPassportRecognizer(PatternRecognizer):
        """Country-format + MRZ-checksum passport recognizer.

        Regex candidates start at a modest score; ``validate_result`` promotes a
        match to certain when its trailing check digit passes the ICAO 9303
        checksum, and the generic DE/NO shapes lean on ``context`` words to
        clear the analyzer threshold rather than firing on any 8-9 char run."""

        def __init__(self) -> None:
            super().__init__(
                supported_entity=PASSPORT_ENTITY,
                patterns=[
                    Pattern(name="passport (MRZ field+CD)", regex=_MRZ_TOKEN_RE.pattern, score=0.4),
                    Pattern(name="passport (FR)", regex=_FR_RE.pattern, score=0.6),
                    Pattern(name="passport (IT)", regex=_IT_RE.pattern, score=0.55),
                    Pattern(name="passport (DE)", regex=_DE_RE.pattern, score=0.3),
                    Pattern(name="passport (NO)", regex=_NO_RE.pattern, score=0.3),
                ],
                context=list(_CONTEXT_WORDS),
            )

        def validate_result(self, pattern_text: str) -> Optional[bool]:
            # A 10-char MRZ field carries its own check digit → verify it.
            if len(pattern_text) == 10 and pattern_text[9:].isdigit():
                return is_valid_mrz_document_number(pattern_text)
            # Country-format shapes can't be checksum-verified here; leave the
            # score as-is (presidio applies context boosting).
            return None

    return [EuPassportRecognizer()]
