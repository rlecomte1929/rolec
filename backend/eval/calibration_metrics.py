"""
Confidence-calibration metrics (deepen-evals slice 2).

Buckets immigration-answer replay records by their `confidence` label and compares
the actual grounded-rate per bucket against the label's intended meaning
(high=0.9, medium=0.7, low=0.4 — the N6 confidence intent). Reports an Expected
Calibration Error (ECE, size-weighted) and calibration_score = 1 − ECE, plus a
reliability curve and any overconfident buckets (actual far below implied).

Correctness proxy = grounding_verdict == 'grounded' among answered records. This
works today (uses the pipeline's own verifier) and complements the human
specialist_review_events calibration loop, which is starved of data.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List

_ANSWER_FEATURE = "immigration_answer"
_IMPLIED = {"high": 0.9, "medium": 0.7, "low": 0.4}
_OVERCONFIDENT_TOLERANCE = 0.1


def _load(rec: Dict[str, Any]) -> Dict[str, Any]:
    raw = rec.get("output_masked") or rec.get("output") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def score_calibration(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate confidence calibration. aggregate = 1 − ECE. Safe on empty input."""
    counts: Dict[str, int] = defaultdict(int)
    correct: Dict[str, int] = defaultdict(int)

    for rec in records:
        if rec.get("feature_key") != _ANSWER_FEATURE:
            continue
        out = _load(rec)
        if out.get("answer_kind") != "answer":
            continue
        conf = str(out.get("confidence") or "").lower()
        if conf not in _IMPLIED:
            continue
        counts[conf] += 1
        if out.get("grounding_verdict") == "grounded":
            correct[conf] += 1

    n_answered = sum(counts.values())
    reliability_curve = []
    ece = 0.0
    overconfident = []
    for conf in ("high", "medium", "low"):
        n = counts[conf]
        if not n:
            continue
        actual = correct[conf] / n
        implied = _IMPLIED[conf]
        ece += (n / n_answered) * abs(implied - actual)
        reliability_curve.append({"confidence": conf, "n": n,
                                  "actual": round(actual, 4), "implied": implied})
        if actual < implied - _OVERCONFIDENT_TOLERANCE:
            overconfident.append(conf)

    score = (1.0 - ece) if n_answered else 0.0
    return {
        "aggregate": round(score, 4),
        "reliability_curve": reliability_curve,
        "extra": {
            "metric": "calibration_score",
            "n_answered": n_answered,
            "ece": round(ece, 4),
            "overconfident_buckets": overconfident,
        },
    }
