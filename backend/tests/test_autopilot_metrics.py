"""Autopilot Phase 4 — metrics dashboard (funnel + cost) endpoint + digest."""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.app import auth_deps
from backend.app.services import autopilot_events as ev
from backend.app.services import autopilot_metrics as m

_ADMIN = {"id": "admin-1", "role": "ADMIN", "is_admin": True}


def test_compute_composes_funnel_and_kpis(monkeypatch):
    monkeypatch.setattr(m, "_funnel_counts", lambda s, since: {
        ev.TASK_DISPATCHED: 8, ev.MERGED: 5, ev.TASK_DONE: 4, ev.REVERTED: 1,
        ev.CANARY_PASSED: 4, ev.CANARY_FAILED: 1,
    })
    monkeypatch.setattr(m, "_dedup_totals", lambda s, since: {"raw": 30, "unique": 10, "dedup_factor": 3.0})
    monkeypatch.setattr(m, "_cost_by_stage", lambda s, since: {"by_stage": [{"stage": "autopilot.dispatch", "cost_usd": 0.5}], "total_usd": 0.5})
    out = m.compute_autopilot_metrics(session=object())
    assert out["kpis"]["dedup_factor"] == 3.0
    assert out["kpis"]["canary_pass_rate"] == 0.8       # 4/5
    assert out["kpis"]["revert_rate"] == 0.2            # 1/5
    assert out["cost"]["remaining_usd"] == pytest.approx(m.monthly_cap_usd() - 0.5)


def test_endpoint_admin_gated_returns_structure(monkeypatch):
    from backend.main import app
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _ADMIN
    try:
        r = TestClient(app).get("/api/admin/autopilot-metrics")
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) >= {"funnel", "dedup", "cost", "kpis"}
    finally:
        app.dependency_overrides.pop(auth_deps.get_current_user, None)


def test_endpoint_registered_on_prod_app():
    from backend.main import app
    assert "/api/admin/autopilot-metrics" in {r.path for r in app.routes}


def test_write_daily_digest_returns_summary(monkeypatch):
    monkeypatch.setattr(m, "compute_autopilot_metrics", lambda since=None, session=None: {
        "funnel": {}, "dedup": {"dedup_factor": 2.0},
        "cost": {"total_usd": 1.25},
        "kpis": {"tasks_dispatched": 3, "merged": 2, "tasks_done": 2, "reverted": 0},
    })
    out = m.write_daily_digest(day="2026-07-07", session=None)
    assert "2026-07-07" in out["summary"] and "dispatched 3" in out["summary"]
    assert "persisted" in out  # fail-soft (table may be absent in SQLite)
