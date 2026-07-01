"""Geospatial helpers for recommendations — keyless, no paid dependency.

Straight-line commute estimation + Nominatim geocoding, ported from the
frontend ``RichCommuteMap`` (SPEED table + geocodeAddress). The commute model
is deliberately a cheap straight-line-plus-speed heuristic; the
``commute_minutes`` seam lets a real routing provider (Google Distance Matrix /
Mapbox / OSRM) replace it later without touching callers.
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from typing import Optional, Tuple

Coord = Tuple[float, float]  # (lat, lng)

# Metres per minute — ported verbatim from frontend RichCommuteMap `SPEED`.
SPEED_M_PER_MIN: dict[str, float] = {
    "walking": 75.0,
    "walk": 75.0,
    "bike": 220.0,
    "cycling": 220.0,
    "transit": 380.0,
    "public_transit": 380.0,
    "car": 550.0,
    "driving": 550.0,
    "no_pref": 300.0,
}
_DEFAULT_SPEED = 300.0

# Straight-line distance underestimates real routes (roads/transit detour);
# scale up so the heuristic reads closer to reality. Tunable per the
# commute-accuracy metric in the plan.
DEFAULT_ROAD_FACTOR = 1.3


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two lat/lng points."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def straight_line_commute_minutes(
    office: Optional[Coord],
    area: Optional[Coord],
    mode: str = "transit",
    road_factor: float = DEFAULT_ROAD_FACTOR,
) -> Optional[float]:
    """Estimate commute minutes between two points via distance / mode-speed.

    Returns ``None`` when either point is missing/invalid so callers can fall
    back to a static estimate.
    """
    if not office or not area:
        return None
    try:
        dist = haversine_m(office[0], office[1], area[0], area[1])
    except (TypeError, ValueError):
        return None
    speed = SPEED_M_PER_MIN.get((mode or "").strip().lower(), _DEFAULT_SPEED)
    return (dist / speed) * road_factor


# The provider seam: today the only provider is the straight-line heuristic.
# Swap this to a routing API later without changing plugin callers.
commute_minutes = straight_line_commute_minutes


# ── Nominatim geocoding: process cache + polite rate limit ──────────────────────
_geo_cache: dict[str, Optional[Coord]] = {}
_geo_lock = threading.Lock()
_last_call = [0.0]
_MIN_INTERVAL_S = 1.0  # Nominatim usage policy: <= 1 request/second


def geocode(address: str, *, timeout: float = 8.0) -> Optional[Coord]:
    """Geocode a free-text address to ``(lat, lng)`` via Nominatim (cached).

    Best-effort: returns ``None`` on empty input, no result, or any error.
    """
    key = (address or "").strip()
    if not key:
        return None
    with _geo_lock:
        if key in _geo_cache:
            return _geo_cache[key]
    result: Optional[Coord] = None
    try:
        with _geo_lock:
            wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.monotonic()
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": key, "format": "json", "limit": 1}
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ReloPass/1.0 (housing-recommendations)",
                "Accept-Language": "en",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted host)
            data = json.loads(resp.read().decode("utf-8"))
        if data:
            result = (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        result = None
    with _geo_lock:
        _geo_cache[key] = result
    return result
