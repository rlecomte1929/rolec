"""Tests for Dispatch → AI Work Queue (context → engineered task → Notion)."""
import os
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.routers import admin_feedback
from backend.app.auth_deps import get_current_user
from backend.app.services import notion_work_queue
from backend.app.services.feedback_task_engineer import status_from_complexity, _parse_task


# ── Pure unit tests ──────────────────────────────────────────────────────────


def test_status_from_complexity():
    assert status_from_complexity("Low") == "Ready for AI"
    assert status_from_complexity("Medium") == "Ready for AI"
    assert status_from_complexity("High") == "Needs Decomposition"
    assert status_from_complexity("Very High") == "Needs Decomposition"
    assert status_from_complexity(None) == "Ready for AI"


_MIN_TASK = ('{"title":"t","strategic_objective":"g","execution_prompt":"p","expected_output":"o",'
             '"validation_criteria":"v","priority":"P1","complexity":"Low","task_type":"Backend Implementation",'
             '"layer":"API","product_area":"Core Product"}')


def test_parse_task_strips_markdown_fences():
    got = _parse_task("```json\n" + _MIN_TASK + "\n```")
    assert got["title"] == "t"
    assert got["priority"] == "P1"


def test_parse_task_raises_on_missing_fields():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        _parse_task('{"title":"only a title"}')


def test_build_properties_maps_fields():
    task = {
        "title": "Fix roadmap 500", "strategic_objective": "why", "execution_prompt": "steps",
        "expected_output": "a fix", "validation_criteria": "tests pass", "test_command": "pytest",
        "priority": "P1", "complexity": "Medium", "task_type": "Backend Implementation",
        "layer": "API", "product_area": "Core Product", "status": "Ready for AI",
    }
    props = notion_work_queue.build_properties(task, failure_evidence="boom", context_links="link")
    assert props["fable"]["title"][0]["text"]["content"] == "Fix roadmap 500"
    assert props["Priority"]["select"]["name"] == "P1"
    assert props["Status"]["select"]["name"] == "Ready for AI"
    assert props["Definition of Ready"]["select"]["name"] == "Vetted — ready"
    assert props["Validation Criteria"]["rich_text"][0]["text"]["content"] == "tests pass"
    assert props["Failure Evidence"]["rich_text"][0]["text"]["content"] == "boom"


def test_build_properties_chunks_long_text():
    props = notion_work_queue.build_properties(
        {"title": "t", "execution_prompt": "x" * 5000}, failure_evidence="", context_links=""
    )
    chunks = props["Execution Prompt"]["rich_text"]
    assert len(chunks) == 3  # 5000 / 1900 → 3 chunks
    assert all(len(c["text"]["content"]) <= 1900 for c in chunks)


def test_create_raises_when_notion_unconfigured(monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    with pytest.raises(notion_work_queue.NotionNotConfigured):
        notion_work_queue.create_work_queue_task({"title": "t"}, failure_evidence="", context_links="")


# ── Endpoint tests ───────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE feedback (
  id TEXT PRIMARY KEY, user_id TEXT, page_url TEXT, category TEXT, message TEXT,
  status TEXT, created_at TEXT, report_id TEXT, screenshot_data TEXT,
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


def _client(db_session):
    app = FastAPI()
    app.include_router(admin_feedback.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "is_admin": True}
    app.dependency_overrides[admin_feedback._get_db] = lambda: db_session
    return TestClient(app)


def test_context_save_and_preview_requires_it(db_session, monkeypatch):
    client = _client(db_session)
    # dispatch_preview reads via its own short-lived SessionLocal (not _get_db) so the
    # DB connection is released before the LLM call — point it at the test engine.
    monkeypatch.setattr(admin_feedback, "SessionLocal", sessionmaker(bind=db_session.get_bind()))

    # preview without context → 400
    resp = client.post("/api/admin/feedback/product/fb-1/dispatch/preview", json={"text": "x", "category": "bug"})
    assert resp.status_code == 400

    # save context
    resp = client.put("/api/admin/feedback/product/fb-1/context", json={"context": "repro: open /journey, roadmap spinner forever"})
    assert resp.status_code == 200

    # preview now works (mock the LLM — engineer_task is synchronous)
    def _fake_engineer(**kwargs):
        assert "repro" in kwargs["admin_context"]
        return {"title": "Fix roadmap", "complexity": "Medium", "status": "Ready for AI",
                "execution_prompt": "do it", "priority": "P1"}
    monkeypatch.setattr(admin_feedback, "engineer_task", _fake_engineer)
    resp = client.post("/api/admin/feedback/product/fb-1/dispatch/preview", json={"text": "roadmap fails", "category": "bug"})
    assert resp.status_code == 200
    assert resp.json()["task"]["title"] == "Fix roadmap"


def test_create_dispatches_via_notion(db_session, monkeypatch):
    client = _client(db_session)
    captured: Dict[str, Any] = {}

    def _fake_create(task, *, failure_evidence, context_links):
        captured["task"] = task
        captured["evidence"] = failure_evidence
        return "https://notion.so/work-queue-page-123"
    monkeypatch.setattr(admin_feedback.notion_work_queue, "create_work_queue_task", _fake_create)

    resp = client.post(
        "/api/admin/feedback/product/fb-1/dispatch/create",
        json={"task": {"title": "Fix roadmap", "priority": "P1", "status": "Ready for AI"}, "confirm": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] is True
    assert body["url"] == "https://notion.so/work-queue-page-123"
    # original message flows into the failure evidence
    assert "roadmap fails to load" in captured["evidence"]
    # feedback_status marked dispatched with the Notion URL, status stays valid
    row = db_session.execute(text(
        "SELECT status, dispatch_status, dispatch_ref FROM feedback_status WHERE stream='product' AND source_id='fb-1'"
    )).fetchone()
    assert row is not None
    assert row[0] == "new"
    assert row[1] == "dispatched"
    assert row[2] == "https://notion.so/work-queue-page-123"


def test_create_is_idempotent_when_already_dispatched(db_session, monkeypatch):
    client = _client(db_session)
    # fb-1 was already dispatched — feedback_status carries a Notion URL.
    db_session.execute(text(
        "INSERT INTO feedback_status (stream, source_id, status, dispatch_status, dispatch_ref) "
        "VALUES ('product', 'fb-1', 'new', 'dispatched', 'https://notion.so/existing-page-999')"
    ))
    db_session.commit()

    calls = {"n": 0}

    def _fake_create(task, *, failure_evidence, context_links):
        calls["n"] += 1
        return "https://notion.so/should-not-be-created"
    monkeypatch.setattr(admin_feedback.notion_work_queue, "create_work_queue_task", _fake_create)

    resp = client.post(
        "/api/admin/feedback/product/fb-1/dispatch/create",
        json={"task": {"title": "Fix roadmap", "priority": "P1", "status": "Ready for AI"}, "confirm": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_exists"] is True
    assert body["notion_url"] == "https://notion.so/existing-page-999"
    # No second Notion task was created.
    assert calls["n"] == 0


def test_create_surfaces_notion_not_configured(db_session, monkeypatch):
    client = _client(db_session)

    def _raise(*a, **k):
        raise notion_work_queue.NotionNotConfigured("NOTION_TOKEN is not set")
    monkeypatch.setattr(admin_feedback.notion_work_queue, "create_work_queue_task", _raise)
    resp = client.post(
        "/api/admin/feedback/product/fb-1/dispatch/create",
        json={"task": {"title": "t"}, "confirm": True},
    )
    assert resp.status_code == 503
