"""
Real-business discovery adapter — augments the LLM catalog_scraper (which only
synthesizes plausible names) with grounded results from a maps provider.

Provider is selected by env so it can be swapped without code changes:
  DISCOVERY_PROVIDER = google_places | apify | disabled   (default: disabled)
  GOOGLE_PLACES_API_KEY = ...
  APIFY_API_TOKEN = ...

When disabled (the default) or unconfigured, search_businesses returns [] cleanly
— nothing calls an external service. Discovered rows are imported into the
Supplier Registry (System A) as source='scraper_discovery' with pending
capabilities, so they never reach employees until an admin approves them.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ReloPass service-category slug → maps search keyword.
CATEGORY_KEYWORDS: Dict[str, str] = {
    "movers": "international moving company",
    "living_areas": "furnished apartments corporate housing",
    "legal_admin": "immigration lawyer expats",
    "schools": "international school",
    "banks": "expat bank account",
    "insurance": "expat insurance broker",
    "tax_finance": "expat tax advisor",
    "medical": "english speaking doctor clinic",
    "telecom": "mobile phone provider",
    "childcare": "international daycare nursery",
    "language_integration": "language school",
    "storage": "self storage",
    "transport": "airport transfer service",
    "electricity": "utilities energy provider",
}


def _provider() -> str:
    return (os.getenv("DISCOVERY_PROVIDER") or "disabled").strip().lower()


def provider_status() -> Dict[str, Any]:
    """Read-only indicator for the admin UI — which provider is active and
    whether its key is configured. Never returns the key itself."""
    provider = _provider()
    if provider == "google_places":
        configured = bool(os.getenv("GOOGLE_PLACES_API_KEY"))
    elif provider == "apify":
        configured = bool(os.getenv("APIFY_API_TOKEN"))
    else:
        provider = "disabled"
        configured = False
    return {"provider": provider, "configured": configured}


def _keyword_for(category: str) -> str:
    return CATEGORY_KEYWORDS.get((category or "").strip().lower(), category or "")


def search_businesses(category: str, city: str, country: str) -> List[Dict[str, Any]]:
    """Return real businesses matching a ReloPass category in a city, via the
    configured provider. Returns [] when disabled/unconfigured or on error."""
    provider = _provider()
    if provider == "google_places":
        return _search_google_places(category, city, country)
    if provider == "apify":
        return _search_apify(category, city, country)
    return []


def _search_google_places(category: str, city: str, country: str) -> List[Dict[str, Any]]:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return []
    query = f"{_keyword_for(category)} in {city}, {country}".strip()
    try:
        import requests  # lazy: keep import cost off the disabled path
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": api_key},
            timeout=15,
        )
        data = resp.json() or {}
    except Exception:
        log.exception("google_places discovery failed for %s / %s", category, city)
        return []
    out: List[Dict[str, Any]] = []
    for r in data.get("results", []) or []:
        out.append({
            "name": r.get("name"),
            "website": None,  # Text Search omits website; enrich via Details if needed
            "phone": None,
            "formatted_address": r.get("formatted_address"),
            "rating": r.get("rating"),
            "user_ratings_total": r.get("user_ratings_total"),
            "place_id": r.get("place_id"),
        })
    return out


def _search_apify(category: str, city: str, country: str) -> List[Dict[str, Any]]:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        return []
    query = f"{_keyword_for(category)} in {city}, {country}".strip()
    try:
        import requests
        resp = requests.post(
            "https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items",
            params={"token": token},
            json={"searchStringsArray": [query], "maxCrawledPlacesPerSearch": 20},
            timeout=120,
        )
        items = resp.json() or []
    except Exception:
        log.exception("apify discovery failed for %s / %s", category, city)
        return []
    out: List[Dict[str, Any]] = []
    for r in items if isinstance(items, list) else []:
        out.append({
            "name": r.get("title") or r.get("name"),
            "website": r.get("website"),
            "phone": r.get("phone"),
            "formatted_address": r.get("address"),
            "rating": r.get("totalScore") or r.get("rating"),
            "user_ratings_total": r.get("reviewsCount") or r.get("user_ratings_total"),
            "place_id": r.get("placeId") or r.get("place_id"),
        })
    return out
