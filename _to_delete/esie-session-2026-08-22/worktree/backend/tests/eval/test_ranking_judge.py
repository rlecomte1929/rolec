# WS-D — the offline mock pairwise judge is deterministic and the agreement
# runner produces a sane report without any network call.
from __future__ import annotations

import json

import pytest

from backend.eval.run_ranking_judge import (
    DEFAULT_FIXTURES,
    mock_judge_pair,
    run_judge,
)

CTX = {"category": "banks", "corridor": "SG-SG", "criteria": {}}


def test_mock_judge_prefers_higher_rating():
    a = {"item_id": "x", "rating": 4.8, "next_available_days": 10}
    b = {"item_id": "y", "rating": 4.2, "next_available_days": 1}
    assert mock_judge_pair(CTX, a, b) == "A"
    assert mock_judge_pair(CTX, b, a) == "B"


def test_mock_judge_tiebreaks_on_availability_then_id():
    a = {"item_id": "a", "rating": 4.5, "next_available_days": 3}
    b = {"item_id": "b", "rating": 4.5, "next_available_days": 9}
    assert mock_judge_pair(CTX, a, b) == "A"  # sooner availability
    c = {"item_id": "c", "rating": 4.5, "next_available_days": 3}
    assert mock_judge_pair(CTX, a, c) == "A"  # tie → item_id asc (a < c)


def test_mock_judge_is_deterministic():
    a = {"item_id": "x", "rating": 4.4, "next_available_days": 5}
    b = {"item_id": "y", "rating": 4.6, "next_available_days": 5}
    verdicts = {mock_judge_pair(CTX, a, b) for _ in range(20)}
    assert verdicts == {"B"}


def test_run_judge_mock_no_network():
    with DEFAULT_FIXTURES.open(encoding="utf-8") as f:
        fixtures = json.load(f)
    report = run_judge(fixtures, live=False)
    assert report["judge"] == "mock"
    assert report["n_cases"] >= 3
    assert 0.0 <= report["mean_agreement"] <= 1.0
    for case in report["per_case"]:
        assert 0.0 <= case["agreement_rate"] <= 1.0
        assert case["pairs"] >= 1
