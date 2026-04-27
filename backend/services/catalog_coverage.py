"""
Recommendations catalog coverage utilities.

Two pieces, both small:
1) report_coverage(destination_city) — read-only inspection: per category,
   how many items exist for the given city. Used by the CLI in
   scripts/recommendations_coverage.py and by the auto-backfill hook.
2) ensure_destination_catalog(category, destination_city, country=None) —
   called from case-creation paths when a new case lands in a destination.
   Today: emits a structured log so we have a metric stream to drive the
   scraper work later. Tomorrow: dispatches a per-category scraper that
   writes up to MAX_ITEMS_PER_DESTINATION items into the catalog and
   quality-scores them from user signals (shortlist / exception / click).

Design (per the conversation):
- First user in a new (category, city) pair triggers a lazy backfill.
- Cap at 10 items per category per city — keeps the curation surface
  small enough for HR / ops to manually vet.
- Quality is implicit: items shortlisted by employees and accepted in
  HR exception decisions earn signal; never-shortlisted items decay.

Implementation note: we read each plugin's dataset directly (rather than
calling the full scoring pipeline) because (a) it's deterministic and
free of criteria-defaulting accidents, and (b) every plugin already
ships a load_dataset() method. Datasets that include a `city` field
are filtered; geo-agnostic datasets count all items.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..app.recommendations.registry import get_plugin, list_categories

log = logging.getLogger(__name__)

MAX_ITEMS_PER_DESTINATION = 10

# Aliases mapped to the same canonical city the schools/living_areas plugins
# already use, so coverage reports for "Germany" or "münchen" land in the
# same bucket as "Munich".
_CITY_ALIAS = {
    "munich": "Munich",
    "münchen": "Munich",
    "germany": "Munich",
    "de": "Munich",
    "singapore": "Singapore",
    "sg": "Singapore",
    "oslo": "Oslo",
    "norway": "Oslo",
    "no": "Oslo",
    "new york": "New York",
    "new york city": "New York",
    "nyc": "New York",
    "ny": "New York",
    "san francisco": "San Francisco",
    "sf": "San Francisco",
}


def _canonical_city(raw: Optional[str]) -> str:
    if not raw:
        return ""
    cleaned = raw.split(",")[0].strip()
    return _CITY_ALIAS.get(cleaned.lower(), cleaned)


def report_coverage(destination_city: str) -> Dict[str, Dict[str, object]]:
    """
    For every registered recommendations category, report how many catalog
    rows exist for the given city. Geo-agnostic datasets (no `city` field
    on rows) count all rows.

    Returns:
        { category_key: { "title": str, "items": int, "geo_bound": bool } }
    """
    target_city = _canonical_city(destination_city)
    out: Dict[str, Dict[str, object]] = {}
    for cat in list_categories():
        key = cat["key"]
        title = cat.get("title", key)
        plugin = get_plugin(key)
        if plugin is None:
            out[key] = {"title": title, "items": 0, "geo_bound": False, "error": "no plugin"}
            continue
        try:
            rows = plugin.load_dataset() or []
        except Exception as ex:  # pragma: no cover — defensive
            out[key] = {"title": title, "items": 0, "geo_bound": False, "error": str(ex)}
            continue
        rows_with_city = [r for r in rows if isinstance(r, dict) and r.get("city")]
        geo_bound = len(rows_with_city) > 0
        if geo_bound:
            count = sum(1 for r in rows_with_city if r.get("city") == target_city)
        else:
            count = len(rows)
        out[key] = {"title": title, "items": count, "geo_bound": geo_bound}
    return out


def ensure_destination_catalog(
    category: str,
    destination_city: str,
    country: Optional[str] = None,
) -> Dict[str, object]:
    """
    Lazy-backfill hook. Called from case-creation paths. Today: emits a
    structured log so we can measure the gap rate before building the
    scrapers. Returns a small status dict so callers can decide whether
    to surface "data coming soon" to the user.
    """
    coverage = report_coverage(destination_city)
    cat = coverage.get(category)
    have = int(cat.get("items", 0)) if cat and isinstance(cat.get("items"), int) else 0
    needed = max(0, MAX_ITEMS_PER_DESTINATION - have)

    if needed > 0:
        # TODO(scraper): dispatch a per-category scraper that writes up to
        # MAX_ITEMS_PER_DESTINATION items into a DB-backed catalog. For
        # now we emit a structured log so we can rank which (category,
        # city) pairs to build scrapers for first based on real demand.
        log.info(
            "catalog_gap_detected category=%s destination_city=%s country=%s have=%d needed=%d",
            category,
            destination_city,
            country or "",
            have,
            needed,
        )

    return {
        "category": category,
        "destination_city": destination_city,
        "country": country,
        "have": have,
        "needed": needed,
        "scraper_dispatched": False,
    }


def categories_with_gaps(destination_city: str) -> List[str]:
    """Convenience: list category keys that would benefit from a backfill."""
    coverage = report_coverage(destination_city)
    return [
        key
        for key, data in coverage.items()
        if isinstance(data.get("items"), int) and (data.get("items") or 0) < MAX_ITEMS_PER_DESTINATION
    ]
