"""Multilingual person-name recognizer (FR/DE/NO/Hindi boosters) — AI-I.3e.

Stock Presidio person-name NER underperforms in the languages mobility cases
run in. This adds two context-boosted layers (mirrors ``iban.py`` / ``eu_passport.py``):

  - Pure-Python detection (``find_names``) with **no presidio import**, so the
    recall/false-positive behaviour is unit-testable without the ML stack.
  - ``get_recognizers`` lazy-imports presidio and returns ``PatternRecognizer``
    instances (Latin context-boosted + Devanagari) that compose on top of the
    NER engine via Presidio's ``context`` mechanism.

Detection strategy (tuned for recall ≥ 0.90, FP ≤ 1 %, cross-language FP ≤ 1 %)
-----------------------------------------------------------------------------
Person names can't be regex'd in isolation (any capitalised word could be one),
so detection is **context-driven** — the whole point of the task:

  1. **Honorific + capitalised token(s)** — an honorific (FR ``M.``/``Mme``,
     DE ``Herr``/``Frau``, NO ``herr``/``fru``, EN ``Mr``/``Dr``, Hindi
     ``श्री``/``श्रीमती``) immediately followed by 1-3 capitalised tokens.
  2. **Birth/name cue + full name** — a cue (FR ``né``/``née``, DE ``geboren``,
     NO ``født``, ``navn``/``nom``/``name``) within a small window of a 2-3
     capitalised-token sequence, rejecting a sequence introduced by a place
     preposition (``in``/``à``/``i`` …) so "geboren in Bad Homburg" is not a name.
  3. **Devanagari run** — a sequence of Devanagari (Hindi) characters; in a
     Latin-script product this is almost always a personal name, boosted further
     by a Devanagari honorific.

Bare capitalised sequences with no cue are left to Presidio's NER — this module
only adds the context boosters, which keeps cross-language false positives low.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, NamedTuple

if TYPE_CHECKING:
    from presidio_analyzer import EntityRecognizer

# Presidio's canonical person entity, so this composes with the NER PERSON
# results instead of inventing a parallel label.
PERSON_ENTITY = "PERSON"

# ── Context vocabularies ─────────────────────────────────────────────────────
# Honorifics that directly introduce a name (Latin scripts).
_HONORIFICS = (
    "M", "Mme", "Mlle", "Monsieur", "Madame",
    "Herr", "Frau",
    "herr", "fru",
    "Mr", "Mrs", "Ms", "Dr", "Prof",
)
# Birth / name cues that sit near (not necessarily adjacent to) a name.
_NAME_CUES = (
    "né", "née", "nee", "prénom", "prenom", "nom",
    "geboren", "Name", "Vorname", "Nachname",
    "født", "fodt", "navn", "fornavn", "etternavn",
    "name", "born",
)
# Devanagari honorifics (Hindi).
_DEVA_HONORIFICS = ("श्री", "श्रीमती", "कुमारी", "डॉ", "सुश्री")

# Place prepositions: a capitalised run right after one of these is a place,
# not a person (kills "geboren in Bad Homburg" / "né à Lyon Centre").
_PLACE_PREPS = {
    "in", "à", "a", "i", "im", "aus", "von", "nach", "zu", "zur", "zum",
    "at", "de", "du", "des", "of",
}

# Geographic / structural words a *place* ends in but a person's name does not.
# Whole-token match (so "Nordmann" is unaffected by "Nord"). Used to reject a
# cue-adjacent capitalised run that is a place, e.g. "Bergen Sentrum",
# "Paris Nord", "Empire State".
_PLACE_WORDS = {
    "Sentrum", "Centre", "Center", "City", "State", "Nord", "Sud", "Syd",
    "Est", "Ouest", "Vest", "West", "East", "North", "South", "Süd", "Ost",
    "Plaza", "Square", "Park", "Station", "Airport", "Building", "Tower",
    "Strasse", "Straße", "Gate", "Vei", "Gata", "Centrum", "Nord-Est",
}

# ── Patterns ─────────────────────────────────────────────────────────────────
# A capitalised name token: starts uppercase (incl. accented), then letters /
# apostrophes / hyphens. Accented ranges cover FR/DE/NO diacritics.
_CAP = r"[A-ZÀ-ÖØ-Þ][A-Za-zà-öø-ÿÀ-ÖØ-Þ'’\-]+"
# Single-letter "M" requires a period (so "M Theory" / "M Night" don't trip);
# multi-char honorifics allow an optional period.
_HON_RE = re.compile(
    r"\b(?:M\.|(?:Mme|Mlle|Monsieur|Madame|Herr|Frau|herr|fru|Mr|Mrs|Ms|Dr|Prof)\.?)\s+"
    r"(" + _CAP + r"(?:\s+" + _CAP + r"){0,2})"
)
_CUE_RE = re.compile(
    r"(?<![\wÀ-ÿ])(?:" + "|".join(re.escape(c) for c in _NAME_CUES) + r")(?![\wÀ-ÿ])",
    re.IGNORECASE,
)
# Two-to-three capitalised tokens, capturing the immediately preceding word so a
# place preposition can be rejected.
_FULLNAME_RE = re.compile(r"(\b[A-Za-zÀ-ÿ']+\s+)?(" + _CAP + r"(?:\s+" + _CAP + r"){1,2})")
_DEVA_RUN_RE = re.compile(r"[ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}")
_DEVA_HON_RE = re.compile(r"(?:" + "|".join(_DEVA_HONORIFICS) + r")")

_CUE_WINDOW = 40


class NameMatch(NamedTuple):
    start: int
    end: int
    value: str
    kind: str   # 'honorific' | 'cue' | 'devanagari'
    score: float


def _add(acc, start, end, value, kind, score):
    acc.append(NameMatch(start, end, value.strip(), kind, score))


def find_names(text: str) -> List[NameMatch]:
    """Pure context-boosted name detector. De-duplicated, highest score wins on
    overlap. Never raises."""
    if not text:
        return []
    raw: List[NameMatch] = []

    # 1) Devanagari runs (Hindi names).
    for m in _DEVA_RUN_RE.finditer(text):
        boosted = _DEVA_HON_RE.search(text[max(0, m.start() - 12):m.start()]) is not None
        _add(raw, m.start(), m.end(), m.group(0), "devanagari", 0.85 if boosted else 0.6)

    # 2) Honorific + capitalised token(s).
    for m in _HON_RE.finditer(text):
        g = m.group(1)
        s = m.start(1)
        _add(raw, s, s + len(g), g, "honorific", 0.85)

    # 3) Birth/name cue within window of a 2-3 capitalised-token sequence.
    cue_spans = [(m.start(), m.end()) for m in _CUE_RE.finditer(text)]
    if cue_spans:
        for m in _FULLNAME_RE.finditer(text):
            prev = (m.group(1) or "").strip().lower()
            if prev in _PLACE_PREPS:
                continue  # a place, not a person
            name = m.group(2)
            if any(tok in _PLACE_WORDS for tok in name.split()):
                continue  # a place/structure (e.g. "Bergen Sentrum"), not a person
            ns, ne = m.start(2), m.end(2)
            near = any(abs(cs - ns) <= _CUE_WINDOW or abs(ce - ns) <= _CUE_WINDOW
                       or (cs <= ns <= ce) for cs, ce in cue_spans)
            if near:
                _add(raw, ns, ne, name, "cue", 0.7)

    # De-overlap: keep the highest-scoring match per overlapping span.
    raw.sort(key=lambda x: (-x.score, x.start))
    kept: List[NameMatch] = []
    for cand in raw:
        if any(cand.start < k.end and k.start < cand.end for k in kept):
            continue
        kept.append(cand)
    kept.sort(key=lambda x: x.start)
    return kept


def get_recognizers() -> "List[EntityRecognizer]":
    """Return the presidio multilingual-name recognizers. Lazy-imports presidio
    so the package stays import-safe without the ML stack installed."""
    from presidio_analyzer import Pattern, PatternRecognizer

    latin = PatternRecognizer(
        supported_entity=PERSON_ENTITY,
        name="MultilingualNameRecognizer",
        patterns=[
            Pattern(name="honorific+name", regex=_HON_RE.pattern, score=0.5),
            Pattern(name="full name (2-3 caps)", regex=r"\b" + _CAP + r"(?:\s+" + _CAP + r"){1,2}\b", score=0.2),
        ],
        # Context words boost the score when they sit near the candidate — this
        # is the "context booster" the task asks for.
        context=[c for c in _NAME_CUES] + [h for h in _HONORIFICS],
    )
    devanagari = PatternRecognizer(
        supported_entity=PERSON_ENTITY,
        name="DevanagariNameRecognizer",
        patterns=[Pattern(name="devanagari run", regex=_DEVA_RUN_RE.pattern, score=0.55)],
        context=list(_DEVA_HONORIFICS),
    )
    return [latin, devanagari]
