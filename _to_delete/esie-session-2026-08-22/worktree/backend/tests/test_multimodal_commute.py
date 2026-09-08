"""Multimodal commute core (PR5) — per-mode time + cost + carbon, keyless.

Built on the existing haversine + speed heuristic (no routing sub-processor). A
live routing/isochrone API would be a new DPA sub-processor — deliberately out of
scope; the commute_minutes seam lets one swap in later.
"""
from __future__ import annotations

from backend.app.recommendations import geo
from backend.app.recommendations.plugins.living_areas import (
    LivingAreasCriteria,
    LivingAreasPlugin,
)

OFFICE = (59.9139, 10.7522)   # Oslo centre
AREA = (59.9276, 10.7167)     # a few km away


def test_mode_profile_has_time_cost_carbon():
    p = geo.mode_profile(OFFICE, AREA, "car")
    assert p["mode"] == "car"
    assert p["minutes"] > 0 and p["distance_km"] > 0
    assert p["cost"] > 0 and p["carbon_g"] > 0


def test_walk_and_bike_are_zero_cost_zero_carbon():
    walk = geo.mode_profile(OFFICE, AREA, "walk")
    bike = geo.mode_profile(OFFICE, AREA, "bike")
    assert walk["cost"] == 0 and walk["carbon_g"] == 0
    assert bike["cost"] == 0 and bike["carbon_g"] == 0
    # Walking is slower than biking for the same leg.
    assert walk["minutes"] > bike["minutes"]


def test_car_emits_more_carbon_than_transit():
    car = geo.mode_profile(OFFICE, AREA, "car")
    transit = geo.mode_profile(OFFICE, AREA, "transit")
    assert car["carbon_g"] > transit["carbon_g"]


def test_multimodal_returns_all_four_modes():
    modes = geo.multimodal_commute(OFFICE, AREA)
    assert {m["mode"] for m in modes} == {"walk", "bike", "transit", "car"}


def test_mode_profile_none_without_coords():
    assert geo.mode_profile(None, AREA, "car") is None
    assert geo.multimodal_commute(OFFICE, None) == []


def test_scorer_attaches_commute_modes_when_coords_present():
    plugin = LivingAreasPlugin()
    crit = LivingAreasCriteria(destination_city="Oslo", office_lat=OFFICE[0], office_lng=OFFICE[1])
    item = {"item_id": "la-o1", "name": "Frogner", "city": "Oslo", "avg_rent_2br": 25000,
            "typical_sqm_range": [70, 100], "tags": {"safety": 8}, "rating": 4.4,
            "availability_level": "high", "lat": AREA[0], "lng": AREA[1]}
    out = plugin.score(crit, item)
    modes = out["metadata"]["commute_modes"]
    assert {m["mode"] for m in modes} == {"walk", "bike", "transit", "car"}


def test_scorer_no_commute_modes_without_office_coords():
    plugin = LivingAreasPlugin()
    crit = LivingAreasCriteria(destination_city="Oslo")  # no office coords
    item = {"item_id": "la-o1", "name": "Frogner", "city": "Oslo", "avg_rent_2br": 25000,
            "tags": {}, "rating": 4.0, "availability_level": "high", "lat": AREA[0], "lng": AREA[1]}
    out = plugin.score(crit, item)
    assert out["metadata"]["commute_modes"] == []
