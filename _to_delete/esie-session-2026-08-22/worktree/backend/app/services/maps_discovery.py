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

from ..config.vendor_discovery import SERVICE_CATEGORY_SEARCH_TERMS, VENDOR_QUALITY_THRESHOLDS

log = logging.getLogger(__name__)

# Registry service-category slugs → VEN-01 config keys where they differ
# (the config uses "housing"; the supplier registry slug is "living_areas").
_CATEGORY_ALIASES = {"living_areas": "housing"}


def _build_query(category: str, city: str) -> str:
    """Search query for a (category, city), sourced from the VEN-01 config
    search-term templates. Resolves registry slugs → config keys; falls back to a
    bare '{city} {category}' query for unknown categories."""
    slug = (category or "").strip().lower()
    key = _CATEGORY_ALIASES.get(slug, slug)
    templates = SERVICE_CATEGORY_SEARCH_TERMS.get(key) or ["{city} " + (category or "")]
    return templates[0].format(city=city)


def _provider() -> str:
    return (os.getenv("DISCOVERY_PROVIDER") or "disabled").strip().lower()


_DEFAULT_MAX_RESULTS = VENDOR_QUALITY_THRESHOLDS["max_candidates_to_fetch"]


def _max_results() -> int:
    """Hard per-search result cap (cost guardrail). Env-tunable, low default."""
    try:
        n = int(os.getenv("DISCOVERY_MAX_RESULTS", str(_DEFAULT_MAX_RESULTS)))
    except (TypeError, ValueError):
        n = _DEFAULT_MAX_RESULTS
    return max(1, min(n, 60))


def provider_status() -> Dict[str, Any]:
    """Read-only indicator for the admin UI — which provider is active, whether its
    key is configured, and the per-search result cap. Never returns the key itself."""
    provider = _provider()
    if provider == "google_places":
        configured = bool(os.getenv("GOOGLE_PLACES_API_KEY"))
    elif provider == "apify":
        configured = bool(os.getenv("APIFY_API_TOKEN"))
    else:
        provider = "disabled"
        configured = False
    return {"provider": provider, "configured": configured, "max_results": _max_results()}


def search_businesses(
    category: str, city: str, country: str, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return real businesses matching a ReloPass category in a city, via the
    configured provider. Results are capped at min(limit, DISCOVERY_MAX_RESULTS) to
    bound per-search cost. Returns [] when disabled/unconfigured or on error."""
    cap = _max_results() if limit is None else max(1, min(limit, _max_results()))
    provider = _provider()
    if provider == "google_places":
        return _search_google_places(category, city, country, cap)
    if provider == "apify":
        return _search_apify(category, city, country, cap)
    return []


# Google Places API (New, v1) — Text Search. Returns websiteUri in one call.
_PLACES_V1_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_PLACES_V1_DETAIL_URL = "https://places.googleapis.com/v1/places/{place_id}"
_PLACES_V1_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
    "places.websiteUri,places.rating,places.userRatingCount,places.businessStatus"
)


def _search_google_places(category: str, city: str, country: str, cap: int) -> List[Dict[str, Any]]:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return []
    try:
        import requests  # lazy: keep import cost off the disabled path
        resp = requests.post(
            _PLACES_V1_SEARCH_URL,
            json={
                "textQuery": _build_query(category, city),
                "maxResultCount": min(cap, 20),  # v1 hard limit is 20
                "languageCode": "en",
            },
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": _PLACES_V1_FIELD_MASK,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception:
        log.exception("google_places discovery failed for %s / %s", category, city)
        return []
    out: List[Dict[str, Any]] = []
    for p in (data.get("places", []) or [])[:cap]:
        out.append({
            "name": (p.get("displayName") or {}).get("text"),
            "website": p.get("websiteUri"),
            "phone": p.get("nationalPhoneNumber"),
            "formatted_address": p.get("formattedAddress"),
            "rating": p.get("rating"),
            "user_ratings_total": p.get("userRatingCount"),
            "business_status": p.get("businessStatus"),
            "place_id": p.get("id"),
        })
    return out


def refresh_vendor_by_place_id(place_id: str) -> Optional[Dict[str, Any]]:
    """Re-fetch a single vendor's live signals by its stable Google place_id
    (used by the freshness refresh job). Returns None when disabled or on error."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key or not place_id:
        return None
    try:
        import requests
        resp = requests.get(
            _PLACES_V1_DETAIL_URL.format(place_id=place_id),
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "id,rating,userRatingCount,businessStatus",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception:
        log.warning("google_places refresh failed for place_id=%s", place_id)
        return None
    return {
        "place_id": data.get("id"),
        "rating": data.get("rating"),
        "user_ratings_total": data.get("userRatingCount"),
        "business_status": data.get("businessStatus"),
    }


def _search_apify(category: str, city: str, country: str, cap: int) -> List[Dict[str, Any]]:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        return []
    query = _build_query(category, city)
    try:
        import requests
        resp = requests.post(
            "https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items",
            params={"token": token},
            json={"searchStringsArray": [query], "maxCrawledPlacesPerSearch": cap},
            timeout=120,
        )
        items = resp.json() or []
    except Exception:
        log.exception("apify discovery failed for %s / %s", category, city)
        return []
    out: List[Dict[str, Any]] = []
    for r in (items[:cap] if isinstance(items, list) else []):
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
