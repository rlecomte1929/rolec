"""Material-vs-cosmetic source-change diff classifier (P2-02b / AIQ-690).

Part of the source-change monitoring pipeline (parent P2-02). When the crawler
re-ingests a source page, we need to know whether the *rule* changed — a fee,
deadline, requirement, threshold or required form — versus a cosmetic change to
the page's presentation (markup, whitespace, navigation, styling, or a footer
"last updated" timestamp). Only material changes should reach the admin review
queue and, on approval, notify affected cases; cosmetic churn must be silent or
the notification stream becomes noise.

Design notes
  * Pure, deterministic, dependency-free. No DB, no network, no LLM — matching
    the codebase's other deterministic classifiers (policy_assistant_classifier,
    relocation_classifier). This keeps it cheap to run on every crawl diff and
    fully reproducible against the golden fixture.
  * Format-insensitive by construction: both sides are reduced to normalized
    visible-text lines (tags stripped, entities unescaped, whitespace collapsed)
    *before* diffing, so HTML/format-only changes produce no changed lines at all
    — satisfying the technical constraint that the diff "must handle HTML/text
    format changes that don't change the actual rule".

The caller (the change-detection / pipeline glue, a later subtask) supplies the
old and new extracted page text. This module deliberately does not read storage
or the DB itself.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

# Material signal categories, in priority order (first match wins for display).
CATEGORY_FEE = "fee"
CATEGORY_DATE = "date"
CATEGORY_FORM = "form"
CATEGORY_REQUIREMENT = "requirement"
CATEGORY_OTHER = "other"

_MATERIAL_CATEGORIES = frozenset({CATEGORY_FEE, CATEGORY_DATE, CATEGORY_FORM, CATEGORY_REQUIREMENT})

# Currency markers — symbols and ISO-ish codes commonly seen on relocation pages.
_CURRENCY = r"(?:€|£|\$|chf|eur|usd|gbp|sek|nok|dkk|pln|aed)"
_RE_FEE = re.compile(
    r"(?:" + _CURRENCY + r"\s?\d)"            # CHF 100 / €100
    r"|(?:\d[\d.,]*\s?" + _CURRENCY + r")"    # 100 CHF
    r"|(?:\d[\d.,]*\s?%)",                    # 7.7%
    re.IGNORECASE,
)
_FEE_WORDS = ("fee", "cost", "price", "charge", "tariff", "salary", "income", "amount", "tax")

# Durations / deadlines / explicit dates.
_RE_DURATION = re.compile(
    r"\b\d+\s?(?:day|days|week|weeks|month|months|year|years|business day|working day)\b",
    re.IGNORECASE,
)
_RE_DATE = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})\b",
    re.IGNORECASE,
)
_DATE_WORDS = ("deadline", "within", "no later than", "valid until", "expires", "by the")

# Requirement / eligibility language.
_REQUIREMENT_WORDS = (
    "must", "shall", "required", "require", "mandatory", "obliged", "obligation",
    "eligible", "eligibility", "minimum", "maximum", "at least", "no later than",
    "permit", "visa", "threshold", "qualify", "qualifying", "prerequisite",
    "condition", "not permitted", "prohibited",
)

# Forms / annexes / official document references.
_RE_FORM = re.compile(r"\b(?:form|annex|appendix|schedule)\b\s*[\w./-]*", re.IGNORECASE)

# Lines that are boilerplate timestamps / legal footers — never material even
# though they may contain dates or numbers.
_RE_BOILERPLATE = re.compile(
    r"(?:last\s+(?:updated|reviewed|modified|revised)"
    r"|page\s+updated"
    r"|©|copyright|all rights reserved"
    r"|cookie|privacy policy|terms of use)",
    re.IGNORECASE,
)

_RE_SCRIPT_STYLE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_RE_TAG = re.compile(r"<[^>]+>")


@dataclass
class ChangedSection:
    """One changed line of visible text and why it matters."""

    kind: str          # "added" | "removed"
    category: str      # fee | date | form | requirement | other
    text: str

    def to_dict(self) -> Dict[str, str]:
        return {"kind": self.kind, "category": self.category, "text": self.text}


@dataclass
class DiffClassification:
    """Result of comparing old vs new page text."""

    is_material: bool
    changed_sections: List[ChangedSection] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "is_material": self.is_material,
            "changed_sections": [s.to_dict() for s in self.changed_sections],
        }


def _visible_lines(text: str) -> List[Tuple[str, str]]:
    """Reduce raw page text/HTML to normalized visible-text segments.

    Returns a list of (key, display) pairs where ``key`` is a lowercased
    comparison key and ``display`` preserves the original casing for
    human-readable change snippets. Empty segments are dropped.

    Whitespace (including source-level newlines) is collapsed *before* tags are
    turned into segment breaks. This makes segmentation depend only on the
    document's block structure — not on where the source happens to wrap lines —
    so pure whitespace/markup reflow yields identical segments (a cosmetic, not
    material, change) while genuine block boundaries (nav vs paragraph) stay
    separate.
    """
    if not text:
        return []
    text = html.unescape(text)
    text = _RE_SCRIPT_STYLE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)   # collapse ALL whitespace first (kills reflow)
    text = _RE_TAG.sub("\n", text)     # then block tags become segment breaks
    out: List[Tuple[str, str]] = []
    for raw in text.split("\n"):
        display = raw.strip()
        if display:
            out.append((display.lower(), display))
    return out


def _classify_line(line: str) -> str:
    """Return the material category for a changed line, or CATEGORY_OTHER."""
    low = line.lower()
    if _RE_BOILERPLATE.search(low):
        return CATEGORY_OTHER
    # Fee words alone (e.g. "tax") are weak; require a digit nearby or a
    # currency/percent marker to call it a fee change.
    if _RE_FEE.search(low) or (any(w in low for w in _FEE_WORDS) and re.search(r"\d", low)):
        return CATEGORY_FEE
    if _RE_DURATION.search(low) or _RE_DATE.search(low) or any(w in low for w in _DATE_WORDS):
        return CATEGORY_DATE
    if _RE_FORM.search(low):
        return CATEGORY_FORM
    if any(w in low for w in _REQUIREMENT_WORDS):
        return CATEGORY_REQUIREMENT
    return CATEGORY_OTHER


def classify_diff(old_text: str, new_text: str) -> DiffClassification:
    """Compare old vs new source-page text and classify the change.

    A change is *material* when at least one added or removed line of visible
    text carries a fee, date/deadline, form, or requirement signal. Pure markup,
    whitespace, navigation, styling, and footer-timestamp changes reduce to no
    changed visible lines (or only CATEGORY_OTHER lines) and are *cosmetic*.
    """
    old_lines = _visible_lines(old_text)
    new_lines = _visible_lines(new_text)
    old_keys = [k for k, _ in old_lines]
    new_keys = [k for k, _ in new_lines]

    sections: List[ChangedSection] = []
    matcher = SequenceMatcher(None, old_keys, new_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            for _, display in old_lines[i1:i2]:
                sections.append(ChangedSection("removed", _classify_line(display), display))
        if tag in ("replace", "insert"):
            for _, display in new_lines[j1:j2]:
                sections.append(ChangedSection("added", _classify_line(display), display))

    is_material = any(s.category in _MATERIAL_CATEGORIES for s in sections)
    return DiffClassification(is_material=is_material, changed_sections=sections)
