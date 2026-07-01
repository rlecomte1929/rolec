"""Phase 1: real commute for living-areas recommendations.

Covers the pure geo math, the score() real-vs-fallback commute path, and the
100% geo-completeness gate for the neighborhoods dataset.
"""
import json
from pathlib import Path

from backend.app.recommendations import geo
from backend.app.recommendations.plugins.living_areas import (
    LivingAreasCriteria,
    LivingAreasPlugin,
    DATASET_PATH,
)


def test_haversine_known_distance():
    # Singapore CBD to Changi Airport ~17-18 km.
    d = geo.haversine_m(1.2830, 103.8510, 1.3644, 103.9915)
    assert 16_000 < d < 19_000


def test_straight_line_commute_minutes_basic():
    office = (1.2830, 103.8510)
    assert geo.straight_line_commute_minutes(office, office, "transit") == 0.0
    near = geo.straight_line_commute_minutes(office, (1.30, 103.85), "transit")
    far = geo.straight_line_commute_minutes(office, (1.42, 103.85), "transit")
    assert near is not None and far is not None and far > near > 0
    # walking is slower than car for the same distance
    assert geo.straight_line_commute_minutes(office, (1.35, 103.90), "walking") > \
        geo.straight_line_commute_minutes(office, (1.35, 103.90), "car")


def test_commute_minutes_none_on_missing_point():
    assert geo.straight_line_commute_minutes(None, (1.0, 103.0)) is None
    assert geo.straight_line_commute_minutes((1.0, 103.0), None) is None


def _item(**over):
    base = {
        "item_id": "t1", "name": "Test Area", "city": "Singapore",
        "avg_rent_2br": 3000, "avg_rent_3br": 4000, "typical_sqm_range": [70, 100],
        "commute_to_work_minutes_estimate": 18, "tags": {"safety": 8, "nightlife": 5, "quiet": 7, "green": 7},
        "rating": 4.2, "availability_level": "medium",
    }
    base.update(over)
    return base


def test_score_falls_back_to_static_estimate_without_coords():
    plugin = LivingAreasPlugin()
    crit = LivingAreasCriteria(destination_city="Singapore")  # no office coords
    out = plugin.score(crit, _item())  # item has no lat/lng
    assert "~18 min commute" in out["summary"]


def test_score_uses_real_commute_when_coords_present():
    plugin = LivingAreasPlugin()
    office = {"office_lat": 1.2830, "office_lng": 103.8510}
    near = plugin.score(
        LivingAreasCriteria(destination_city="Singapore", **office),
        _item(lat=1.30, lng=103.85, commute_to_work_minutes_estimate=99),  # static value must be ignored
    )
    far = plugin.score(
        LivingAreasCriteria(destination_city="Singapore", **office),
        _item(lat=1.45, lng=103.99, commute_to_work_minutes_estimate=1),
    )
    # Real geo overrides the (deliberately wrong) static estimate:
    assert "~99 min" not in near["summary"] and "~1 min" not in far["summary"]
    # Nearer neighborhood scores commute higher than the far one.
    assert near["breakdown"]["commute"] > far["breakdown"]["commute"]
    # Coords are surfaced for the map.
    assert near["metadata"]["lat"] == 1.30 and near["metadata"]["lng"] == 103.85


def test_neighborhoods_dataset_100pct_geocoded():
    rows = json.loads(Path(DATASET_PATH).read_text(encoding="utf-8"))
    missing = [r.get("name") for r in rows
               if not (isinstance(r.get("lat"), (int, float)) and isinstance(r.get("lng"), (int, float)))]
    assert not missing, f"neighborhoods missing coords: {missing}"
