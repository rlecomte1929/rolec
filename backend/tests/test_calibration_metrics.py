"""
Deepen-evals slice 2 — confidence calibration.

Answers the customer-sensitive question: when the system says HIGH confidence, is
the answer actually grounded? Buckets immigration-answer replay records by their
`confidence` label, measures the actual grounded-rate per bucket, and reports an
Expected Calibration Error (ECE) → calibration_score = 1 − ECE. Implied semantics:
high=0.9, medium=0.7, low=0.4 (the N6 confidence intent).
"""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.calibration_metrics import score_calibration


def _ans(confidence, grounded):
    out = {"answer_kind": "answer", "confidence": confidence,
           "grounding_verdict": "grounded" if grounded else "partially_grounded"}
    return {"feature_key": "immigration_answer", "output_masked": json.dumps(out)}


def test_calibration_score_is_one_minus_ece():
    records = (
        [_ans("high", True)] * 5      # high actual 1.0, implied 0.9 → gap 0.1, weight 5/10
        + [_ans("low", True)] * 2     # low: 2 of 5 grounded → actual 0.4, implied 0.4 → gap 0.0
        + [_ans("low", False)] * 3
    )

    report = score_calibration(records)

    assert report["extra"]["n_answered"] == 10
    # ECE = (5/10)*0.1 + (5/10)*0.0 = 0.05 → score 0.95
    assert report["extra"]["ece"] == 0.05
    assert report["aggregate"] == 0.95
    curve = {b["confidence"]: b for b in report["reliability_curve"]}
    assert curve["high"]["actual"] == 1.0 and curve["high"]["n"] == 5
    assert curve["low"]["actual"] == 0.4 and curve["low"]["n"] == 5


def test_overconfident_bucket_flagged():
    # HIGH bucket that is actually mostly ungrounded → overconfident.
    records = [_ans("high", False)] * 4 + [_ans("high", True)] * 1  # actual 0.2 vs implied 0.9
    report = score_calibration(records)
    assert "high" in report["extra"]["overconfident_buckets"]
    assert report["aggregate"] < 0.5  # large miscalibration


def test_empty_is_safe():
    report = score_calibration([])
    assert report["aggregate"] == 0.0
    assert report["extra"]["n_answered"] == 0
