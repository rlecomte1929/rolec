"""
WS-B — tests for the outcome-accuracy producer (run_outcome_accuracy).

Verifies the producer assembles a roadmap, grades it against the seed golden roadmap,
and writes a dashboard report file in the exact shape rag_eval_reports reads (so the
previously-dead `outcome_accuracy` metric goes live).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from backend.eval.run_outcome_accuracy import _DEFAULT_GOLD, assemble_roadmap, grade, main
from backend.app.services.rag_eval_reports import build_dashboard

_GOLD = json.loads(_DEFAULT_GOLD.read_text())


def test_assemble_roadmap_non_empty():
    steps = assemble_roadmap(_GOLD["profile"])
    assert steps, "expected a non-empty assembled roadmap"
    assert all("title" in s for s in steps)


def test_grade_reports_outcome_accuracy():
    report = grade(_GOLD)
    assert "outcome_accuracy" in report
    assert report["outcome_accuracy"] == 1.0
    assert report["per_roadmap"]["missing_steps"] == []


def test_producer_writes_valid_dashboard_report(tmp_path):
    rc = main(["--gold", str(_DEFAULT_GOLD), "--out", str(tmp_path),
               "--today", "2026-06-30", "--gate"])
    assert rc == 0

    out_file = tmp_path / "outcome_accuracy_20260630.json"
    assert out_file.exists()

    payload = json.loads(out_file.read_text())
    # The two fields rag_eval_reports.load_live_reports requires.
    assert isinstance(payload["aggregate"], (int, float))
    assert payload["generated_at"] == "2026-06-30"

    # The dashboard reads this dir as a LIVE outcome_accuracy series.
    dash = build_dashboard(reports_dir=tmp_path, today=date(2026, 6, 30))
    assert dash["source"] == "live"
    oa = next(m for m in dash["metrics"] if m["metric"] == "outcome_accuracy")
    assert oa["latest"] == payload["aggregate"]
    assert oa["points"][-1]["passes_threshold"] is True
