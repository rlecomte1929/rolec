"""
Tests for the P3-01e RAG-quality dashboard — service + admin route.

The service is filesystem-based (reads committed eval-report JSON, no DB), so
the unit tests drive it with tmp_path report dirs. The route tests cover auth
gating and the mock-fallback payload shape.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import rag_eval_reports as svc  # noqa: E402
from backend.app.routers import admin_rag_eval  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402


# ── Alert logic ────────────────────────────────────────────────────────────────

def _pts(*values):
    return [{"date": f"2026-01-{i + 1:02d}", "aggregate": v} for i, v in enumerate(values)]


def test_alert_below_threshold_fires():
    alert = svc.evaluate_alert(_pts(0.90, 0.88, 0.83), threshold=0.85)
    assert alert == {"firing": True, "reason": "below_threshold"}


def test_alert_declining_above_threshold_fires():
    alert = svc.evaluate_alert(_pts(0.96, 0.95, 0.94), threshold=0.90)
    assert alert == {"firing": True, "reason": "declining"}


def test_alert_healthy_does_not_fire():
    alert = svc.evaluate_alert(_pts(0.91, 0.93, 0.92), threshold=0.85)
    assert alert == {"firing": False, "reason": "healthy"}


def test_alert_below_threshold_takes_precedence_over_decline():
    # Strictly declining AND ends below threshold → below_threshold wins.
    alert = svc.evaluate_alert(_pts(0.88, 0.86, 0.84), threshold=0.85)
    assert alert["reason"] == "below_threshold"


def test_alert_no_data():
    assert svc.evaluate_alert([], threshold=0.85) == {"firing": False, "reason": "no_data"}


# ── Mock generation ──────────────────────────────────────────────────────────────

def test_mock_is_deterministic_and_three_months():
    a = svc.generate_mock_reports(date(2026, 6, 4))
    b = svc.generate_mock_reports(date(2026, 6, 4))
    assert a == b
    assert set(a) == {s.key for s in svc.METRIC_SPECS}
    for points in a.values():
        assert len(points) == svc._MOCK_WEEKS  # ~3 months of weekly points
    # Last point lands on the requested end date.
    assert a["context_precision"][-1]["date"] == "2026-06-04"


def test_mock_dashboard_demonstrates_all_alert_states(tmp_path):
    # Force the mock path with an empty dir (reports_dir=None reads the real
    # audit/rag_eval/, which now has committed reports → would flip to 'live').
    dash = svc.build_dashboard(reports_dir=tmp_path, today=date(2026, 6, 4))
    assert dash["source"] == "mock"
    by_metric = {m["metric"]: m for m in dash["metrics"]}
    # Engineered states: precision below, factual healthy, outcome declining.
    assert by_metric["context_precision"]["alert"]["reason"] == "below_threshold"
    assert by_metric["factual_consistency"]["alert"]["firing"] is False
    assert by_metric["outcome_accuracy"]["alert"]["reason"] == "declining"


# ── Live report ingestion ────────────────────────────────────────────────────────

def _write_report(d, name, aggregate, generated_at=None):
    payload = {"metric": "x", "aggregate": aggregate}
    if generated_at:
        payload["generated_at"] = generated_at
    (d / name).write_text(json.dumps(payload))


def test_live_reports_parse_date_from_filename_and_sort(tmp_path):
    _write_report(tmp_path, "context_precision_20260301.json", 0.80)
    _write_report(tmp_path, "context_precision_20260308.json", 0.86)
    grouped = svc.load_live_reports(tmp_path)
    pts = grouped["context_precision"]
    assert [p["date"] for p in pts] == ["2026-03-01", "2026-03-08"]
    assert pts[0]["passes_threshold"] is False  # 0.80 < 0.85
    assert pts[1]["passes_threshold"] is True   # 0.86 >= 0.85


def test_live_reports_switch_source_to_live(tmp_path):
    _write_report(tmp_path, "factual_consistency_2026-04-01.json", 0.97)
    dash = svc.build_dashboard(reports_dir=tmp_path, today=date(2026, 6, 4))
    assert dash["source"] == "live"
    fc = next(m for m in dash["metrics"] if m["metric"] == "factual_consistency")
    assert fc["latest"] == 0.97


def test_malformed_and_unmatched_reports_skipped(tmp_path):
    (tmp_path / "context_precision_bad.json").write_text("{not json")  # unparseable
    (tmp_path / "context_precision_nodate.json").write_text('{"aggregate": 0.9}')  # no date
    _write_report(tmp_path, "unrelated_thing_20260301.json", 0.5)  # no metric prefix
    _write_report(tmp_path, "context_precision_20260301.json", 0.9)  # the only valid one
    grouped = svc.load_live_reports(tmp_path)
    assert list(grouped) == ["context_precision"]
    assert len(grouped["context_precision"]) == 1


def test_generated_at_field_overrides_filename(tmp_path):
    _write_report(tmp_path, "outcome_accuracy_20260101.json", 0.9, generated_at="2026-05-15")
    grouped = svc.load_live_reports(tmp_path)
    assert grouped["outcome_accuracy"][0]["date"] == "2026-05-15"


# ── Route: auth + payload ────────────────────────────────────────────────────────

def _client(*, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_rag_eval.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1", "is_admin": is_admin}
    return TestClient(app)


def test_route_rejects_non_admin():
    assert _client(is_admin=False).get("/api/admin/rag-eval/metrics").status_code == 403


def test_route_returns_all_metrics():
    r = _client().get("/api/admin/rag-eval/metrics")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] in ("mock", "live")
    assert {m["metric"] for m in body["metrics"]} == {s.key for s in svc.METRIC_SPECS}
    for m in body["metrics"]:
        assert "threshold" in m and "points" in m and "alert" in m
