"""Tests for scripts/calibration_analysis.py (P1-04b / AIQ-636).

Covers both branches required by the task's validation criteria:
  - produces calibration curves for HIGH/MEDIUM/LOW once >=50 reviews exist;
  - rejects insufficient sample sizes with a clear message rather than
    producing misleading output.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# scripts/ is not a package — load the module directly from its file path.
_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "calibration_analysis.py"
_spec = importlib.util.spec_from_file_location("calibration_analysis", _MODULE_PATH)
cal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cal)  # type: ignore[union-attr]


def _rows(bucket: str, approved: int, corrected: int):
    out = []
    out += [{"confidence_at_time": bucket, "specialist_outcome": "approved",
             "was_edited": False, "confidence_score_at_time": 0.9} for _ in range(approved)]
    out += [{"confidence_at_time": bucket, "specialist_outcome": "rejected",
             "was_edited": True, "confidence_score_at_time": 0.6} for _ in range(corrected)]
    return out


# --- normalization / classification ---------------------------------------
def test_normalize_bucket_variants():
    assert cal.normalize_bucket("high") == "HIGH"
    assert cal.normalize_bucket("  Medium ") == "MEDIUM"
    assert cal.normalize_bucket("LOW") == "LOW"
    assert cal.normalize_bucket(None) == "UNKNOWN"
    assert cal.normalize_bucket("very-high") == "UNKNOWN"


def test_classify_outcome_uses_was_edited_fallback():
    assert cal.classify_outcome({"specialist_outcome": "approved"}) == "approved"
    assert cal.classify_outcome({"specialist_outcome": "edited"}) == "corrected"
    assert cal.classify_outcome({"specialist_outcome": None, "was_edited": True}) == "corrected"
    assert cal.classify_outcome({"specialist_outcome": None, "was_edited": False}) == "unknown"


# --- insufficient-sample guard (the reject path) ---------------------------
def test_empty_input_is_insufficient_and_does_not_crash():
    result = cal.compute_calibration([], min_sample=50)
    assert result["had_sufficient_data"] is False
    assert result["total_reviews"] == 0
    for bucket in cal.BUCKETS:
        assert result["buckets"][bucket]["sufficient"] is False
        assert "INSUFFICIENT SAMPLE" in result["buckets"][bucket]["recommendation"]


def test_below_min_sample_emits_no_threshold_recommendation():
    result = cal.compute_calibration(_rows("HIGH", approved=10, corrected=5), min_sample=50)
    high = result["buckets"]["HIGH"]
    assert high["n"] == 15
    assert high["sufficient"] is False
    assert "INSUFFICIENT SAMPLE" in high["recommendation"]
    # Must NOT leak a tighten/loosen recommendation on thin data.
    assert "TIGHTEN" not in high["recommendation"]
    assert result["had_sufficient_data"] is False


def test_markdown_flags_insufficient_data():
    result = cal.compute_calibration(_rows("HIGH", 5, 2), min_sample=50)
    md = cal.render_markdown(result, "2026-06-04")
    assert "INSUFFICIENT DATA" in md
    assert "Calibration curve" in md
    for bucket in cal.BUCKETS:
        assert bucket in md


# --- sufficient sample (the curve path) ------------------------------------
def test_high_below_target_recommends_tighten():
    # 60 HIGH reviews, 50 approved / 10 corrected -> 83.3% approval (< 95% target)
    result = cal.compute_calibration(_rows("HIGH", approved=50, corrected=10), min_sample=50)
    high = result["buckets"]["HIGH"]
    assert high["sufficient"] is True
    assert high["approval_rate"] == pytest.approx(50 / 60, rel=1e-3)
    assert "TIGHTEN HIGH" in high["recommendation"]
    assert result["had_sufficient_data"] is True


def test_high_at_target_reports_ok():
    # 60 HIGH reviews, 58 approved / 2 corrected -> 96.7% approval (>= 95%)
    result = cal.compute_calibration(_rows("HIGH", approved=58, corrected=2), min_sample=50)
    high = result["buckets"]["HIGH"]
    assert high["sufficient"] is True
    assert "HIGH OK" in high["recommendation"]


def test_low_under_correction_target_recommends_loosen():
    # 60 LOW reviews, 50 approved / 10 corrected -> only 16.7% corrected (< 90%)
    result = cal.compute_calibration(_rows("LOW", approved=50, corrected=10), min_sample=50)
    low = result["buckets"]["LOW"]
    assert low["sufficient"] is True
    assert "LOOSEN LOW" in low["recommendation"]


def test_unknown_bucket_rows_are_isolated():
    rows = _rows("HIGH", 55, 5) + [
        {"confidence_at_time": "weird", "specialist_outcome": "approved", "was_edited": False,
         "confidence_score_at_time": None}
    ]
    result = cal.compute_calibration(rows, min_sample=50)
    assert result["unknown_bucket_reviews"] == 1
    assert result["buckets"]["HIGH"]["n"] == 60  # unknown not counted in HIGH


def test_markdown_curve_path_has_recommendations():
    result = cal.compute_calibration(_rows("HIGH", 50, 10), min_sample=50)
    md = cal.render_markdown(result, "2026-06-04")
    assert "INSUFFICIENT DATA" not in md  # had sufficient data
    assert "TIGHTEN HIGH" in md
    assert "## Recommendations" in md
