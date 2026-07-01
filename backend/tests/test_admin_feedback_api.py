"""Tests for GET/PATCH /api/admin/feedback (Task 6 — unified feedback console).

All tests use an in-memory SQLite DB. No live Postgres required.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin_feedback  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  page_url TEXT,
  category TEXT DEFAULT 'other',
  message TEXT,
  status TEXT DEFAULT 'new',
  created_at TEXT,
  report_id TEXT,
  screenshot_data TEXT
);
CREATE TABLE IF NOT EXISTS ai_human_feedback (
  id TEXT PRIMARY KEY,
  trace_session_id TEXT,
  reviewer_user_id TEXT,
  verdict TEXT,
  edited_output_json TEXT,
  comment TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS policy_answer_helpfulness (
  id TEXT PRIMARY KEY,
  trace_session_id TEXT,
  company_id TEXT,
  user_id TEXT,
  helpful INTEGER,
  comment TEXT,
  created_at TEXT
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
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT
)
"""


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        # Seed one row per stream
        conn.execute(text(
            "INSERT INTO feedback (id, user_id, page_url, category, message, status, created_at) "
            "VALUES ('f-001', 'u-1', '/dashboard', 'bug', 'Button broken', 'new', '2026-06-01T10:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO ai_human_feedback (id, trace_session_id, reviewer_user_id, verdict, comment, created_at) "
            "VALUES ('h-001', 'trace-001', 'rev-1', 'approved', 'Looks good', '2026-06-01T11:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO policy_answer_helpfulness (id, trace_session_id, company_id, user_id, helpful, comment, created_at) "
            "VALUES ('p-001', 'trace-002', 'co-1', 'emp-1', 1, 'Very helpful', '2026-06-01T12:00:00')"
        ))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_client(db_session, *, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin-1", "is_admin": is_admin}
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def admin_client(db_session):
    return _make_client(db_session, is_admin=True)


@pytest.fixture()
def non_admin_client(db_session):
    return _make_client(db_session, is_admin=False)


# ── GET tests ─────────────────────────────────────────────────────────────────


def test_get_returns_all_streams(admin_client):
    """GET /api/admin/feedback returns normalized rows from ≥2 streams."""
    resp = admin_client.get("/api/admin/feedback")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    streams = {r["stream"] for r in body["items"]}
    assert streams >= {"product", "ai_answers", "helpfulness"}


def test_get_stream_filter(admin_client):
    """GET ?stream=helpfulness returns only helpfulness rows."""
    resp = admin_client.get("/api/admin/feedback?stream=helpfulness")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(r["stream"] == "helpfulness" for r in items)


def test_get_normalized_fields(admin_client):
    """Normalized row has the required fields."""
    resp = admin_client.get("/api/admin/feedback?stream=product")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    for field in ("id", "stream", "source_ref", "text", "verdict", "user_id", "created_at"):
        assert field in item, f"missing field: {field}"


def test_get_left_joins_feedback_status(admin_client, db_session):
    """status/owner/resolution from feedback_status are included (null when no triage)."""
    resp = admin_client.get("/api/admin/feedback?stream=product")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    # No triage yet — status should be None (no row in feedback_status)
    assert item["status"] is None
    assert item["owner"] is None

    # Now seed a triage row and re-query
    db_session.execute(text(
        "INSERT INTO feedback_status (stream, source_id, status, owner, resolution, updated_at) "
        "VALUES ('product', 'f-001', 'reviewed', 'alice', 'Fixed', '2026-06-01T13:00:00')"
    ))
    db_session.commit()
    resp2 = admin_client.get("/api/admin/feedback?stream=product")
    item2 = resp2.json()["items"][0]
    assert item2["status"] == "reviewed"
    assert item2["owner"] == "alice"


def test_get_non_admin_returns_403(non_admin_client):
    """Non-admin gets 403 (require_admin raises 403 Forbidden)."""
    resp = non_admin_client.get("/api/admin/feedback")
    assert resp.status_code == 403


# ── PATCH tests ───────────────────────────────────────────────────────────────


def test_patch_upserts_status(admin_client, db_session):
    """PATCH upserts feedback_status and returns the new state."""
    resp = admin_client.patch(
        "/api/admin/feedback/product/f-001",
        json={"status": "reviewed", "owner": "bob", "resolution": "Will fix"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reviewed"
    assert body["stream"] == "product"
    assert body["id"] == "f-001"

    # Verify persisted in DB
    row = db_session.execute(
        text("SELECT status, owner, resolution FROM feedback_status WHERE stream='product' AND source_id='f-001'")
    ).fetchone()
    assert row is not None
    assert row[0] == "reviewed"
    assert row[1] == "bob"
    assert row[2] == "Will fix"


def test_patch_writes_audit_row(admin_client, db_session):
    """PATCH writes a feedback_triaged audit log row."""
    admin_client.patch(
        "/api/admin/feedback/helpfulness/p-001",
        json={"status": "acted_on"},
    )
    rows = db_session.execute(text("SELECT new_value_json FROM audit_logs")).fetchall()
    assert len(rows) >= 1
    events = [json.loads(r[0])["event"] for r in rows if r[0]]
    assert "feedback_triaged" in events


def test_patch_upsert_overwrites(admin_client, db_session):
    """Second PATCH overwrites the first (upsert semantics)."""
    admin_client.patch("/api/admin/feedback/product/f-001", json={"status": "reviewed"})
    admin_client.patch("/api/admin/feedback/product/f-001", json={"status": "closed"})
    row = db_session.execute(
        text("SELECT status FROM feedback_status WHERE stream='product' AND source_id='f-001'")
    ).fetchone()
    assert row[0] == "closed"


def test_patch_invalid_status_400(admin_client):
    """Invalid status value → 400."""
    resp = admin_client.patch(
        "/api/admin/feedback/product/f-001",
        json={"status": "bogus"},
    )
    assert resp.status_code == 400


def test_patch_non_admin_returns_403(non_admin_client):
    """Non-admin PATCH → 403 (require_admin raises 403 Forbidden)."""
    resp = non_admin_client.patch(
        "/api/admin/feedback/product/f-001",
        json={"status": "reviewed"},
    )
    assert resp.status_code == 403
