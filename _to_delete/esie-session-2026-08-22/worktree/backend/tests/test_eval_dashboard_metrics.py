"""
Dashboard metric wiring for the Phase 2 evals.

The aggregate 'roadmap_completeness' (corridor completeness %) metric is
RETIRED: an aggregate average hides rare-slice failures, so the dashboard now
plots sliced non-obvious recall vs the lawyer-verified HLP baseline
(``nonobvious_recall``, emitted by run_nonobvious_recall_eval) with the WORST
(corridor x employee_type) slice as the plotted number. These tests pin:
no roadmap_completeness spec or mock series anywhere, the structuring runner
still emits its report, and the new sliced runner emits a report the dashboard
reads with worst-first slice detail.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.rag_eval_reports import (
    METRIC_SPECS,
    build_dashboard,
    load_live_reports,
)
from backend.eval import run_nonobvious_recall_eval, run_roadmap_outcome_eval, run_structuring_eval

_FIX = Path(__file__).parent / "fixtures" / "eval"


def test_aggregate_roadmap_completeness_is_retired():
    keys = {s.key for s in METRIC_SPECS}
    assert "roadmap_completeness" not in keys
    assert "nonobvious_recall" in keys
    assert "structuring_accuracy" in keys
    # A single missed non-obvious requirement in any slice must alert.
    spec = next(s for s in METRIC_SPECS if s.key == "nonobvious_recall")
    assert spec.threshold == 1.0
    # Mock path must not KeyError on the specs (hard _MOCK_VALUES lookup), and
    # must not resurrect the retired aggregate.
    dash = build_dashboard(reports_dir=Path("/nonexistent-xyz"), today=date(2026, 6, 29))
    assert dash["source"] == "mock"
    mkeys = {m["metric"] for m in dash["metrics"]}
    assert "roadmap_completeness" not in mkeys
    assert {"structuring_accuracy", "nonobvious_recall"} <= mkeys


def test_mock_dashboard_surfaces_worst_slice_first():
    dash = build_dashboard(reports_dir=Path("/nonexistent-xyz"), today=date(2026, 6, 29))
    metric = next(m for m in dash["metrics"] if m["metric"] == "nonobvious_recall")
    slices = metric["slices"]
    # All three active corridors report sliced recall.
    assert {s["corridor"] for s in slices} == {"FR_NO", "ES_IE", "NO_FR"}
    assert len(slices) == 6
    # Worst slice first, identified by corridor AND employee type.
    recalls = [s["recall"] for s in slices]
    assert recalls == sorted(recalls)
    assert metric["worst_slice"]["corridor"] == slices[0]["corridor"]
    assert metric["worst_slice"]["employee_type"] == slices[0]["employee_type"]
    # The plotted aggregate is the worst slice's recall, not a mean.
    assert metric["latest"] == slices[0]["recall"]


def test_structuring_runner_emits_dashboard_report(tmp_path):
    gold = _FIX / "structuring" / "in_de.jsonl"
    rc = run_structuring_eval.main(["--gold", str(gold), "--out", str(tmp_path)])
    assert rc == 0
    assert list(tmp_path.glob("structuring_accuracy_*.json"))
    series = load_live_reports(tmp_path)
    assert series.get("structuring_accuracy")
    assert series["structuring_accuracy"][-1]["aggregate"] == 1.0  # real engine scores 1.0


def test_roadmap_runner_no_longer_emits_the_aggregate_report(tmp_path):
    # --out was the roadmap_completeness (corridor completeness %) emission; it
    # is gone, so argparse must reject it.
    gold = _FIX / "roadmap" / "in_de.json"
    produced = _FIX / "roadmap" / "in_de_produced_sample.json"
    with pytest.raises(SystemExit):
        run_roadmap_outcome_eval.main(
            ["--gold", str(gold), "--produced", str(produced), "--out", str(tmp_path)]
        )
    assert not list(tmp_path.glob("roadmap_completeness_*.json"))


def test_nonobvious_runner_emits_sliced_dashboard_report(tmp_path):
    produced = _FIX / "nonobvious" / "produced_slices_sample.json"
    rc = run_nonobvious_recall_eval.main(
        ["--produced", str(produced), "--out", str(tmp_path), "--gate"]
    )
    assert rc == 0  # the sample serves every requirement in every slice
    files = list(tmp_path.glob("nonobvious_recall_*.json"))
    assert files
    series = load_live_reports(tmp_path)
    points = series.get("nonobvious_recall")
    assert points
    latest = points[-1]
    assert latest["aggregate"] == 1.0  # worst slice recall, not an average
    assert len(latest["slices"]) == 6
    assert {s["corridor"] for s in latest["slices"]} == {"FR_NO", "ES_IE", "NO_FR"}
    # Live report flows into the dashboard with worst-first slice detail.
    dash = build_dashboard(reports_dir=tmp_path)
    metric = next(m for m in dash["metrics"] if m["metric"] == "nonobvious_recall")
    assert dash["source"] == "live"
    assert metric["slices"] == latest["slices"]
