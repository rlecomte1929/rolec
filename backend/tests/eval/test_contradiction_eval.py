# AIQ-584 — unit tests for run_contradiction_eval (no file I/O, inline fixtures).
"""
5 test cases:
1. mock.perfect: recall=1.0, precision=1.0
2. per-type tp exactly 5/5/5/5/5
3. silent detector: recall=0.0, gate FAILS
4. noisy detector (255 preds, 25 true): precision<0.20, gate FAILS
5. 4-of-5-per-type: recall=0.8, gate FAILS
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from backend.eval.run_contradiction_eval import (
    _eval_one_dossier,
    RECALL_GATE,
    PRECISION_GATE,
    FP_PER_DOSSIER_GATE,
)

CONTRADICTION_TYPES = [
    "SURNAME_MISMATCH",
    "DOB_MISMATCH",
    "EMPLOYER_MISMATCH",
    "SALARY_MISMATCH",
    "ADDRESS_MISMATCH",
]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_contradiction(dossier_id: str, ctype: str, idx: int = 0) -> Dict[str, Any]:
    return {
        "dossier_id": dossier_id,
        "type": ctype,
        "field_key": f"{ctype.lower()}_field_{idx}",
        "affected_documents": [f"doc_{ctype}_{idx}_a", f"doc_{ctype}_{idx}_b"],
    }


def _gt_with_contradictions(contradictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"seeded_contradictions": contradictions}


def _perfect_predictor(gt: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(gt.get("seeded_contradictions", []))


def _silent_predictor(gt: Dict[str, Any]) -> List[Dict[str, Any]]:
    return []


# ---------------------------------------------------------------------------
# Test 1: mock.perfect → recall=1.0, precision=1.0
# ---------------------------------------------------------------------------

def test_perfect_predictor_full_marks():
    contradictions = [
        _make_contradiction("d1", ctype, i)
        for i, ctype in enumerate(CONTRADICTION_TYPES)
    ]
    gt = _gt_with_contradictions(contradictions)
    metrics = _eval_one_dossier(gt, _perfect_predictor)

    n = len(CONTRADICTION_TYPES)
    assert metrics["tp_gt"] == n
    assert metrics["tp_pred"] == n
    assert metrics["fp"] == 0
    assert metrics["n_gt"] == n
    assert metrics["n_pred"] == n


# ---------------------------------------------------------------------------
# Test 2: per-type TP exactly 5/5/5/5/5 (one per type, perfect)
# ---------------------------------------------------------------------------

def test_per_type_tp_five_each():
    """One seeded contradiction per type, predictor echoes all."""
    contradictions = [
        _make_contradiction("d2", ctype, i)
        for i, ctype in enumerate(CONTRADICTION_TYPES)
    ]
    gt = _gt_with_contradictions(contradictions)
    metrics = _eval_one_dossier(gt, _perfect_predictor)

    assert metrics["n_gt"] == 5
    assert metrics["tp_gt"] == 5
    assert metrics["tp_pred"] == 5
    assert metrics["fp"] == 0


# ---------------------------------------------------------------------------
# Test 3: silent detector → recall=0.0
# ---------------------------------------------------------------------------

def test_silent_detector_fails_recall_gate():
    contradictions = [
        _make_contradiction("d3", ctype, i)
        for i, ctype in enumerate(CONTRADICTION_TYPES)
    ]
    gt = _gt_with_contradictions(contradictions)
    metrics = _eval_one_dossier(gt, _silent_predictor)

    assert metrics["tp_gt"] == 0
    assert metrics["n_pred"] == 0
    assert metrics["fp"] == 0

    # Aggregate recall would be 0.0 — fails gate
    recall = metrics["tp_gt"] / metrics["n_gt"]
    assert recall == 0.0
    assert recall < RECALL_GATE


# ---------------------------------------------------------------------------
# Test 4: noisy detector (255 preds, 25 true) → precision < 0.20
# ---------------------------------------------------------------------------

def test_noisy_detector_fails_precision_gate():
    """25 real contradictions (5 types x 5 each), predictor returns 255 predictions."""
    real_contradictions = [
        _make_contradiction("d4", ctype, i)
        for ctype in CONTRADICTION_TYPES
        for i in range(5)
    ]
    gt = _gt_with_contradictions(real_contradictions)

    def noisy_predictor(ground_truth):
        # Return all 25 real contradictions plus 230 garbage ones.
        real = list(ground_truth.get("seeded_contradictions", []))
        noise = [
            {
                "dossier_id": "d4",
                "type": "SURNAME_MISMATCH",
                "field_key": f"noise_field_{j}",
                "affected_documents": [f"noise_doc_{j}"],
            }
            for j in range(230)
        ]
        return real + noise

    metrics = _eval_one_dossier(gt, noisy_predictor)
    precision = metrics["tp_pred"] / metrics["n_pred"]
    assert precision < 0.20
    assert precision < PRECISION_GATE


# ---------------------------------------------------------------------------
# Test 5: 4-of-5-per-type → recall=0.80, gate FAILS
# ---------------------------------------------------------------------------

def test_four_of_five_per_type_fails_recall_gate():
    """5 types x 5 contradictions each = 25 total. Predictor returns only 4/5 per type."""
    all_contradictions = [
        _make_contradiction("d5", ctype, i)
        for ctype in CONTRADICTION_TYPES
        for i in range(5)
    ]
    gt = _gt_with_contradictions(all_contradictions)

    def four_of_five_predictor(ground_truth):
        seeded = ground_truth.get("seeded_contradictions", [])
        # Skip the 5th item of each type (indices 4, 9, 14, 19, 24)
        return [c for idx, c in enumerate(seeded) if (idx % 5) != 4]

    metrics = _eval_one_dossier(gt, four_of_five_predictor)
    recall = metrics["tp_gt"] / metrics["n_gt"]
    assert recall == pytest.approx(0.8)
    assert recall < RECALL_GATE
