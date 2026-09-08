"""Tests for the feedback pipeline state machine (Task 6):
validate_transition/timestamp_column pure logic + the PATCH /state endpoint.
"""
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.services.feedback_state_machine import validate_transition
from backend.app.routers import admin_feedback
from backend.app.auth_deps import get_current_user


def test_legal_transition():
    assert validate_transition("dispatched", "in_progress") is True


def test_illegal_jump():
    assert validate_transition("new", "deployed") is False


def test_terminal_is_dead_end():
    assert validate_transition("done", "in_progress") is False


def test_none_treated_as_new():
    assert validate_transition(None, "triaged") is True


# ── PATCH /state endpoint (app-mounted harness) ───────────────────────────────

_SCHEMA = """
CREATE TABLE feedback (
  id TEXT PRIMARY KEY, user_id TEXT, page_url TEXT, category TEXT, message TEXT,
  status TEXT, created_at TEXT, report_id TEXT, screenshot_data TEXT, screenshot_url TEXT,
  reporter_email TEXT, reporter_name TEXT, reporter_role TEXT, client_context TEXT
);
CREATE TABLE feedback_status (
  stream TEXT NOT NULL, source_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','reviewed','acted_on','closed')),
  owner TEXT, resolution TEXT, updated_at TEXT, severity TEXT, area TEXT,
  reporter_id TEXT, dispatch_ref TEXT, dispatch_status TEXT, dispatch_context TEXT, dismissed_at TEXT,
  notion_task_id TEXT, autonomy_tier TEXT, spec_drafted_at TEXT, dispatched_at TEXT,
  triaged_at TEXT, in_progress_at TEXT, deployed_at TEXT, done_at TEXT,
  pr_url TEXT, pr_number INTEGER, branch_name TEXT,
  PRIMARY KEY (stream, source_id)
);
"""


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as c:
        for stmt in _SCHEMA.strip().split(";"):
            if stmt.strip():
                c.execute(text(stmt))
        c.execute(text(
            "INSERT INTO feedback (id, page_url, category, message, status, created_at, report_id) "
            "VALUES ('fb-1', '/journey', 'bug', 'roadmap fails to load', 'new', '2026-07-01T10:00:00', 'BUG-1')"
        ))
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "is_admin": True}
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    return TestClient(app)


def _dispatch_status(db_session, item_id):
    row = db_session.execute(text(
        "SELECT dispatch_status FROM feedback_status WHERE stream='product' AND source_id=:id"
    ), {"id": item_id}).fetchone()
    return row[0] if row else None


def test_endpoint_legal_transition_from_absent_row(client, db_session):
    resp = client.patch("/api/admin/feedback/product/fb-1/state", json={"target": "triaged"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "dispatch_status": "triaged"}
    row = db_session.execute(text(
        "SELECT dispatch_status, triaged_at FROM feedback_status WHERE stream='product' AND source_id='fb-1'"
    )).fetchone()
    assert row[0] == "triaged"
    assert row[1] is not None


def test_endpoint_illegal_transition_returns_409(client, db_session):
    db_session.execute(text(
        "INSERT INTO feedback_status (stream, source_id, status, dispatch_status) "
        "VALUES ('product', 'fb-1', 'new', 'new')"
    ))
    db_session.commit()
    resp = client.patch("/api/admin/feedback/product/fb-1/state", json={"target": "deployed"})
    assert resp.status_code == 409
    assert _dispatch_status(db_session, "fb-1") == "new"


def test_endpoint_unknown_target_returns_422(client):
    resp = client.patch("/api/admin/feedback/product/fb-1/state", json={"target": "bogus"})
    assert resp.status_code == 422


def test_endpoint_updates_existing_row(client, db_session):
    db_session.execute(text(
        "INSERT INTO feedback_status (stream, source_id, status, dispatch_status) "
        "VALUES ('product', 'fb-1', 'new', 'dispatched')"
    ))
    db_session.commit()
    resp = client.patch("/api/admin/feedback/product/fb-1/state", json={"target": "in_progress"})
    assert resp.status_code == 200, resp.text
    row = db_session.execute(text(
        "SELECT dispatch_status, in_progress_at FROM feedback_status WHERE stream='product' AND source_id='fb-1'"
    )).fetchone()
    assert row[0] == "in_progress"
    assert row[1] is not None
