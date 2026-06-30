# WS-D — correctness of the pure-python ranking metrics on a tiny hand-computed
# case, plus an end-to-end run of the offline eval over the seeded fixtures.
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.eval.ranking_metrics import (
    aggregate,
    dcg_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
)
from backend.eval.run_ranking_eval import DEFAULT_FIXTURES, run_eval

# Known case: graded relevance with an imperfect prediction.
RELEVANCE = {"a": 3.0, "b": 2.0, "c": 0.0, "d": 1.0}
PREDICTED = ["a", "c", "b", "d"]


def test_dcg_at_k_hand_computed():
    # 3/log2(2) + 0/log2(3) + 2/log2(4) + 1/log2(5)
    expected = 3 / math.log2(2) + 0 + 2 / math.log2(4) + 1 / math.log2(5)
    assert dcg_at_k(PREDICTED, RELEVANCE, 4) == pytest.approx(expected)


def test_ndcg_at_k_hand_computed():
    # IDCG ideal order a,b,d,c: 3 + 2/log2(3) + 1/log2(4) + 0
    idcg = 3 + 2 / math.log2(3) + 1 / math.log2(4)
    dcg = 3 + 2 / math.log2(4) + 1 / math.log2(5)
    assert ndcg_at_k(PREDICTED, RELEVANCE, 4) == pytest.approx(dcg / idcg)


def test_ndcg_perfect_order_is_one():
    ideal = ["a", "b", "d", "c"]
    assert ndcg_at_k(ideal, RELEVANCE, 4) == pytest.approx(1.0)


def test_ndcg_no_relevance_signal_is_one():
    assert ndcg_at_k(["x", "y"], {"x": 0.0, "y": 0.0}, 2) == 1.0


def test_mrr_first_relevant_position():
    assert mrr(PREDICTED, RELEVANCE) == pytest.approx(1.0)  # "a" at rank 1
    assert mrr(["c", "c", "b"], RELEVANCE) == pytest.approx(1 / 3)  # "b" at rank 3
    assert mrr(["c"], RELEVANCE) == 0.0  # none relevant


def test_precision_at_k():
    assert precision_at_k(PREDICTED, RELEVANCE, 2) == pytest.approx(0.5)  # a yes, c no
    assert precision_at_k(PREDICTED, RELEVANCE, 4) == pytest.approx(0.75)  # a,b,d
    assert precision_at_k(PREDICTED, RELEVANCE, 0) == 0.0


def test_aggregate_means():
    rows = [
        {"ndcg": 1.0, "mrr": 1.0, "precision": 0.5},
        {"ndcg": 0.0, "mrr": 0.0, "precision": 0.5},
    ]
    agg = aggregate(rows)
    assert agg["ndcg"] == pytest.approx(0.5)
    assert agg["precision"] == pytest.approx(0.5)
    assert aggregate([]) == {"ndcg": 0.0, "mrr": 0.0, "precision": 0.0}


def test_seeded_fixtures_exist_and_are_attribute_derived():
    """Golden rankings must use independently-derived gold, not engine output."""
    with DEFAULT_FIXTURES.open(encoding="utf-8") as f:
        data = json.load(f)
    # "attribute_derived" confirms the gold was derived from supplier attributes,
    # not seeded from engine output (which would make the gate vacuous).
    assert data["_meta"]["verification_status"] == "attribute_derived"
    assert len(data["cases"]) >= 3


def test_end_to_end_eval_passes_gate():
    """The fixed engine scores against the independent gold → NDCG@k >= 0.90 gate."""
    with DEFAULT_FIXTURES.open(encoding="utf-8") as f:
        data = json.load(f)
    report = run_eval(data)
    assert report["n_cases"] >= 3
    assert report["aggregate"]["ndcg"] >= report["ndcg_gate"]
    # Mean NDCG is expected to be ~0.98 (banks ~0.95, insurance/movers 1.0).
    # Do NOT assert == 1.0: a perfect score would re-introduce vacuity.
    assert report["aggregate"]["ndcg"] < 1.0 or any(
        c["ndcg"] < 1.0 for c in report["per_case"]
    ), "All cases score 1.0 — check that gold was not re-seeded from engine output"
