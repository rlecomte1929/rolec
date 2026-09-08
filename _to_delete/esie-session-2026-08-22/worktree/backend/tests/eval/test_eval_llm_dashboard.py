"""
P3 — the new real-LLM eval metrics surface on the rag-eval dashboard.

Covers: (1) build_dashboard returns the new metric keys (live when seed reports
exist, mock otherwise without KeyError), (2) write_dashboard_report round-trips a
new key, (3) the three runners' --emit-dashboard flag writes dated report files
the dashboard reads as live.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from backend.eval.dashboard_report import write_dashboard_report
from backend.app.services.rag_eval_reports import (
    METRIC_SPECS,
    build_dashboard,
    load_live_reports,
)
from backend.eval import run_judge_calibration, run_ranking_judge, run_rag_triad

_NEW_KEYS = {
    "context_relevance", "groundedness", "answer_relevance",
    "judge_calibration_kappa", "ranking_agreement",
}


def test_new_metric_specs_registered():
    assert _NEW_KEYS <= {s.key for s in METRIC_SPECS}


def test_mock_dashboard_includes_new_metrics_without_keyerror():
    # generate_mock_reports does a hard _MOCK_VALUES[key] lookup — a missing
    # series would KeyError here.
    dash = build_dashboard(reports_dir=Path("/nonexistent-p3"), today=date(2026, 6, 30))
    assert dash["source"] == "mock"
    assert _NEW_KEYS <= {m["metric"] for m in dash["metrics"]}


def test_write_dashboard_report_round_trips_new_key(tmp_path):
    dest = write_dashboard_report(
        tmp_path, "ranking_agreement", 0.812, {"judge": "live"}, today=date(2026, 6, 30)
    )
    assert dest.name == "ranking_agreement_20260630.json"
    payload = json.loads(dest.read_text())
    assert payload["aggregate"] == 0.812
    assert payload["generated_at"] == "2026-06-30"
    series = load_live_reports(tmp_path)
    assert series["ranking_agreement"][-1]["aggregate"] == 0.812


def test_seed_reports_make_new_metrics_live(tmp_path):
    for key in _NEW_KEYS:
        write_dashboard_report(tmp_path, key, 0.75, {"seed": True}, today=date(2026, 6, 30))
    dash = build_dashboard(reports_dir=tmp_path, today=date(2026, 6, 30))
    assert dash["source"] == "live"
    by_metric = {m["metric"]: m for m in dash["metrics"]}
    for key in _NEW_KEYS:
        assert by_metric[key]["latest"] == 0.75
        assert by_metric[key]["points"]


def test_triad_runner_emit_dashboard_writes_three_files(tmp_path):
    rc = run_rag_triad.main(["--emit-dashboard", "--out-dir", str(tmp_path)])
    assert rc in (0, 1)  # gate pass/fail is irrelevant; report-only emit must happen
    series = load_live_reports(tmp_path)
    for m in ("context_relevance", "groundedness", "answer_relevance"):
        assert series.get(m), f"expected a {m} report"


def test_calibration_runner_emit_dashboard_writes_file(tmp_path):
    rc = run_judge_calibration.main(["--emit-dashboard", "--out-dir", str(tmp_path)])
    assert rc == 0
    assert load_live_reports(tmp_path).get("judge_calibration_kappa")


def test_ranking_runner_emit_dashboard_writes_file(tmp_path, monkeypatch):
    # run_ranking_judge.main() reads sys.argv (no argv param) and returns None.
    monkeypatch.setattr(
        "sys.argv",
        ["run_ranking_judge", "--emit-dashboard", "--out-dir", str(tmp_path)],
    )
    run_ranking_judge.main()
    assert load_live_reports(tmp_path).get("ranking_agreement")


def test_runners_do_not_write_without_flag(tmp_path):
    run_rag_triad.main(["--out-dir", str(tmp_path)])
    run_judge_calibration.main(["--out-dir", str(tmp_path)])
    assert not list(tmp_path.glob("*.json"))
