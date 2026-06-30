# WS-D — prove the weights externalization (recommendations/weights.py) is a
# pure refactor: every plugin's score_raw must stay byte-identical to the frozen
# pre-refactor baseline, and the request-supplied criteria.weights override must
# still take precedence over the externalized fallback.
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.recommendations.registry import get_plugin
from backend.app.recommendations.weights import WEIGHTS

BASELINE = (
    Path(__file__).resolve().parent / "fixtures" / "weight_refactor_baseline.json"
)


def _load_baseline():
    with BASELINE.open(encoding="utf-8") as f:
        return json.load(f)["categories"]


def test_weights_unchanged_byte_identical_scores():
    """score_raw for every (category, item) matches the pre-refactor baseline."""
    baseline = _load_baseline()
    checked = 0
    for category, payload in baseline.items():
        plugin = get_plugin(category)
        assert plugin is not None, f"missing plugin for {category}"
        criteria_obj = plugin.validate_and_parse(payload["criteria"])
        by_id = {it.get("item_id"): it for it in plugin.load_dataset()}
        for row in payload["scores"]:
            item = by_id[row["item_id"]]
            current = round(float(plugin.score(criteria_obj, item).get("score_raw") or 0.0), 6)
            assert current == row["score_raw"], (
                f"{category}/{row['item_id']}: {current} != baseline {row['score_raw']}"
            )
            checked += 1
    assert checked >= 100  # sanity: the whole corpus actually ran


def test_weights_sum_to_one():
    """Each category's externalized weights form a convex blend (sum == 1.0)."""
    for category, weights in WEIGHTS.items():
        assert abs(sum(weights.values()) - 1.0) < 1e-9, f"{category} weights sum != 1.0"


def test_movers_request_weights_override_still_applied():
    """criteria.weights overrides the externalized fallback (movers)."""
    plugin = get_plugin("movers")
    item = plugin.load_dataset()[0]
    base_criteria = {
        "origin_city": "Singapore",
        "destination_city": "Tokyo",
        "move_type": "international",
        "current_accommodation": {"type": "apartment", "bedrooms": 2, "sqm": 80},
        "people": 2,
    }
    default_score = plugin.score(
        plugin.validate_and_parse(base_criteria), item
    )["score_raw"]
    # A lopsided override must produce a different score than the fallback blend.
    overridden = dict(base_criteria, weights={"cost": 1.0, "speed": 0.0, "reliability": 0.0,
                                              "services": 0.0, "rating": 0.0, "availability": 0.0})
    override_score = plugin.score(
        plugin.validate_and_parse(overridden), item
    )["score_raw"]
    assert override_score != default_score
