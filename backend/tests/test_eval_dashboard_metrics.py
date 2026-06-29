"""
Phase 2 follow-up — surface the structuring + roadmap evals on the rag-eval
dashboard, the same way outcome_accuracy now is. Adds two MetricSpecs and makes
the two runners emit dated dashboard reports that rag_eval_reports reads.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.rag_eval_reports import (
    METRIC_SPECS,
    build_dashboard,
    load_live_reports,
)
from backend.eval import run_roadmap_outcome_eval, run_structuring_eval

_FIX = Path(__file__).parent / "fixtures" / "eval"


def test_specs_and_mock_dashboard_include_new_metrics():
    keys = {s.key for s in METRIC_SPECS}
    assert {"structuring_accuracy", "roadmap_completeness"} <= keys
    # Mock path must not KeyError on the new specs (it does a hard _MOCK_VALUES lookup).
    dash = build_dashboard(reports_dir=Path("/nonexistent-xyz"), today=date(2026, 6, 29))
    assert dash["source"] == "mock"
    mkeys = {m["metric"] for m in dash["metrics"]}
    assert {"structuring_accuracy", "roadmap_completeness"} <= mkeys


def test_structuring_runner_emits_dashboard_report(tmp_path):
    gold = _FIX / "structuring" / "in_de.jsonl"
    rc = run_structuring_eval.main(["--gold", str(gold), "--out", str(tmp_path)])
    assert rc == 0
    assert list(tmp_path.glob("structuring_accuracy_*.json"))
    series = load_live_reports(tmp_path)
    assert series.get("structuring_accuracy")
    assert series["structuring_accuracy"][-1]["aggregate"] == 1.0  # real engine scores 1.0


def test_roadmap_runner_emits_dashboard_report(tmp_path):
    gold = _FIX / "roadmap" / "in_de.json"
    produced = _FIX / "roadmap" / "in_de_produced_sample.json"
    rc = run_roadmap_outcome_eval.main(
        ["--gold", str(gold), "--produced", str(produced), "--out", str(tmp_path)]
    )
    assert rc == 0
    assert list(tmp_path.glob("roadmap_completeness_*.json"))
    series = load_live_reports(tmp_path)
    assert series.get("roadmap_completeness")
    # the imperfect sample is missing 1 of 3 steps → completeness 0.6667
    assert series["roadmap_completeness"][-1]["aggregate"] == round(2 / 3, 4)
