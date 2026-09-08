"""
Roadmap completeness/ordering eval metrics (Phase 2, gaps #2 + #4).

Grades a produced AI roadmap (list of steps) against a gold expectation for a
profile:
  - completeness (recall): |expected steps present| / |expected steps|
  - noise_precision:       |produced steps that match some expected step| / |produced|
  - ordering:              |gold order constraints satisfied| / |applicable constraints|

A produced step matches an expected step when the expected `match` substring appears
(case-insensitive) in the produced step's title. Complements the Phase 1 replay
grader (which aggregates the verifier's per-step verdicts) by checking the roadmap
against an independent gold of what SHOULD be there and in what order.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _first_match_index(produced_titles: List[str], match: str) -> Optional[int]:
    needle = (match or "").strip().lower()
    if not needle:
        return None
    for i, title in enumerate(produced_titles):
        if needle in title:
            return i
    return None


def score_roadmap(produced_steps: List[Dict[str, Any]], gold: Dict[str, Any]) -> Dict[str, Any]:
    """Score one produced roadmap against a gold expectation. Safe on empty input."""
    titles = [str(s.get("title") or "").lower() for s in produced_steps]
    expected = gold.get("expected_steps") or []

    # Map each expected key to the produced index it matched (or None if missing).
    matched_index: Dict[str, Optional[int]] = {
        e["key"]: _first_match_index(titles, e.get("match", "")) for e in expected
    }
    present_keys = {k for k, idx in matched_index.items() if idx is not None}
    missing_steps = [e["key"] for e in expected if matched_index[e["key"]] is None]

    # A produced step is "relevant" if it matched at least one expected step.
    matched_produced_idx = {idx for idx in matched_index.values() if idx is not None}
    extra_steps = [
        str(s.get("title")) for i, s in enumerate(produced_steps) if i not in matched_produced_idx
    ]

    n_expected = len(expected)
    n_produced = len(produced_steps)
    completeness = (len(present_keys) / n_expected) if n_expected else 0.0
    noise_precision = (len(matched_produced_idx) / n_produced) if n_produced else 0.0

    # Ordering: of the gold constraints whose BOTH endpoints are present, how many
    # appear in the right order in the produced sequence.
    constraints = gold.get("order") or []
    applicable = [(a, b) for a, b in constraints
                  if a in present_keys and b in present_keys]
    satisfied = sum(1 for a, b in applicable if matched_index[a] < matched_index[b])
    ordering = (satisfied / len(applicable)) if applicable else 1.0

    return {
        "completeness": round(completeness, 4),
        "noise_precision": round(noise_precision, 4),
        "ordering": round(ordering, 4),
        "missing_steps": missing_steps,
        "extra_steps": extra_steps,
        "counts": {
            "n_expected": n_expected,
            "n_present": len(present_keys),
            "n_produced": n_produced,
            "n_constraints_applicable": len(applicable),
        },
    }


def aggregate_roadmap_scores(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mean completeness/noise/ordering across many graded roadmaps (e.g. a gold set).
    The composite `outcome_accuracy` is the mean of the three (all must be high for a
    roadmap to be good)."""
    if not reports:
        return {"completeness": 0.0, "noise_precision": 0.0, "ordering": 0.0,
                "outcome_accuracy": 0.0, "n": 0}
    n = len(reports)
    comp = sum(r["completeness"] for r in reports) / n
    noise = sum(r["noise_precision"] for r in reports) / n
    order = sum(r["ordering"] for r in reports) / n
    return {
        "completeness": round(comp, 4),
        "noise_precision": round(noise, 4),
        "ordering": round(order, 4),
        "outcome_accuracy": round((comp + noise + order) / 3, 4),
        "n": n,
    }
