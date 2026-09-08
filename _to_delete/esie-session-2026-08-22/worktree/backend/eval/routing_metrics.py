"""
Routing eval metrics — how well the assistant domain router sends a question to
the right engine (immigration vs policy) and defers honestly (ambiguous).

A gold case is ``{question, expected_domain}``. Reports overall accuracy, per-domain
precision/recall/F1 (so a regression localises to one domain), an ambiguous-rate
(sanity: high enough to be honest, low enough to be useful), and a confusion map.

The classifier is injectable (defaults to the real `classify_domain`) so the metric
math is unit-testable against a known confusion matrix.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

Classifier = Callable[[str], Dict[str, Any]]

DOMAINS = ("immigration", "policy", "ambiguous")


def _default_classifier() -> Classifier:
    from backend.app.services.assistant_domain_router import classify_domain

    return classify_domain


def _f1(precision: float, recall: float) -> float:
    return (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0


def score_routing(
    cases: List[Dict[str, Any]],
    classifier: Optional[Classifier] = None,
) -> Dict[str, Any]:
    clf = classifier or _default_classifier()
    total = len(cases)

    correct = 0
    predicted_ambiguous = 0
    tp: Dict[str, int] = defaultdict(int)
    fp: Dict[str, int] = defaultdict(int)
    fn: Dict[str, int] = defaultdict(int)
    confusion: Dict[str, int] = defaultdict(int)

    for case in cases:
        expected = case["expected_domain"]
        predicted = clf(case["question"])["domain"]
        confusion[f"{expected}->{predicted}"] += 1
        if predicted == "ambiguous":
            predicted_ambiguous += 1
        if predicted == expected:
            correct += 1
            tp[expected] += 1
        else:
            fp[predicted] += 1
            fn[expected] += 1

    per_domain: Dict[str, Dict[str, float]] = {}
    for d in DOMAINS:
        precision = tp[d] / (tp[d] + fp[d]) if (tp[d] + fp[d]) else 0.0
        recall = tp[d] / (tp[d] + fn[d]) if (tp[d] + fn[d]) else 0.0
        per_domain[d] = {
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
            "support": tp[d] + fn[d],
        }

    return {
        "accuracy": correct / total if total else 0.0,
        "ambiguous_rate": predicted_ambiguous / total if total else 0.0,
        "per_domain": per_domain,
        "confusion": dict(confusion),
        "total": total,
    }
