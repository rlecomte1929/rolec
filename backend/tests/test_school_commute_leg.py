"""Multi-destination commute: attach a per-mode commute to the nearest school.

Households weigh the office run AND the school run. attach_nearby_schools already
finds the nearest schools; this adds a multimodal (walk/bike/transit/car) leg to
the nearest one on each neighbourhood's metadata.
"""
from __future__ import annotations

from unittest import mock

from backend.app.recommendations import schools_nearby


class _Item:
    def __init__(self, meta):
        self.metadata = meta


class _Resp:
    def __init__(self, items):
        self.recommendations = items


_OSLO_SCHOOL = {"item_id": "s1", "name": "Oslo Intl School", "type": "international",
                "curriculum": "IB", "city": "Oslo", "lat": 59.93, "lng": 10.72}


def _run(meta):
    resp = _Resp([_Item(meta)])
    with mock.patch.object(schools_nearby, "_load_schools", return_value=[_OSLO_SCHOOL]):
        schools_nearby.attach_nearby_schools(resp, "Oslo")
    return meta


def test_school_commute_modes_attached_for_neighbourhood_with_coords():
    meta = _run({"lat": 59.9139, "lng": 10.7522})
    modes = meta.get("school_commute_modes")
    assert modes and {m["mode"] for m in modes} == {"walk", "bike", "transit", "car"}
    assert meta.get("nearest_school_name") == "Oslo Intl School"
    # nearby_schools is still attached (unchanged behaviour).
    assert meta.get("nearby_schools")


def test_no_school_leg_without_neighbourhood_coords():
    meta = _run({})  # no lat/lng
    assert "school_commute_modes" not in meta


def test_no_school_leg_when_no_schools_in_city():
    resp = _Resp([_Item({"lat": 59.9139, "lng": 10.7522})])
    with mock.patch.object(schools_nearby, "_load_schools", return_value=[]):
        schools_nearby.attach_nearby_schools(resp, "Oslo")
    assert "school_commute_modes" not in resp.recommendations[0].metadata
