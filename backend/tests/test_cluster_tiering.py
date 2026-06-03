"""Tests for cluster-relative supplier tiering (Parker-C).

Skipped cleanly on a machine without scikit-learn (the bare-`pytest` verify step).
The pure-Python dispatch in engine.tier is also exercised here.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest

pytest.importorskip("sklearn")

from backend.app.recommendations import engine, tiering  # noqa: E402
from backend.app.recommendations.types import RecommendationTier  # noqa: E402


def _supplier(sid: str, *, rating: float, count: int, conf: float, avail: str) -> Dict[str, Any]:
    return {
        "item_id": sid,
        "name": f"Bank {sid}",
        "rating": rating,
        "rating_count": count,
        "confidence": conf,
        "availability_level": avail,
    }


def _premium(i: int) -> Dict[str, Any]:
    # Clearly-separated high-end feature profile.
    return _supplier(f"p{i}", rating=4.5 + (i % 5) * 0.1, count=200 + i * 10, conf=90.0, avail="high")


def _budget(i: int) -> Dict[str, Any]:
    # Clearly-separated low-end feature profile.
    return _supplier(f"b{i}", rating=3.0 + (i % 5) * 0.1, count=10 + i, conf=70.0, avail="medium")


def _bank_cell() -> List[Dict[str, Any]]:
    """15 premium + 15 budget banks → two well-separated clusters."""
    return [_premium(i) for i in range(15)] + [_budget(i) for i in range(15)]


def _thresholds_from(labels: List[int], scores: List[float]) -> Dict[str, Dict[str, float]]:
    """Mirror compute_cluster_cache's per-cluster percentile cutoffs (test-side)."""
    import numpy as np

    by_cluster: Dict[int, List[float]] = {}
    for lbl, sc in zip(labels, scores):
        if lbl < 0:
            continue
        by_cluster.setdefault(lbl, []).append(sc)
    return {
        str(cid): {
            "best": float(np.percentile(vals, tiering.PCT_BEST)),
            "good": float(np.percentile(vals, tiering.PCT_GOOD)),
            "ok": float(np.percentile(vals, tiering.PCT_OK)),
        }
        for cid, vals in by_cluster.items()
    }


def test_deterministic_seed():
    cell = _bank_cell()
    a = tiering.cluster_suppliers(cell, "banks", "BE")
    b = tiering.cluster_suppliers(cell, "banks", "BE")
    assert a.labels == b.labels
    assert a.k_selected == b.k_selected
    assert a.silhouette == pytest.approx(b.silhouette)


def test_nan_features_excluded():
    cell = _bank_cell()
    cell[0] = {**cell[0], "rating": None}  # missing feature
    assignment = tiering.cluster_suppliers(cell, "banks", "BE")
    assert assignment.labels[0] == -1
    assert all(lbl >= 0 for lbl in assignment.labels[1:])


def test_under_8_falls_back():
    before = tiering.fallback_total()
    thin_cache = {"cluster_size": 5, "thresholds_json": {}, "supplier_ids_json": {}}
    t = engine.tier(72.0, category="banks", country_iso2="BE", supplier_id="s1", cache=thin_cache)
    assert t == RecommendationTier.GOOD_FIT  # absolute(72) → GOOD_FIT
    assert tiering.fallback_total() == before + 1


def test_no_cache_uses_plugin_fallback():
    before = tiering.fallback_total()
    t = engine.tier(90.0, category="banks", country_iso2="BE", supplier_id="s1", cache=None)
    assert t == RecommendationTier.BEST_MATCH
    assert tiering.fallback_total() == before + 1


def test_tier_monotonicity_within_cluster():
    thresholds = {"0": {"best": 80.0, "good": 60.0, "ok": 40.0}}
    cache = {
        "cluster_size": 10,
        "thresholds_json": thresholds,
        "supplier_ids_json": {"0": [f"s{i}" for i in range(10)]},
    }
    order = {
        RecommendationTier.WEAK: 0,
        RecommendationTier.OK: 1,
        RecommendationTier.GOOD_FIT: 2,
        RecommendationTier.BEST_MATCH: 3,
    }
    prev = -1
    for score in range(0, 101, 5):
        t = engine.tier(float(score), supplier_id="s0", cache=cache)
        assert order[t] >= prev
        prev = order[t]


def test_top_suppliers_best_match():
    thresholds = {"0": {"best": 80.0, "good": 60.0, "ok": 40.0}}
    cache = {
        "cluster_size": 10,
        "thresholds_json": thresholds,
        "supplier_ids_json": {"0": [f"s{i}" for i in range(10)]},
    }
    assert engine.tier(95.0, supplier_id="s0", cache=cache) == RecommendationTier.BEST_MATCH
    assert engine.tier(50.0, supplier_id="s1", cache=cache) == RecommendationTier.OK


def test_cluster_promotes_good_fit_to_best_match():
    """Acceptance: a budget bank that is GOOD_FIT under absolute thresholds becomes
    BEST_MATCH cluster-relative (it tops its own thin-market cluster)."""
    t0 = time.time()
    cell = _bank_cell()
    assignment = tiering.cluster_suppliers(cell, "banks", "BE")
    assert time.time() - t0 < 5.0  # CLI cell compute well under 5s

    # Scores: premiums 78-92, budgets 55-75. The top budget bank sits at 75.
    scores = [78.0 + i for i in range(15)] + [55.0 + (i * 20.0 / 14.0) for i in range(15)]
    thresholds = _thresholds_from(assignment.labels, scores)

    # Find the highest-scoring budget supplier and its cluster.
    budget_idx = 29  # last budget, score 75.0
    budget_score = scores[budget_idx]
    budget_cluster = assignment.labels[budget_idx]
    assert budget_cluster >= 0

    cache = {
        "cluster_size": sum(assignment.cluster_sizes.values()),
        "thresholds_json": thresholds,
        "supplier_ids_json": {
            str(cid): [cell[i]["item_id"] for i, lbl in enumerate(assignment.labels) if lbl == cid]
            for cid in assignment.cluster_sizes
        },
    }

    absolute = engine._absolute_tier(budget_score)
    relative = engine.tier(
        budget_score,
        category="banks",
        country_iso2="BE",
        supplier_id=cell[budget_idx]["item_id"],
        cache=cache,
    )
    assert absolute == RecommendationTier.GOOD_FIT  # 75 → absolute GOOD_FIT
    assert relative == RecommendationTier.BEST_MATCH  # tops its cluster → promoted


def test_tier_with_cluster_context_unknown_cluster_raises():
    with pytest.raises(KeyError):
        tiering.tier_with_cluster_context(90.0, 7, {"0": {"best": 80, "good": 60, "ok": 40}})
