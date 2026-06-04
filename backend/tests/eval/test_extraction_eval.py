# AIQ-582 — pytest suite for extraction_metrics and run_extraction_eval (no file I/O)
from __future__ import annotations

import pytest

from backend.eval.extraction_metrics import (
    AgentScore,
    aggregate_scores,
    bbox_iou,
    money_within_tolerance,
    normalize_value,
)
from backend.eval.run_extraction_eval import _score_record

# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

_SYNTHETIC_GT = {
    "document_id": "doc-001",
    "doc_type": "diploma",
    "fields": [
        {
            "name": "full_name",
            "value": "Jane Doe",
            "bbox": {"x0": 100, "y0": 200, "x1": 300, "y1": 250},
        },
        {
            "name": "institution",
            "value": "University of Paris",
            "bbox": {"x0": 100, "y0": 300, "x1": 400, "y1": 350},
        },
        {
            "name": "graduation_year",
            "value": "2019",
            "bbox": {"x0": 100, "y0": 400, "x1": 200, "y1": 430},
        },
    ],
}


def _make_pred_from_gt(gt: dict) -> dict:
    """Return a perfect copy of the ground-truth record as the prediction."""
    import copy
    return copy.deepcopy(gt)


# ---------------------------------------------------------------------------
# 1. Mock perfect predictor → value_accuracy = 1.0, bbox_iou ≥ 0.6
# ---------------------------------------------------------------------------

def test_mock_perfect_scores_unity():
    gt = _SYNTHETIC_GT
    pred = _make_pred_from_gt(gt)

    score = _score_record(gt, pred)

    assert score.n_fields == 3
    assert score.n_value_correct == 3, "All values should match for a perfect predictor"
    # bbox: perfect overlap → IoU == 1.0 ≥ 0.6
    assert score.n_bbox_correct == 3, "All bboxes should match for a perfect predictor"
    assert score.value_accuracy == 1.0
    assert score.bbox_accuracy >= 0.6


# ---------------------------------------------------------------------------
# 2. Tamper one field value → n_value_correct drops by 1
# ---------------------------------------------------------------------------

def test_tampered_value_drops_accuracy():
    import copy
    gt = _SYNTHETIC_GT
    pred = copy.deepcopy(gt)
    # Change the value of the second field
    pred["fields"][1]["value"] = "Wrong University"

    score = _score_record(gt, pred)

    assert score.n_value_correct == 2, "One tampered field should drop n_value_correct to 2"


# ---------------------------------------------------------------------------
# 3. Shifted bbox outside IoU threshold → n_bbox_correct drops
# ---------------------------------------------------------------------------

def test_shifted_bbox_drops_bbox_accuracy():
    import copy
    gt = _SYNTHETIC_GT
    pred = copy.deepcopy(gt)
    # Shift the first field's bbox far away so IoU < 0.5
    pred["fields"][0]["bbox"] = {"x0": 900, "y0": 900, "x1": 950, "y1": 950}

    score = _score_record(gt, pred)

    # Only 2 of 3 bboxes should now be correct
    assert score.n_bbox_correct == 2, "Shifted bbox should drop n_bbox_correct to 2"


# ---------------------------------------------------------------------------
# 4. Money within tolerance → match
# ---------------------------------------------------------------------------

def test_money_within_tolerance():
    # 1 % tolerance: 1000 vs 1009 → within 1 %
    assert money_within_tolerance("€ 1 009,00", "€ 1 000,00", pct=0.01) is True
    # Exact match
    assert money_within_tolerance("EUR 2500.00", "EUR 2500.00") is True
    # European format
    assert money_within_tolerance("1.500,00 EUR", "1.500,00 EUR") is True


# ---------------------------------------------------------------------------
# 5. Money above tolerance → no match
# ---------------------------------------------------------------------------

def test_money_above_tolerance():
    # 2 % difference with 1 % tolerance → should NOT match
    assert money_within_tolerance("€ 1 020,00", "€ 1 000,00", pct=0.01) is False
    # Large difference
    assert money_within_tolerance("€500.00", "€1000.00", pct=0.01) is False
