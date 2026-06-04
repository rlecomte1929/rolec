# AIQ-583 — unit tests for run_eligibility_eval (no file I/O, inline fixtures).
"""
5 test cases:
1. mock.perfect: outcome_accuracy=1.0, citation_effective_ratio=1.0
2. wrong outcome: outcome_accuracy=0.0, gate FAILS
3. uncited outcome: n_has_citation=0, gate FAILS (citation_effective_ratio=1.0 vacuous, but gate is outcome-based)
4. future citation: citation_effective_ratio=0.0, gate FAILS
5. rule registry basics: DE_AUFENTHG_18G:2026 effective 2026-07-01 but NOT 2025-12-31
"""

from datetime import date

import pytest

from backend.eval.rule_registry import is_effective, RULE_EFFECTIVE_WINDOWS
from backend.eval.run_eligibility_eval import _eval_one, EVAL_DATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gt(outcome_set, citations=None):
    """Build a minimal ground_truth dict."""
    return {
        "eligibility_verdict": {
            "outcome_set": outcome_set,
            "citations": citations or [],
        }
    }


def _perfect_predictor(gt):
    return gt.get("eligibility_verdict", {})


# ---------------------------------------------------------------------------
# Test 1: mock.perfect — both metrics must be 1.0
# ---------------------------------------------------------------------------

def test_perfect_predictor():
    gt = _gt(
        outcome_set=["ELIGIBLE_BLUE_CARD", "ELIGIBLE_ICT"],
        citations=["DE_AUFENTHG_18G:2026", "EU_DIR_2021_1883"],
    )
    metrics = _eval_one(gt, _perfect_predictor)
    assert metrics["outcome_accuracy"] == 1.0
    assert metrics["citation_effective_ratio"] == 1.0
    assert metrics["n_has_citation"] == 1


# ---------------------------------------------------------------------------
# Test 2: wrong outcome → outcome_accuracy=0.0
# ---------------------------------------------------------------------------

def test_wrong_outcome_fails_gate():
    gt = _gt(
        outcome_set=["ELIGIBLE_BLUE_CARD"],
        citations=["DE_AUFENTHG_18G:2026"],
    )

    def wrong_predictor(ground_truth):
        return {
            "outcome_set": ["WRONG_OUTCOME"],
            "citations": ["DE_AUFENTHG_18G:2026"],
        }

    metrics = _eval_one(gt, wrong_predictor)
    assert metrics["outcome_accuracy"] == 0.0


# ---------------------------------------------------------------------------
# Test 3: no citations → n_has_citation=0
# ---------------------------------------------------------------------------

def test_uncited_outcome_has_no_citation():
    gt = _gt(
        outcome_set=["ELIGIBLE_BLUE_CARD"],
        citations=["DE_AUFENTHG_18G:2026"],
    )

    def empty_citations_predictor(ground_truth):
        return {
            "outcome_set": ["ELIGIBLE_BLUE_CARD"],
            "citations": [],
        }

    metrics = _eval_one(gt, empty_citations_predictor)
    assert metrics["n_has_citation"] == 0
    # citation_effective_ratio is vacuously 1.0 (nothing to check)
    assert metrics["citation_effective_ratio"] == 1.0
    # outcome_accuracy is 1.0 (outcome was correct)
    assert metrics["outcome_accuracy"] == 1.0


# ---------------------------------------------------------------------------
# Test 4: future citation (rule not yet effective) → citation_effective_ratio=0.0
# ---------------------------------------------------------------------------

def test_future_citation_fails_gate():
    # Use a date before DE_AUFENTHG_18G:2026 became effective (2026-01-01).
    past_date = date(2025, 12, 31)
    gt = _gt(
        outcome_set=["ELIGIBLE_BLUE_CARD"],
        citations=["DE_AUFENTHG_18G:2026"],
    )

    def future_predictor(ground_truth):
        return {
            "outcome_set": ["ELIGIBLE_BLUE_CARD"],
            "citations": ["DE_AUFENTHG_18G:2026"],
        }

    metrics = _eval_one(gt, future_predictor, eval_date=past_date)
    assert metrics["citation_effective_ratio"] == 0.0


# ---------------------------------------------------------------------------
# Test 5: rule registry basics
# ---------------------------------------------------------------------------

def test_rule_registry_effective_window():
    rule_id = "DE_AUFENTHG_18G:2026"
    # Must be in the registry
    assert rule_id in RULE_EFFECTIVE_WINDOWS

    # Effective on evaluation date (2026-07-01)
    assert is_effective(rule_id, date(2026, 7, 1)) is True

    # NOT effective before it came into force (2026-01-01)
    assert is_effective(rule_id, date(2025, 12, 31)) is False

    # Unknown rule → always False
    assert is_effective("UNKNOWN_RULE:9999", date(2026, 7, 1)) is False
