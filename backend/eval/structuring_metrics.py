"""
Structuring eval metrics (Phase 2, gap #3).

Scores how well policy_applicability_engine STRUCTURES requirements for a specific
profile. Positive class = "applicable" (the two-sided risk: a requirement wrongly
included = false positive; a requirement wrongly dropped = false negative). Reports
overall accuracy (exact-status match), applicable-class precision/recall/F1, and
per-axis accuracy so a regression can be localised to assignment_type / family /
nationality / destination matching.

The evaluator is injectable (defaults to the real engine) so the metric math is
unit-testable against a known confusion matrix.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

Evaluator = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]

_APPLICABLE = "applicable"


def _default_evaluator() -> Evaluator:
    from backend.app.services.policy_applicability_engine import evaluate_fact_applicability

    return evaluate_fact_applicability


def _f1(precision: float, recall: float) -> float:
    return (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0


def score_structuring(
    cases: List[Dict[str, Any]],
    evaluator: Optional[Evaluator] = None,
) -> Dict[str, Any]:
    """Run each gold case through the evaluator and aggregate quality metrics.

    A gold case is ``{fact, case_profile, expected_status, axis}``. `expected_status`
    is the applicability_status the engine should return for this (fact, profile).
    """
    evaluator = evaluator or _default_evaluator()

    n = len(cases)
    n_correct = 0
    tp = fp = fn = 0
    by_axis_total: Dict[str, int] = defaultdict(int)
    by_axis_correct: Dict[str, int] = defaultdict(int)
    confusion: Dict[str, int] = defaultdict(int)

    for case in cases:
        expected = case.get("expected_status")
        actual = (evaluator(case.get("fact") or {}, case.get("case_profile") or {})
                  or {}).get("applicability_status")
        correct = actual == expected
        n_correct += int(correct)

        axis = case.get("axis") or "unspecified"
        by_axis_total[axis] += 1
        by_axis_correct[axis] += int(correct)
        confusion[f"{expected}->{actual}"] += 1

        exp_pos = expected == _APPLICABLE
        act_pos = actual == _APPLICABLE
        if exp_pos and act_pos:
            tp += 1
        elif not exp_pos and act_pos:
            fp += 1
        elif exp_pos and not act_pos:
            fn += 1

    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0

    return {
        "n": n,
        "n_correct": n_correct,
        "accuracy": round(n_correct / n, 4) if n else 0.0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(_f1(precision, recall), 4),
        "by_axis": {
            axis: round(by_axis_correct[axis] / by_axis_total[axis], 4)
            for axis in sorted(by_axis_total)
        },
        "confusion": dict(confusion),
        "counts": {"tp": tp, "fp": fp, "fn": fn},
    }
