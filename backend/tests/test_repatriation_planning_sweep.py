"""AIQ-2270 — 6-month repatriation planning sweep.

Pure decision layer (injected today) plus SQLite DB + cron-secret HTTP gates.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.repatriation_planning_sweep import (  # noqa: E402
    WINDOW_DAYS,
    plan_case,
    run_repatriation_planning_sweep,
)
from backend.app.services import repatriation_planning_sweep as sweep  # noqa: E402
import backend.app.routers.crons as crons  # noqa: E402

START = date(2025, 1, 1)
END = date(2026, 1, 1)  # 12 months
IN_WINDOW = END - timedelta(days=30)
BEFORE_WINDOW = END - timedelta(days=WINDOW_DAYS + 1)
ON_END = END

_SECRET = "test-cron-secret"
_PATH = "/api/crons/repatriation-planning-sweep"


def _case(**kw):
    base = {
        "id": "case-1",
        "assignment_type": "LTA",
        "expected_duration_months": 12,
        "target_move_date": START,
        "assignment_end_date": None,
        "origin_country_code": "ES",
        "dest_country_code": "IE",
        "status": "active",
    }
    base.update(kw)
    return base


def test_fires_inside_window():
    result = plan_case(_case(), today=IN_WINDOW)
    assert result.skip_reason is None
    assert result.end_date == END


def test_skips_before_window():
    result = plan_case(_case(), today=BEFORE_WINDOW)
    assert result.skip_reason == "outside_window"


def test_skips_on_or_after_end():
    result = plan_case(_case(), today=ON_END)
    assert result.skip_reason == "outside_window"


def test_skips_permanent():
    result = plan_case(_case(assignment_type="PERMANENT"), today=IN_WINDOW)
    assert result.skip_reason == "permanent"


def test_skips_domestic():
    result = plan_case(
        _case(origin_country_code="FR", dest_country_code="FR"), today=IN_WINDOW
    )
    assert result.skip_reason == "domestic"


def test_skips_when_end_date_missing():
    result = plan_case(
        _case(expected_duration_months=None, target_move_date=None, assignment_end_date=None),
        today=IN_WINDOW,
    )
    assert result.skip_reason == "missing_end_date"


def test_skips_already_seeded():
    result = plan_case(_case(), today=IN_WINDOW, already_seeded=True)
    assert result.skip_reason == "already_seeded"


def test_uses_stored_assignment_end_date():
    custom_end = date(2026, 6, 1)
    result = plan_case(
        _case(assignment_end_date=custom_end, expected_duration_months=None),
        today=custom_end - timedelta(days=10),
    )
    assert result.skip_reason is None
    assert result.end_date == custom_end


def test_derive_unit_via_missing_input_skip():
    from backend.app.services.timeline_service import derive_assignment_end_date
    assert derive_assignment_end_date(START, 12) == END
    assert derive_assignment_end_date(START, 0) is None


# ── DB layer ────────────────────────────────────────────────────────────────

_SCHEMA = [
    """CREATE TABLE cases (
        id TEXT PRIMARY KEY, origin_country_code TEXT, dest_country_code TEXT,
        target_move_date DATE, status TEXT, assignment_type TEXT,
        expected_duration_months INTEGER, assignment_end_date DATE,
        created_at TEXT)""",
    """CREATE TABLE case_milestones (
        id TEXT PRIMARY KEY, case_id TEXT, canonical_case_id TEXT,
        milestone_type TEXT, title TEXT, description TEXT, target_date TEXT,
        status TEXT, sort_order INTEGER, created_at TEXT, updated_at TEXT,
        owner TEXT, criticality TEXT, notes TEXT)""",
    """CREATE TABLE case_events (
        id TEXT PRIMARY KEY, case_id TEXT, canonical_case_id TEXT,
        event_type TEXT, payload TEXT, created_at TEXT)""",
]


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
        conn.execute(text(
            "INSERT INTO cases (id, origin_country_code, dest_country_code, "
            "target_move_date, status, assignment_type, expected_duration_months, "
            "assignment_end_date, created_at) "
            "VALUES ('case-1','ES','IE',:start,'active','LTA',12,NULL,'2025-01-01')"
        ), {"start": START.isoformat()})
    monkeypatch.setattr(sweep, "_engine", lambda: engine)
    return engine


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def test_dry_run_writes_nothing(db):
    result = run_repatriation_planning_sweep(today=IN_WINDOW, dry_run=True)
    assert result["dry_run"] is True
    assert result["would_seed"]
    assert _count(db, "case_milestones") == 0
    assert _count(db, "case_events") == 0


def test_seed_writes_return_milestones(db):
    result = run_repatriation_planning_sweep(today=IN_WINDOW)
    assert result["seeded"] == 1
    assert _count(db, "case_milestones") == 10
    with db.connect() as conn:
        types = {r[0] for r in conn.execute(text("SELECT milestone_type FROM case_milestones"))}
    assert "task_return_review" in types
    assert _count(db, "case_events") == 1


def test_second_run_is_idempotent(db):
    first = run_repatriation_planning_sweep(today=IN_WINDOW)
    second = run_repatriation_planning_sweep(today=IN_WINDOW)
    assert first["seeded"] == 1
    assert second["seeded"] == 0
    assert any(s["reason"] == "already_seeded" for s in second["skips"])
    assert _count(db, "case_milestones") == 10


def test_outside_window_db_writes_nothing(db):
    result = run_repatriation_planning_sweep(today=BEFORE_WINDOW)
    assert result["seeded"] == 0
    assert _count(db, "case_milestones") == 0


# ── Cron HTTP ───────────────────────────────────────────────────────────────

def _client() -> TestClient:
    app = FastAPI()
    app.include_router(crons.router)
    return TestClient(app, raise_server_exceptions=False)


def test_cron_secret_unset_returns_503(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    resp = _client().post(_PATH, headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 503


def test_cron_secret_wrong_returns_401(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    resp = _client().post(_PATH, headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_cron_secret_ok_returns_200(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    monkeypatch.setattr(
        crons, "run_repatriation_planning_sweep",
        lambda **k: {"today": "2026-01-01", "seeded": 0},
    )
    resp = _client().post(
        _PATH,
        headers={"Authorization": f"Bearer {_SECRET}"},
        json={"dry_run": True, "today": "2025-12-01"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
