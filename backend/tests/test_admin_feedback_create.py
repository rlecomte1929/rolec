"""AIQ-1492 — POST /api/admin/feedback (admin authors a dispatch-ready feedback item).

Verifies: admin-only; returns the new id; the item appears in the Inbox (GET /feedback);
and feedback_status.dispatch_context is persisted at creation — the exact invariant
dispatch/preview's 400-on-empty-context check reads, so the item is immediately
dispatch-ready. (dispatch/preview itself opens a real SessionLocal + calls the LLM, so it
is not exercised end-to-end in the SQLite harness.)
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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY, user_id TEXT, page_url TEXT, category TEXT DEFAULT 'other',
  message TEXT, status TEXT DEFAULT 'new', created_at TEXT, report_id TEXT,
  screenshot_data TEXT, screenshot_url TEXT,
  reporter_email TEXT, reporter_name TEXT, reporter_role TEXT, client_context TEXT
);
CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, email TEXT, full_name TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS ai_human_feedback (
  id TEXT PRIMARY KEY, trace_session_id TEXT, reviewer_user_id TEXT, verdict TEXT,
  edited_output_json TEXT, comment TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS policy_answer_helpfulness (
  id TEXT PRIMARY KEY, trace_session_id TEXT, company_id TEXT, user_id TEXT,
  helpful INTEGER, comment TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS feedback_status (
  stream TEXT NOT NULL, source_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','reviewed','acted_on','closed')),
  owner TEXT, resolution TEXT, updated_at TEXT, severity TEXT, area TEXT, reporter_id TEXT,
  dispatch_ref TEXT, dispatch_status TEXT, dispatch_context TEXT, autonomy_tier TEXT, dismissed_at TEXT,
  PRIMARY KEY (stream, source_id)
);
CREATE TABLE IF NOT EXISTS hr_feedback (id TEXT PRIMARY KEY, assignment_id TEXT, hr_user_id TEXT, employee_user_id TEXT, message TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS case_feedback (id TEXT PRIMARY KEY, case_id TEXT, canonical_case_id TEXT, assignment_id TEXT, author_user_id TEXT, author_role TEXT, section TEXT, message TEXT, created_at_ts TEXT);
CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, action_type TEXT NOT NULL, old_value_json TEXT, new_value_json TEXT, actor_type TEXT NOT NULL, actor_id TEXT, created_at TEXT)
"""


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        for stmt in _SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_client(db_session, *, is_admin: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-admin-1", "is_admin": is_admin, "email": "admin@acme.com",
        "name": "Ada Admin", "role": "ADMIN",
    }
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    return TestClient(app)


def _body(**over):
    b = {
        "page_url": "/admin/dashboard",
        "category": "bug",
        "message": "Sidebar count is wrong on the HR command center",
        "dispatch_context": "Repro: open /hr, note the badge shows 0 while 3 cases exist.",
        "severity": "medium",
        "area": "api",
    }
    b.update(over)
    return b


def test_create_returns_201_with_id(db_session):
    resp = _make_client(db_session).post("/api/admin/feedback", json=_body())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data.get("id")
    assert data.get("report_id", "").startswith("BUG-")


def test_create_non_admin_403(db_session):
    resp = _make_client(db_session, is_admin=False).post("/api/admin/feedback", json=_body())
    assert resp.status_code == 403


def test_created_item_appears_in_inbox(db_session):
    client = _make_client(db_session)
    new_id = client.post("/api/admin/feedback", json=_body(message="UNIQUE-MARKER-XYZ")).json()["id"]
    items = client.get("/api/admin/feedback").json()["items"]
    match = [i for i in items if str(i.get("id")) == new_id or "UNIQUE-MARKER-XYZ" in (i.get("message") or "")]
    assert match, f"new item {new_id} not in inbox"


def test_created_item_is_dispatch_ready(db_session):
    """feedback_status.dispatch_context is written at creation → dispatch/preview's
    400-on-empty-context check passes with no extra step."""
    new_id = _make_client(db_session).post("/api/admin/feedback", json=_body()).json()["id"]
    row = db_session.execute(
        text("SELECT dispatch_context, severity, area FROM feedback_status "
             "WHERE stream = 'product' AND source_id = :id"),
        {"id": new_id},
    ).fetchone()
    assert row is not None, "no feedback_status row created"
    assert (row[0] or "").strip(), "dispatch_context empty — item is NOT dispatch-ready"
    assert row[1] == "medium" and row[2] == "api"


def test_empty_context_400(db_session):
    resp = _make_client(db_session).post("/api/admin/feedback", json=_body(dispatch_context="   "))
    assert resp.status_code == 400


def test_no_screenshot_still_succeeds(db_session):
    resp = _make_client(db_session).post("/api/admin/feedback", json=_body(screenshot_data=None))
    assert resp.status_code == 201, resp.text


def test_severity_area_derived_when_omitted(db_session):
    """Omitting severity/area falls back to classify() — still dispatch-ready."""
    new_id = _make_client(db_session).post(
        "/api/admin/feedback",
        json={"page_url": "/x", "category": "bug", "message": "crash on save",
              "dispatch_context": "steps: click save"},
    ).json()["id"]
    row = db_session.execute(
        text("SELECT severity, area FROM feedback_status WHERE source_id = :id"), {"id": new_id},
    ).fetchone()
    assert row[0] and row[1], "classify() did not populate severity/area"
