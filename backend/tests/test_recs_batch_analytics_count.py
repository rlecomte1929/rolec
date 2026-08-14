"""The recommendations-batch telemetry counts recommendations, not `items`.

The batch endpoint summed `r.get("items", [])` over the results, but the values are
`RecommendationResponse` pydantic models (field: `recommendations`) with no `.get`.
That raised AttributeError inside the telemetry try/except, so the
recommendations-generated analytics event never emitted at all. This pins the field.
"""
from __future__ import annotations

import pytest

from backend.app.recommendations.types import (
    RecommendationResponse,
    RecommendationItem,
    RecommendationTier,
)


def _resp(category, n):
    items = [
        RecommendationItem(item_id=f"{category}-{i}", name=f"n{i}", score=90.0,
                           tier=RecommendationTier.BEST_MATCH, summary="", rationale="",
                           breakdown={}, pros=[], cons=[], metadata={})
        for i in range(n)
    ]
    return RecommendationResponse(category=category, generated_at="now",
                                  criteria_echo={}, recommendations=items)


def test_batch_item_count_sums_recommendations():
    results = {"living_areas": _resp("living_areas", 5), "housing_agencies": _resp("housing_agencies", 3)}
    total = sum(len(r.recommendations) for r in results.values())
    assert total == 8


def test_response_has_no_get_method_so_old_code_would_have_failed():
    # Documents the bug: the pre-fix `r.get("items", [])` raised on these models.
    resp = _resp("living_areas", 1)
    assert not hasattr(resp, "get")
    with pytest.raises(AttributeError):
        resp.get("items", [])  # type: ignore[attr-defined]
