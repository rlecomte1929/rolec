"""Tests for feedback pipeline state writers (Task 4):
dispatch/preview stamps `spec_drafted`; dispatch/create stamps `dispatched`
+ join key (`notion_task_id`) + `autonomy_tier`.
"""
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.routers import admin_feedback
from backend.app.auth_deps import get_current_user


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
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "is_admin": True}
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    # dispatch_preview reads/writes via its own short-lived SessionLocal (not _get_db) so
    # the DB connection is released before the LLM call — point it at the test engine.
    monkeypatch.setattr(admin_feedback, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    return TestClient(app)


@pytest.fixture()
def seed_item(db_session):
    return "fb-1"


def _fetch_feedback_status(db_session, item_id):
    row = db_session.execute(text(
        "SELECT dispatch_status, spec_drafted_at, dispatched_at, notion_task_id, autonomy_tier "
        "FROM feedback_status WHERE stream='product' AND source_id=:id"
    ), {"id": item_id}).fetchone()
    assert row is not None
    return dict(zip(
        ["dispatch_status", "spec_drafted_at", "dispatched_at", "notion_task_id", "autonomy_tier"], row
    ))


def test_preview_stamps_spec_drafted(client, db_session, seed_item, monkeypatch):
    # context is required before preview
    resp = client.put(
        f"/api/admin/feedback/product/{seed_item}/context",
        json={"context": "repro: open /journey, roadmap spinner forever"},
    )
    assert resp.status_code == 200
    # The `_get_db` override hands the raw test Session to the route (bypassing the
    # generator's own commit), and dispatch_preview's short-lived SessionLocal() shares
    # the same StaticPool connection — closing it rolls back any *uncommitted* work on
    # that shared connection. Commit explicitly so the context write survives.
    db_session.commit()

    def _fake_engineer(**kwargs):
        return {"title": "Fix roadmap", "complexity": "Medium", "status": "Ready for AI",
                "execution_prompt": "do it", "priority": "P1", "autonomy_tier": "green"}
    monkeypatch.setattr(admin_feedback, "engineer_task", _fake_engineer)

    resp = client.post(
        f"/api/admin/feedback/product/{seed_item}/dispatch/preview",
        json={"text": "roadmap fails", "category": "bug"},
    )
    assert resp.status_code == 200, resp.text

    row = _fetch_feedback_status(db_session, seed_item)
    assert row["dispatch_status"] == "spec_drafted"
    assert row["spec_drafted_at"] is not None


def test_create_stamps_dispatched_and_join_key(client, db_session, seed_item, monkeypatch):
    def _fake_create(task, *, failure_evidence, context_links):
        return "https://www.notion.so/Task-0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(admin_feedback.notion_work_queue, "create_work_queue_task", _fake_create)

    task = {"title": "t", "priority": "P1", "status": "Ready for AI", "autonomy_tier": "yellow"}
    resp = client.post(
        f"/api/admin/feedback/product/{seed_item}/dispatch/create",
        json={"task": task, "confirm": True},
    )
    assert resp.status_code == 200, resp.text

    row = _fetch_feedback_status(db_session, seed_item)
    assert row["dispatch_status"] == "dispatched"
    assert row["dispatched_at"] is not None
    assert row["autonomy_tier"] == "yellow"
    assert row["notion_task_id"] == "0123456789abcdef0123456789abcdef"  # dashless lower
