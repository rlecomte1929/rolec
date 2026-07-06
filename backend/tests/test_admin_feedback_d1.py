"""TDD tests for D1: expose ticket fields + dispatched filter on GET /api/admin/feedback.

D1 adds:
  - fs.severity, fs.area, fs.dispatch_status, fs.dispatch_ref to the projection
  - ?dispatched=true filter (AND fs.dispatch_status IS NOT NULL)

All tests use in-memory SQLite; no live Postgres required.
"""
from __future__ import annotations

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

# ── Schema — includes all BR-1/BR-2 ticket columns ───────────────────────────

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
  screenshot_data TEXT,
  reporter_email TEXT,
  reporter_name TEXT,
  reporter_role TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,
  email TEXT,
  full_name TEXT,
  role TEXT
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
  status          TEXT NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new','reviewed','acted_on','closed')),
  owner           TEXT,
  resolution      TEXT,
  updated_at      TEXT,
  severity        TEXT,
  area            TEXT,
  reporter_id     TEXT,
  dispatch_ref    TEXT,
  dispatch_status TEXT,
  dispatch_context TEXT,
  dismissed_at TEXT,
  PRIMARY KEY (stream, source_id)
);
CREATE TABLE IF NOT EXISTS hr_feedback (
  id TEXT PRIMARY KEY,
  assignment_id TEXT,
  hr_user_id TEXT,
  employee_user_id TEXT,
  message TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS case_feedback (
  id TEXT PRIMARY KEY,
  case_id TEXT,
  canonical_case_id TEXT,
  assignment_id TEXT,
  author_user_id TEXT,
  author_role TEXT,
  section TEXT,
  message TEXT,
  created_at_ts TEXT
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
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        # Seed base feedback rows
        conn.execute(text(
            "INSERT INTO feedback (id, user_id, page_url, category, message, status, created_at) "
            "VALUES ('f-001', 'u-1', '/dashboard', 'bug', 'Button broken', 'new', '2026-06-01T10:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO feedback (id, user_id, page_url, category, message, status, created_at) "
            "VALUES ('f-002', 'u-2', '/roadmap', 'ui', 'Layout off', 'new', '2026-06-01T09:00:00')"
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


# ── D1-A: ticket fields in projection ────────────────────────────────────────


def test_d1_ticket_fields_present_when_triaged_and_dispatched(db_session):
    """GET returns severity/area/dispatch_status/dispatch_ref for a triaged+dispatched ticket."""
    # Seed a triage row with all ticket fields set
    db_session.execute(text(
        "INSERT INTO feedback_status "
        "(stream, source_id, status, owner, resolution, severity, area, dispatch_status, dispatch_ref, updated_at) "
        "VALUES ('product', 'f-001', 'acted_on', 'alice', 'Dispatched to routine', "
        "'high', 'ui', 'dispatched', 'ref-abc-123', '2026-06-01T14:00:00')"
    ))
    db_session.commit()

    client = _make_client(db_session)
    resp = client.get("/api/admin/feedback?stream=product")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    item = next(r for r in items if r["id"] == "f-001")

    assert item["severity"] == "high", f"expected severity='high', got {item.get('severity')!r}"
    assert item["area"] == "ui", f"expected area='ui', got {item.get('area')!r}"
    assert item["dispatch_status"] == "dispatched", f"expected dispatch_status='dispatched', got {item.get('dispatch_status')!r}"
    assert item["dispatch_ref"] == "ref-abc-123", f"expected dispatch_ref='ref-abc-123', got {item.get('dispatch_ref')!r}"


def test_d1_ticket_fields_null_when_no_status_row(db_session):
    """GET returns null for severity/area/dispatch_status/dispatch_ref when no feedback_status row."""
    client = _make_client(db_session)
    resp = client.get("/api/admin/feedback?stream=product")
    assert resp.status_code == 200
    items = resp.json()["items"]
    item = next(r for r in items if r["id"] == "f-001")

    assert item["severity"] is None
    assert item["area"] is None
    assert item["dispatch_status"] is None
    assert item["dispatch_ref"] is None


# ── D1-B: ?dispatched=true filter ────────────────────────────────────────────


def test_d1_dispatched_filter_returns_only_dispatched(db_session):
    """?dispatched=true returns ONLY rows with dispatch_status IS NOT NULL."""
    # f-001: dispatched
    db_session.execute(text(
        "INSERT INTO feedback_status "
        "(stream, source_id, status, severity, dispatch_status, dispatch_ref, updated_at) "
        "VALUES ('product', 'f-001', 'acted_on', 'medium', 'dispatched', 'ref-xyz', '2026-06-01T14:00:00')"
    ))
    # f-002: triaged but NOT dispatched (dispatch_status NULL)
    db_session.execute(text(
        "INSERT INTO feedback_status "
        "(stream, source_id, status, severity, dispatch_status, updated_at) "
        "VALUES ('product', 'f-002', 'reviewed', 'low', NULL, '2026-06-01T13:00:00')"
    ))
    db_session.commit()

    client = _make_client(db_session)
    resp = client.get("/api/admin/feedback?dispatched=true")
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = {r["id"] for r in items}

    assert "f-001" in ids, "dispatched ticket must be present"
    assert "f-002" not in ids, "non-dispatched ticket must be absent"


def test_d1_no_dispatched_filter_returns_all(db_session):
    """GET without ?dispatched= returns all rows (regression: f-001 + f-002 both present)."""
    db_session.execute(text(
        "INSERT INTO feedback_status "
        "(stream, source_id, status, dispatch_status, updated_at) "
        "VALUES ('product', 'f-001', 'acted_on', 'dispatched', '2026-06-01T14:00:00')"
    ))
    db_session.commit()

    client = _make_client(db_session)
    resp = client.get("/api/admin/feedback")
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = {r["id"] for r in items}
    # Both f-001 and f-002 are feedback rows; both must appear with no filter
    assert "f-001" in ids
    assert "f-002" in ids


def test_d1_dispatched_filter_false_returns_all(db_session):
    """?dispatched=false (falsy) behaves the same as no filter — returns all rows."""
    client = _make_client(db_session)
    resp = client.get("/api/admin/feedback?dispatched=false")
    assert resp.status_code == 200
    # Should not crash and should return rows
    assert resp.json()["count"] >= 1


def test_d1_non_admin_403(db_session):
    """Non-admin cannot GET the dispatched-filter endpoint."""
    client = _make_client(db_session, is_admin=False)
    resp = client.get("/api/admin/feedback?dispatched=true")
    assert resp.status_code == 403
