"""AIQ-2119: the neighbourhood advisor must actually rank by commute.

`commute` carries the joint-largest weight (0.25, tied with budget), and the card's whole
premise is "rank Dublin areas by commute + family + budget". But the component was scored as a
PASS/FAIL against `max_minutes`, so every area inside the limit got a flat 100 and the weight
contributed exactly zero differentiation. Measured on the card's own scenario (Grand Canal Dock
office, transit, 40-min cap) the office's own neighbourhood ranked FOURTH, behind an area 30
minutes away, and the whole eight-area spread was 1.35 points.

These assert the gradient, not merely "the order changed" — an order-changed test goes green
over the defect, because the order does shift once `max_minutes` starts excluding distant areas.
See docs/plans/AIQ-2119_neighbourhood_advisor_plan_2026-08-23.md.
"""
from backend.app.recommendations.plugins.living_areas import (
    LivingAreasCriteria,
    LivingAreasPlugin,
)

# Two areas identical in every scored dimension except distance from the office, so any
# difference in the final score is attributable to commute alone.
_BASE = {
    "city": "Dublin",
    "avg_rent_2br": 2600,
    "avg_rent_3br": 3400,
    "typical_sqm_range": [70, 100],
    "tags": {"safety": 8, "nightlife": 6, "quiet": 7, "green": 7},
    "rating": 4.2,
    "availability_level": "medium",
}

# Dublin city centre; the second point is ~8km north, a materially longer commute.
_OFFICE = {"office_lat": 53.3417, "office_lng": -6.2350}


def _area(item_id: str, lat: float, lng: float, **over):
    return {**_BASE, "item_id": item_id, "name": item_id, "lat": lat, "lng": lng, **over}


def _crit(**over):
    base = {
        "destination_city": "Dublin",
        "commute_work": {"mode": "transit", "max_minutes": 40},
        **_OFFICE,
    }
    base.update(over)
    return LivingAreasCriteria(**base)


def test_commute_subscore_differs_between_near_and_far():
    """The core defect: both scored a flat 100.0 because both were inside max_minutes."""
    plugin = LivingAreasPlugin()
    crit = _crit()
    at_office = plugin.score(crit, _area("at-office", 53.3417, -6.2350))
    far = plugin.score(crit, _area("far", 53.4150, -6.2350))

    near_commute = at_office["breakdown"]["commute"]
    far_commute = far["breakdown"]["commute"]
    assert near_commute > far_commute, (
        f"commute must be a gradient, not pass/fail: at-office={near_commute} far={far_commute}"
    )


def test_area_at_the_office_outranks_a_comparable_distant_one():
    plugin = LivingAreasPlugin()
    crit = _crit()
    at_office = plugin.score(crit, _area("at-office", 53.3417, -6.2350))
    far = plugin.score(crit, _area("far", 53.4150, -6.2350))
    assert at_office["score_raw"] > far["score_raw"], (
        f"0-minute area must beat a distant identical one: "
        f"{at_office['score_raw']} vs {far['score_raw']}"
    )


def test_commute_beyond_the_stated_limit_scores_zero():
    """The employee said 40 minutes was the cap; a gradient must not quietly readmit 90.

    NOTE this is a deliberate behaviour CHANGE, not a preservation. The plan doc calls it
    "the existing hard exclusion", but there was none: the old line degraded linearly
    (100 - 3*overage), so an area 60 min from a 40-min cap still scored 40.
    """
    plugin = LivingAreasPlugin()
    crit = _crit()
    way_out = plugin.score(crit, _area("way-out", 54.1000, -6.2350))
    assert way_out["breakdown"]["commute"] == 0.0


def test_the_top_area_changes_when_the_office_moves():
    """Stricter than "the list changed": the WINNER must change."""
    plugin = LivingAreasPlugin()
    south = _area("south", 53.3244, -6.2550)
    north = _area("north", 53.3695, -6.2550)

    at_south = _crit(office_lat=53.3244, office_lng=-6.2550)
    at_north = _crit(office_lat=53.3695, office_lng=-6.2550)

    def winner(crit):
        scored = [(plugin.score(crit, a)["score_raw"], a["item_id"]) for a in (south, north)]
        return max(scored)[1]

    assert winner(at_south) == "south"
    assert winner(at_north) == "north"
