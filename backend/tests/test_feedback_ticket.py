"""TDD tests for D-BugRoutine Slice-1 — submit pre-fill + reporter status endpoint.

Tests cover:
  1. submit_feedback pre-fills feedback_status (stream='product', source_id=report_id)
     with status='new', severity, area, reporter_id from classify().
  2. Best-effort: submit still returns 201 even when feedback_status table is absent.
  3. GET /api/feedback/{report_id}/status returns the ticket for the owner.
  4. GET /api/feedback/{report_id}/status returns 404 for a different user.

Uses a minimal FastAPI app (NOT backend.main) with the feedback router mounted
and backend.app.auth_deps.get_current_user overridden.
The feedback router's db.engine is monkeypatched to an in-memory SQLite engine
so no real Postgres is required.

Isolation note: some sibling test modules (e.g. test_e1b_extraction_persist.py)
replace sys.modules["backend.database"] with the real module at collection time.
To stay suite-order-independent we patch ``feedback_router_module.db.engine``
(the exact reference the router holds) rather than ``_db_module.db.engine``
(which may be a different object after that replacement).
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import feedback as feedback_router_module  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

# ── Shared SQLite schema (feedback + feedback_status with new ticket columns) ─

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id           TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  user_id      TEXT,
  page_url     TEXT,
  category     TEXT DEFAULT 'other',
  message      TEXT,
  status       TEXT DEFAULT 'new',
  created_at   TEXT DEFAULT (datetime('now')),
  report_id    TEXT,
  screenshot_data TEXT, screenshot_url TEXT,
  reporter_email TEXT,
  reporter_name TEXT,
  reporter_role TEXT
);
CREATE TABLE IF NOT EXISTS feedback_status (
  stream          TEXT NOT NULL,
  source_id       TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'new',
  owner           TEXT,
  resolution      TEXT,
  updated_at      TEXT,
  severity        TEXT,
  area            TEXT,
  reporter_id     TEXT,
  dispatch_ref    TEXT,
  dispatch_status TEXT,
  PRIMARY KEY (stream, source_id)
)
"""

# ── Fixture: SQLite engine + monkeypatch db.engine ────────────────────────────


@pytest.fixture()
def sqlite_engine():
    """Create an in-memory SQLite engine with the required schema."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
    return engine


@pytest.fixture()
def patched_db(sqlite_engine, monkeypatch):
    """Monkeypatch the feedback router's db.engine to the SQLite engine.

    Patches feedback_router_module.db directly (the reference the router
    captured at import time) so the fixture is robust to suite-order effects
    that replace sys.modules["backend.database"] mid-collection.
    """
    monkeypatch.setattr(feedback_router_module.db, "engine", sqlite_engine)
    yield sqlite_engine


# ── Test client factory ───────────────────────────────────────────────────────


def _make_client(user_id: str = "user-001") -> TestClient:
    app = FastAPI()
    app.include_router(feedback_router_module.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "auth_uuid": user_id,
        "is_admin": False,
    }
    return TestClient(app)


# ── submit_feedback pre-fill tests ───────────────────────────────────────────


def test_submit_prefills_feedback_status(patched_db):
    """submit_feedback upserts a feedback_status row with classified severity/area."""
    client = _make_client("u-alpha")
    resp = client.post(
        "/api/feedback",
        json={"category": "bug", "message": "I get a 500 error on the dashboard"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["ticket_seeded"] is True
    report_id = body["report_id"]

    # Check feedback_status was seeded
    with patched_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT fs.stream, fs.status, fs.severity, fs.area, fs.reporter_id "
                "FROM feedback f JOIN feedback_status fs "
                "  ON fs.source_id = CAST(f.id AS TEXT) "
                "WHERE f.report_id = :rid"
            ),
            {"rid": report_id},
        ).fetchone()

    assert row is not None, "feedback_status row was not created"
    assert row[0] == "product"
    assert row[1] == "new"
    assert row[2] in {"low", "medium", "high", "critical"}  # 500 → high
    assert row[3] in {"ui", "api", "isolation", "feature", "other"}
    assert row[4] == "u-alpha"


def test_submit_status_is_new(patched_db):
    """Seeded feedback_status always starts with status='new'."""
    client = _make_client("u-beta")
    resp = client.post(
        "/api/feedback",
        json={"category": "other", "message": "Nice tool, keep it up"},
    )
    assert resp.status_code == 201
    report_id = resp.json()["report_id"]

    with patched_db.connect() as conn:
        status = conn.execute(
            text(
                "SELECT fs.status FROM feedback f JOIN feedback_status fs "
                "  ON fs.source_id = CAST(f.id AS TEXT) WHERE f.report_id = :rid"
            ),
            {"rid": report_id},
        ).scalar()
    assert status == "new"


def test_submit_still_succeeds_without_feedback_status_table(monkeypatch):
    """Best-effort: submit returns 201 even when feedback_status table doesn't exist."""
    # Use an engine that has ONLY the feedback table (no feedback_status)
    engine_no_fs = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine_no_fs.begin() as conn:
        conn.execute(text(
            "CREATE TABLE feedback ("
            "id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),"
            "user_id TEXT, page_url TEXT, category TEXT DEFAULT 'other',"
            "message TEXT, status TEXT DEFAULT 'new',"
            "created_at TEXT DEFAULT (datetime('now')),"
            "report_id TEXT, screenshot_data TEXT, screenshot_url TEXT,"
            "reporter_email TEXT, reporter_name TEXT, reporter_role TEXT)"
        ))

    # Patch the router's own db reference (suite-order safe).
    monkeypatch.setattr(feedback_router_module.db, "engine", engine_no_fs)
    client = _make_client("u-gamma")
    resp = client.post(
        "/api/feedback",
        json={"category": "bug", "message": "broken form"},
    )
    assert resp.status_code == 201, f"submit must survive missing feedback_status: {resp.text}"
    body = resp.json()
    assert body["ok"] is True
    assert body["ticket_seeded"] is False


def test_submit_isolation_bug_classified_critical(patched_db):
    """Isolation-keyword feedback → critical severity in feedback_status."""
    client = _make_client("u-sec")
    resp = client.post(
        "/api/feedback",
        json={"category": "bug", "message": "I can see another company's data — isolation leak!"},
    )
    assert resp.status_code == 201
    report_id = resp.json()["report_id"]

    with patched_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT fs.severity, fs.area FROM feedback f JOIN feedback_status fs "
                "  ON fs.source_id = CAST(f.id AS TEXT) WHERE f.report_id = :rid"
            ),
            {"rid": report_id},
        ).fetchone()
    assert row is not None
    assert row[0] == "critical"
    assert row[1] == "isolation"


def _submit_as(user: dict):
    app = FastAPI()
    app.include_router(feedback_router_module.router)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    resp = client.post("/api/feedback", json={"category": "bug", "message": "probe"})
    return resp


def test_submit_legacy_id_binds_null_user_id(patched_db):
    """Regression: a legacy/seed session (non-uuid id) must NOT bind its id into
    feedback.user_id. In prod that column is uuid with FK → auth.users(id); a text
    id fails the uuid cast and a profiles-derived uuid violates the FK — both 500.
    So user_id is stored NULL; the legacy id is preserved on the text
    feedback_status.reporter_id for attribution.
    """
    resp = _submit_as({"id": "seed-emp-testingapril", "auth_uuid": None, "is_admin": False})
    assert resp.status_code == 201, resp.text
    rid = resp.json()["report_id"]
    with patched_db.connect() as conn:
        user_id = conn.execute(
            text("SELECT user_id FROM feedback WHERE report_id = :rid"), {"rid": rid}
        ).scalar()
        reporter_id = conn.execute(
            text(
                "SELECT fs.reporter_id FROM feedback f JOIN feedback_status fs "
                "  ON fs.source_id = CAST(f.id AS TEXT) WHERE f.report_id = :rid"
            ),
            {"rid": rid},
        ).scalar()
    assert user_id is None, f"feedback.user_id must be NULL for a legacy id, got {user_id!r}"
    assert reporter_id == "seed-emp-testingapril", "legacy id must remain on reporter_id"


def test_submit_uuid_native_id_binds_user_id(patched_db):
    """A Supabase-native session's id IS the auth.users uuid → bind it to
    feedback.user_id (valid FK, preserves attribution for real users).
    """
    native = "5669fcbe-0145-4133-ba2d-a4fdc0ad6009"
    resp = _submit_as({"id": native, "auth_uuid": native, "is_admin": False})
    assert resp.status_code == 201, resp.text
    rid = resp.json()["report_id"]
    with patched_db.connect() as conn:
        user_id = conn.execute(
            text("SELECT user_id FROM feedback WHERE report_id = :rid"), {"rid": rid}
        ).scalar()
    assert user_id == native, f"uuid-native id must be bound to feedback.user_id, got {user_id!r}"


# ── Reporter status endpoint tests ───────────────────────────────────────────


def _seed_status(engine, *, report_id: str, reporter_id: str, severity: str = "high"):
    """Helper: insert a feedback row + its feedback_status ticket.

    feedback_status is keyed by the feedback uuid, and the /status endpoint
    resolves the reporter's report_id → feedback.id → feedback_status, so the
    seed needs a matching feedback row.
    """
    fid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO feedback (id, page_url, category, message, report_id, created_at) "
                "VALUES (:fid, '/', 'bug', 'seed', :rid, datetime('now'))"
            ),
            {"fid": fid, "rid": report_id},
        )
        conn.execute(
            text(
                "INSERT INTO feedback_status "
                "(stream, source_id, status, severity, area, reporter_id, updated_at) "
                "VALUES ('product', :fid, 'new', :sev, 'api', :rep, datetime('now'))"
            ),
            {"fid": fid, "sev": severity, "rep": reporter_id},
        )


def test_reporter_status_returns_own_ticket(patched_db):
    """GET /api/feedback/{report_id}/status returns the ticket for the owning reporter."""
    rid = f"BUG-{uuid.uuid4().hex[:8]}"
    _seed_status(patched_db, report_id=rid, reporter_id="u-owner")

    client = _make_client("u-owner")
    resp = client.get(f"/api/feedback/{rid}/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["report_id"] == rid
    assert body["status"] == "new"
    assert body["severity"] == "high"
    assert "area" in body
    assert "dispatch_status" in body


def test_reporter_status_404_for_wrong_user(patched_db):
    """GET /api/feedback/{report_id}/status → 404 when caller is not the reporter."""
    rid = f"BUG-{uuid.uuid4().hex[:8]}"
    _seed_status(patched_db, report_id=rid, reporter_id="u-owner")

    client = _make_client("u-intruder")
    resp = client.get(f"/api/feedback/{rid}/status")
    assert resp.status_code == 404


def test_reporter_status_404_for_unknown_report(patched_db):
    """GET /api/feedback/nonexistent/status → 404."""
    client = _make_client("u-nobody")
    resp = client.get("/api/feedback/NOPE-99999999/status")
    assert resp.status_code == 404


def test_reporter_status_requires_auth():
    """GET /api/feedback/{report_id}/status with no auth → 401."""
    app = FastAPI()
    app.include_router(feedback_router_module.router)
    # No override → real get_current_user raises 401 without Authorization header
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/feedback/BUG-12345678/status")
    assert resp.status_code == 401
