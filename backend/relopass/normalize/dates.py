"""Date normalization to ISO 8601 — C1-06.

4-rule precedence per Architecture Report §3.4:

  1. ISO format detected (YYYY-MM-DD or YYYY/MM/DD) → use as-is, confidence 0.99
  2. MRZ YYMMDD with century inference → confidence 0.95
  3. Locale of document (FR/NO/DE: DD/MM/YYYY; US: MM/DD/YYYY) → 0.85
  4. Freeform via dateparser with locale hint → 0.70 .. 0.85

Ambiguous inputs (e.g. 03/04/2025 with no locale_hint) get confidence ≤ 0.6
and emit a LocaleHintSuggestion finding so the caller can prompt the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

try:  # dateparser is in requirements.txt; the try/except guards the test envs
    import dateparser  # type: ignore[import-not-found]
except Exception:  # pragma: no cover — pip install dateparser
    dateparser = None  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────────────
# Findings
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LocaleHintSuggestion:
    """Emitted when the input could be parsed by either FR/DE/NO (DMY) or
    US (MDY) conventions. The caller should resolve by asking the user or
    looking at the issuing-state metadata."""
    code: str = "AMBIGUOUS_DMY_MDY"
    detail: str = ""
    candidates: Tuple[str, ...] = field(default_factory=tuple)


# ─────────────────────────────────────────────────────────────────────────────
# Public type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedDate:
    """Canonical parse output. `iso` is None when parsing fails entirely."""
    iso: Optional[str]
    confidence: float
    rule_used: str  # 'iso' | 'mrz' | 'locale_dmy' | 'locale_mdy' | 'freeform' | 'ambiguous_no_hint' | 'unparseable'
    findings: Tuple[LocaleHintSuggestion, ...] = field(default_factory=tuple)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 1 — ISO
# ─────────────────────────────────────────────────────────────────────────────

_ISO_RE = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$")


def _try_iso(text: str) -> Optional[date]:
    m = _ISO_RE.match(text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — MRZ YYMMDD
# ─────────────────────────────────────────────────────────────────────────────

_MRZ_RE = re.compile(r"^\s*(\d{2})(\d{2})(\d{2})\s*$")


def _try_mrz(text: str, *, century_pivot: int = 50) -> Optional[date]:
    m = _MRZ_RE.match(text)
    if not m:
        return None
    yy, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 2000 + yy if yy < century_pivot else 1900 + yy
    try:
        return date(year, mo, d)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3 — locale-aware DD/MM/YYYY vs MM/DD/YYYY
# ─────────────────────────────────────────────────────────────────────────────

_SLASH_RE = re.compile(r"^\s*(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})\s*$")

# Locales we hint via the locale_hint parameter. Matches the corridors in scope.
_LOCALES_DMY = {"FR", "DE", "NO", "SE", "DK", "FI", "IS", "NL", "BE", "IT", "ES", "AT", "CH", "PT", "GB", "UK", "IN"}
_LOCALES_MDY = {"US", "CA"}


def _try_locale(text: str, locale_hint: Optional[str]) -> Tuple[Optional[date], str]:
    """Returns (date, rule_label). rule_label tells the caller which path applied."""
    m = _SLASH_RE.match(text)
    if not m:
        return None, ""
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y = 2000 + y if y < 50 else 1900 + y
    hint = (locale_hint or "").upper().strip()
    if hint in _LOCALES_DMY:
        try:
            return date(y, b, a), "locale_dmy"
        except ValueError:
            return None, "locale_dmy"
    if hint in _LOCALES_MDY:
        try:
            return date(y, a, b), "locale_mdy"
        except ValueError:
            return None, "locale_mdy"
    return None, ""


def _try_ambiguous(text: str) -> Tuple[Optional[date], Optional[date]]:
    """When no hint is provided, attempt BOTH DMY and MDY interpretations.
    Returns (dmy_candidate, mdy_candidate); either may be None.

    If both parse and differ → ambiguous → caller emits LocaleHintSuggestion.
    If both parse and agree   → unambiguous (e.g. 13/04/2025 only fits DMY).
    """
    m = _SLASH_RE.match(text)
    if not m:
        return None, None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y = 2000 + y if y < 50 else 1900 + y
    dmy: Optional[date]
    mdy: Optional[date]
    try:
        dmy = date(y, b, a)
    except ValueError:
        dmy = None
    try:
        mdy = date(y, a, b)
    except ValueError:
        mdy = None
    return dmy, mdy


# ─────────────────────────────────────────────────────────────────────────────
# Rule 4 — freeform via dateparser
# ─────────────────────────────────────────────────────────────────────────────


def _try_freeform(text: str, locale_hint: Optional[str]) -> Optional[date]:
    if dateparser is None:
        return None
    settings = {"PREFER_DAY_OF_MONTH": "first", "RETURN_AS_TIMEZONE_AWARE": False}
    languages: Optional[List[str]] = None
    hint = (locale_hint or "").upper().strip()
    if hint == "FR":
        languages = ["fr"]
        settings["DATE_ORDER"] = "DMY"
    elif hint == "DE":
        languages = ["de"]
        settings["DATE_ORDER"] = "DMY"
    elif hint == "NO":
        languages = ["no"]
        settings["DATE_ORDER"] = "DMY"
    elif hint in _LOCALES_DMY:
        settings["DATE_ORDER"] = "DMY"
    elif hint in _LOCALES_MDY:
        settings["DATE_ORDER"] = "MDY"

    try:
        dt = dateparser.parse(text, languages=languages, settings=settings)
    except Exception:
        return None
    return dt.date() if dt else None


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def parse_date(text: str, locale_hint: Optional[str] = None) -> ParsedDate:
    """Apply the 4-rule precedence and return a structured result.

    `locale_hint` is an ISO 3166-1 alpha-2 country code (e.g. 'FR', 'US') —
    typically the document's issuing state or the user's profile locale.
    """
    if text is None:
        return ParsedDate(iso=None, confidence=0.0, rule_used="unparseable")
    s = text.strip()
    if not s:
        return ParsedDate(iso=None, confidence=0.0, rule_used="unparseable")

    # Rule 1 — ISO
    iso_match = _try_iso(s)
    if iso_match:
        return ParsedDate(iso=iso_match.isoformat(), confidence=0.99, rule_used="iso")

    # Rule 2 — MRZ
    mrz_match = _try_mrz(s)
    if mrz_match:
        return ParsedDate(iso=mrz_match.isoformat(), confidence=0.95, rule_used="mrz")

    # Rule 3 — locale-aware DD/MM vs MM/DD
    if locale_hint:
        loc, rule = _try_locale(s, locale_hint)
        if loc:
            return ParsedDate(iso=loc.isoformat(), confidence=0.85, rule_used=rule)

    # Rule 3b — no hint: detect ambiguity
    dmy, mdy = _try_ambiguous(s)
    if dmy and mdy and dmy != mdy:
        finding = LocaleHintSuggestion(
            detail="Date is ambiguous between DD/MM and MM/DD; pass locale_hint=FR/DE/NO/US to disambiguate.",
            candidates=(dmy.isoformat(), mdy.isoformat()),
        )
        return ParsedDate(
            iso=None,
            confidence=0.5,
            rule_used="ambiguous_no_hint",
            findings=(finding,),
        )
    if dmy and mdy and dmy == mdy:
        # Same date under both interpretations — unambiguous.
        return ParsedDate(iso=dmy.isoformat(), confidence=0.85, rule_used="locale_dmy")
    if dmy and not mdy:
        return ParsedDate(iso=dmy.isoformat(), confidence=0.85, rule_used="locale_dmy")
    if mdy and not dmy:
        return ParsedDate(iso=mdy.isoformat(), confidence=0.85, rule_used="locale_mdy")

    # Rule 4 — freeform
    ff = _try_freeform(s, locale_hint)
    if ff:
        confidence = 0.85 if locale_hint else 0.70
        return ParsedDate(iso=ff.isoformat(), confidence=confidence, rule_used="freeform")

    return ParsedDate(iso=None, confidence=0.0, rule_used="unparseable")
