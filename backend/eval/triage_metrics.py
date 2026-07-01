"""
Mission Control P3 — triage eval metrics.

Scores the demand triage classifier against a gold set of {title, body,
expected_kind, expected_priority?}. Headline = kind accuracy (did we route the
demand to the right type); priority accuracy is reported when the gold pins it.
The classifier is injectable (defaults to `classify_demand`) so the math is
unit-testable against a known confusion matrix.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

Classifier = Callable[[str, str], Dict[str, Any]]


def _default_classifier() -> Classifier:
    from backend.app.services.work_item_triage import classify_demand

    return lambda title, body="": classify_demand(title, body)


def score_triage(cases: List[Dict[str, Any]], classifier: Optional[Classifier] = None) -> Dict[str, Any]:
    clf = classifier or _default_classifier()
    total = len(cases)

    kind_correct = 0
    priority_correct = 0
    priority_total = 0
    both_correct = 0
    confusion: Dict[str, int] = defaultdict(int)

    for case in cases:
        pred = clf(case["title"], case.get("body", ""))
        expected_kind = case["expected_kind"]
        expected_priority = case.get("expected_priority")

        kind_ok = pred.get("kind") == expected_kind
        confusion[f"{expected_kind}->{pred.get('kind')}"] += 1
        if kind_ok:
            kind_correct += 1

        priority_ok = True
        if expected_priority is not None:
            priority_total += 1
            priority_ok = pred.get("priority") == expected_priority
            if priority_ok:
                priority_correct += 1

        if kind_ok and priority_ok:
            both_correct += 1

    kind_accuracy = kind_correct / total if total else 0.0
    return {
        "accuracy": kind_accuracy,  # dashboard headline = kind accuracy
        "kind_accuracy": kind_accuracy,
        "priority_accuracy": (priority_correct / priority_total) if priority_total else None,
        "overall_accuracy": both_correct / total if total else 0.0,
        "confusion": dict(confusion),
        "total": total,
    }
