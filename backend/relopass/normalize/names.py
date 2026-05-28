"""Name normalization — C1-06.

Two outputs the rest of the pipeline cares about:

  - `surname_main`         : the indexable form (no particles, fully folded,
                             ICAO-9303-aware so Müller and MUELLER collapse
                             together when the issuing state hints at German)
  - `surname_with_particle`: the display form (particles preserved + title-cased)

Plus the given-names canonical list and a single-string `normalized_join`
field used downstream as the embedding source for entity resolution (C1-07).

References:
  - ICAO Doc 9303 Part 3 §6 (transliteration tables) — same data file already
    used by `relopass.docs.mrz` for the MRZ-to-display direction.
  - ISO 15919 — Devanagari ↔ Latin. v1 implements a minimal subset that
    covers common Indian-passport surname patterns; broader script support is
    a follow-up.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Particles (multi-word handled; longest match first)
# ─────────────────────────────────────────────────────────────────────────────

# Per Architecture Report §3.4 — the canonical particle list for surname splitting.
# Order matters: when scanning a surname for a leading particle, multi-word
# variants must be tried before single-word so 'van der' beats 'van'.
PARTICLES_RAW = [
    "van der",
    "van den",
    "von der",
    "de la",
    "de",
    "du",
    "la",
    "le",
    "van",
    "von",
    "del",
]
# Lowercased and sorted by length descending for greedy matching.
_PARTICLES_ORDERED = sorted(PARTICLES_RAW, key=lambda p: -len(p))


# ─────────────────────────────────────────────────────────────────────────────
# Transliteration tables (loaded lazily)
# ─────────────────────────────────────────────────────────────────────────────

_ICAO_TABLE: Optional[dict] = None


def _load_icao_table() -> dict:
    """Lazy-load the same ICAO 9303 table the MRZ parser (C1-02) ships."""
    global _ICAO_TABLE
    if _ICAO_TABLE is not None:
        return _ICAO_TABLE
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "data" / "transliteration" / "icao_9303.json"
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as fh:
                _ICAO_TABLE = json.load(fh)
                return _ICAO_TABLE
    _ICAO_TABLE = {
        "german_scandinavian": {},
        "scandinavian_extras": {},
        "issuing_states_using_german_scandinavian": [],
        "issuing_states_using_scandinavian_extras": [],
    }
    return _ICAO_TABLE


# ─────────────────────────────────────────────────────────────────────────────
# Devanagari → Latin (ISO 15919 minimal subset)
# ─────────────────────────────────────────────────────────────────────────────

# Inline minimal mapping. Covers Hindi vowels + commonly-used consonants for
# names. Anything not in the table passes through unchanged. Full ISO 15919
# (with nukta combinations, diacritic placement, virama handling for
# conjuncts) is a follow-up — the validation criterion is round-trip on
# common name patterns, which this covers.
_DEVANAGARI_INDEPENDENT_VOWELS = {
    "अ": "a", "आ": "ā", "इ": "i", "ई": "ī", "उ": "u", "ऊ": "ū",
    "ऋ": "r̥", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
_DEVANAGARI_VOWEL_SIGNS = {
    "ा": "ā", "ि": "i", "ी": "ī", "ु": "u", "ू": "ū",
    "ृ": "r̥", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}
_DEVANAGARI_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ṅ",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "ñ",
    "ट": "ṭ", "ठ": "ṭh", "ड": "ḍ", "ढ": "ḍh", "ण": "ṇ",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "ś", "ष": "ṣ", "स": "s", "ह": "h",
}
_DEVANAGARI_VIRAMA = "्"


def _is_devanagari(text: str) -> bool:
    """True if the string contains any character in the Devanagari block."""
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def _transliterate_devanagari(text: str) -> str:
    """Minimal ISO-15919-ish Devanagari → Latin. Each consonant gets an
    implicit 'a' unless followed by a vowel sign or virama (halant)."""
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in _DEVANAGARI_INDEPENDENT_VOWELS:
            out.append(_DEVANAGARI_INDEPENDENT_VOWELS[ch])
            i += 1
            continue
        if ch in _DEVANAGARI_CONSONANTS:
            consonant = _DEVANAGARI_CONSONANTS[ch]
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt in _DEVANAGARI_VOWEL_SIGNS:
                out.append(consonant + _DEVANAGARI_VOWEL_SIGNS[nxt])
                i += 2
            elif nxt == _DEVANAGARI_VIRAMA:
                out.append(consonant)
                i += 2
            else:
                # Implicit 'a' at end of consonant cluster
                out.append(consonant + "a")
                i += 1
            continue
        if ch in _DEVANAGARI_VOWEL_SIGNS:
            # Vowel sign without a preceding consonant — emit it standalone.
            out.append(_DEVANAGARI_VOWEL_SIGNS[ch])
            i += 1
            continue
        # Anything else (whitespace, Latin, punctuation, unknown Devanagari) — pass through.
        out.append(ch)
        i += 1
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NormalizedName:
    """The canonical decomposition of a name.

    `surname_main` is the canonical surname used for indexing / blocking /
    embeddings — particles stripped, ICAO-folded, uppercase, ASCII where
    possible. `surname_with_particle` preserves particles for display.
    """
    surname_main: str
    surname_with_particle: str
    given_names: Tuple[str, ...] = field(default_factory=tuple)
    initial: str = ""
    normalized_join: str = ""
    issuing_state_iso3: Optional[str] = None
    transliteration_applied: Tuple[str, ...] = field(default_factory=tuple)


# ─────────────────────────────────────────────────────────────────────────────
# Folding helpers
# ─────────────────────────────────────────────────────────────────────────────


def _strip_diacritics(text: str) -> str:
    """NFD-decompose and drop Mn (non-spacing mark) — the general Latin fold
    used when no issuing-state specific table applies."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _apply_icao_fold(text: str, issuing_state_iso3: Optional[str]) -> Tuple[str, Tuple[str, ...]]:
    """Apply the ICAO 9303 §6 fold for the issuing state if applicable.

    Returns (folded_text, list_of_substitutions_applied).
    Substitutions are recorded as 'Ü→UE' style strings so callers can audit
    what the transliteration did.
    """
    if not text:
        return text, ()
    table = _load_icao_table()
    state = (issuing_state_iso3 or "").upper().strip("<")
    applied: List[str] = []
    out = text

    digraph_states = set(table.get("issuing_states_using_german_scandinavian", []))
    scandi_states = set(table.get("issuing_states_using_scandinavian_extras", []))

    if state in digraph_states:
        # Ä→AE, Ö→OE, Ü→UE, ß→SS (and lowercase variants).
        gs = table.get("german_scandinavian", {})  # {"AE": "Ä", "OE": "Ö", ...}
        for digraph, glyph in gs.items():
            if glyph in out or glyph.lower() in out:
                out = out.replace(glyph, digraph).replace(glyph.lower(), digraph.lower())
                applied.append(f"{glyph}→{digraph}")
    if state in scandi_states:
        # Å→AA, Æ→AE, Ø→OE.
        for glyph, digraph in (("Å", "AA"), ("Æ", "AE"), ("Ø", "OE")):
            if glyph in out or glyph.lower() in out:
                out = out.replace(glyph, digraph).replace(glyph.lower(), digraph.lower())
                applied.append(f"{glyph}→{digraph}")

    return out, tuple(applied)


# ─────────────────────────────────────────────────────────────────────────────
# Particle handling
# ─────────────────────────────────────────────────────────────────────────────


def _split_particle(surname_text: str) -> Tuple[str, str]:
    """Return (particle_part, main_part). The particle is greedy-matched
    from the canonical PARTICLES list at the START of the surname; if no
    match, particle_part is empty and main_part is the original text.

    Comparison is case-insensitive but the original casing of the input is
    preserved in the returned segments.
    """
    if not surname_text:
        return "", surname_text
    lower = surname_text.lower()
    for particle in _PARTICLES_ORDERED:
        # Match as a whole-word prefix followed by whitespace.
        prefix = particle + " "
        if lower.startswith(prefix):
            cut = len(prefix)
            return surname_text[:cut].strip(), surname_text[cut:].strip()
    return "", surname_text


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(
    text: str,
    issuing_state_iso3: Optional[str] = None,
) -> NormalizedName:
    """Decompose a full-name string into canonical parts.

    Two common input shapes:
      - "Surname, Given Names"    (comma-separated; surname first)
      - "Given Names Surname"     (no comma; last token treated as surname
                                   unless particles are detected)

    For passport flows the MRZ already split surname / given_names — those
    callers can either pre-split and feed each half via this function or
    construct a NormalizedName directly.
    """
    if text is None:
        return NormalizedName(surname_main="", surname_with_particle="")

    raw = text.strip()
    if not raw:
        return NormalizedName(surname_main="", surname_with_particle="")

    # Detect Devanagari and transliterate before any further processing.
    if _is_devanagari(raw):
        raw = _transliterate_devanagari(raw)
        # Re-collapse any ASCII-equivalent leftovers.

    # Determine surname/given_names split.
    if "," in raw:
        surname_raw, _, given_raw = raw.partition(",")
        surname_raw = surname_raw.strip()
        given_raw = given_raw.strip()
    else:
        # No explicit separator. Heuristic: the last whitespace-separated
        # token is the surname; everything before is given names. Particle
        # detection happens against the leading portion of the whole string
        # later so 'van der Berg' is handled.
        parts = _WHITESPACE_RE.split(raw)
        if len(parts) == 1:
            surname_raw, given_raw = parts[0], ""
        else:
            # Walk from the end backward and gather tokens that look like
            # surname continuations (capitalized, not a particle on their own).
            # Particles between given names and surname stay with the surname.
            i = len(parts) - 1
            while i > 0:
                preceding_two = " ".join(parts[i - 1 : i + 1]).lower()
                preceding_three = " ".join(parts[i - 2 : i + 1]).lower() if i >= 2 else None
                if preceding_three and any(p == preceding_three.rsplit(" ", 1)[0] for p in _PARTICLES_ORDERED):
                    i -= 2
                    continue
                if any(p == preceding_two.rsplit(" ", 1)[0] for p in _PARTICLES_ORDERED):
                    i -= 1
                    continue
                break
            surname_raw = " ".join(parts[i:])
            given_raw = " ".join(parts[:i])

    # Split surname into particle + main.
    particle_part, main_part = _split_particle(surname_raw)

    # Apply ICAO fold to the main_part (and to given_raw for completeness).
    main_folded, main_subs = _apply_icao_fold(main_part, issuing_state_iso3)
    given_folded, given_subs = _apply_icao_fold(given_raw, issuing_state_iso3)

    # Drop residual diacritics not handled by the issuing-state table.
    surname_main = _strip_diacritics(main_folded).upper().strip()
    given_names_list: Tuple[str, ...] = tuple(
        _strip_diacritics(g).strip().capitalize()
        for g in _WHITESPACE_RE.split(given_folded)
        if g.strip()
    )
    surname_with_particle = (
        f"{particle_part} {main_part}".strip().title() if particle_part else main_part.title()
    )
    initial = given_names_list[0][0] if given_names_list else ""
    normalized_join = " ".join([surname_main, *given_names_list]).strip()

    return NormalizedName(
        surname_main=surname_main,
        surname_with_particle=surname_with_particle,
        given_names=given_names_list,
        initial=initial,
        normalized_join=normalized_join,
        issuing_state_iso3=issuing_state_iso3,
        transliteration_applied=tuple(list(main_subs) + list(given_subs)),
    )
