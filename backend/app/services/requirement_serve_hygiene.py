"""Serve-time hygiene for requirement titles that would mis-educate a relocator.

Catalog rows are often NULL-scoped (apply to everyone) even when the *title* is
written as an instruction to a Non-EEA national. Truncated titles ending in an
ellipsis are stored in the title column (varchar cut at 178) while the full
claim sits in description. Generic “30 days before start” lead-time rows are a
free-movement default and unsafe on a third-country work-pass corridor.

This module is in the serving closure of `rules_engine`. Do not import LLM
clients from here.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

_THIRD_COUNTRY_TITLE_PREFIXES = (
    "non-eea ",
    "non-eu ",
    "non-eu/eea ",
    "non-eu/eea",
)


def display_title(title: Optional[str], description: Optional[str]) -> str:
    """Prefer a complete claim over a title that was cut with an ellipsis."""
    t = (title or "").strip()
    d = (description or "").strip()
    if t.endswith(("…", "...")) and d:
        first = d.split("\n", 1)[0].strip()
        if first:
            return first
    return t


def addressed_to_third_country_only(title: Optional[str]) -> bool:
    """True when the title is an instruction *to* Non-EEA / Non-EU nationals.

    Used so a NULL nationality scope cannot put IRP/permit duties on an EEA
    or own-national checklist. Does not inspect the description — a mixed
    paragraph can mention Non-EEA without being their task list.
    """
    low = (title or "").strip().lower()
    if not low:
        return False
    return any(low.startswith(p) for p in _THIRD_COUNTRY_TITLE_PREFIXES)


def is_generic_thirty_day_lead(item: Dict[str, Any]) -> bool:
    """Catalog filler copied from research.py — not a cited permit runway."""
    title = (item.get("title") or "").strip().lower()
    desc = (item.get("description") or "").strip().lower()
    if title != "minimum lead time":
        return False
    return "at least 30 days before start date" in desc
