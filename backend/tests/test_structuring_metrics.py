"""
Phase 2 — structuring eval metrics (gap #3).

Grades how ReloPass STRUCTURES requirements for a specific person: does
policy_applicability_engine apply the right requirements for this profile
(assignment_type / family / nationality / destination)? The metric is
precision/recall/F1 on the "applicable" class (the risk is a requirement wrongly
included OR wrongly dropped) plus per-axis accuracy.

These tests pin the metric MATH with an injected fake evaluator so a known
confusion matrix can be constructed deterministically — the real engine is
exercised by the fixture-driven runner test.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.structuring_metrics import score_structuring


def _case(cid, expected, axis):
    return {"id": cid, "fact": {}, "case_profile": {}, "expected_status": expected, "axis": axis}


def _fake_evaluator(returns):
    # returns: {case_id -> status}; the fake keys off a marker we stash on the fact.
    def _ev(fact, case_profile):
        return {"applicability_status": returns[fact["__id__"]]}
    return _ev


def test_precision_recall_f1_and_accuracy():
    cases = [
        _case("A", "applicable", "assignment_type"),       # TP
        _case("B", "not_applicable", "assignment_type"),   # FP (engine says applicable)
        _case("C", "applicable", "family"),                # FN (engine says not_applicable)
        _case("D", "not_applicable", "family"),            # TN
    ]
    for c in cases:
        c["fact"]["__id__"] = c["id"]
    fake = _fake_evaluator({"A": "applicable", "B": "applicable",
                            "C": "not_applicable", "D": "not_applicable"})

    report = score_structuring(cases, evaluator=fake)

    assert report["n"] == 4
    assert report["accuracy"] == 0.5          # A, D correct
    assert report["precision"] == 0.5         # TP=1, FP=1
    assert report["recall"] == 0.5            # TP=1, FN=1
    assert report["f1"] == 0.5
    assert report["by_axis"]["assignment_type"] == 0.5  # A correct, B wrong
    assert report["by_axis"]["family"] == 0.5           # C wrong, D correct


def test_all_correct_scores_one():
    cases = [_case("A", "applicable", "x"), _case("B", "not_applicable", "x")]
    for c in cases:
        c["fact"]["__id__"] = c["id"]
    fake = _fake_evaluator({"A": "applicable", "B": "not_applicable"})

    report = score_structuring(cases, evaluator=fake)

    assert report["accuracy"] == 1.0
    assert report["f1"] == 1.0


def test_empty_is_safe():
    report = score_structuring([], evaluator=_fake_evaluator({}))
    assert report["n"] == 0
    assert report["accuracy"] == 0.0
    assert report["f1"] == 0.0
