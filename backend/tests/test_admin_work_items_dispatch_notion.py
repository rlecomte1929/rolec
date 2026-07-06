"""
Work board → Notion dispatch (the single, sanctioned dispatch engine). Covers the
plan-folding helper and the endpoint's orchestration + error mapping (engineer_task
failure → 502, Notion-not-configured → 503, Notion API error → 502, success → url).

Uses a light fake engine so the test doesn't depend on Postgres `now()` (SQLite lacks
it) — the endpoint's SQL is exercised for shape, the DB write is a no-op.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import admin_work_items
from backend.app.auth_deps import require_admin
from backend.app.services import notion_work_queue
from backend.app.routers.admin_work_items import _plan_context


# ── Pure helper ───────────────────────────────────────────────────────────────


def test_plan_context_empty_when_no_plan():
    assert _plan_context({}) == ""


def test_plan_context_folds_plan_fields():
    ctx = _plan_context({
        "summary": "Fix the roadmap 500", "approach": "guard the query",
        "test_plan": "pytest x", "affected_files": ["a.py", "b.py"],
    })
    assert "Plan summary: Fix the roadmap 500" in ctx
    assert "Approach: guard the query" in ctx
    assert "Test plan: pytest x" in ctx
    assert "Affected files: a.py, b.py" in ctx


# ── Endpoint orchestration (fake engine) ──────────────────────────────────────


class _Result:
    def __init__(self, row): self._row = row
    def mappings(self): return self
    def first(self): return self._row


class _Conn:
    def __init__(self, row): self.row = row; self.executed = []
    def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        return _Result(self.row if "SELECT" in str(stmt).upper() else None)


class _Begin:
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self.conn
    def __exit__(self, *a): return False


class _Engine:
    def __init__(self, row): self.conn = _Conn(row)
    def begin(self): return _Begin(self.conn)


_ITEM = {
    "id": "wi-1", "title": "Roadmap 500", "body": "spinner forever",
    "source_url": "/journey", "kind": "bug", "priority": "P1",
    "triage_json": {"rationale": "bug/P1"}, "plan_json": None,
}


def _client(monkeypatch, row: Optional[Dict[str, Any]] = _ITEM) -> TestClient:
    monkeypatch.setattr(admin_work_items.db, "engine", _Engine(row))
    app = FastAPI()
    app.include_router(admin_work_items.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "is_admin": True}
    return TestClient(app)


def test_dispatch_notion_success(monkeypatch):
    client = _client(monkeypatch)
    captured: Dict[str, Any] = {}

    def _fake_engineer(**kwargs):
        captured["kwargs"] = kwargs
        return {"title": "Fix roadmap 500", "priority": "P1", "status": "Ready for AI"}
    monkeypatch.setattr(admin_work_items, "engineer_task", _fake_engineer)
    monkeypatch.setattr(
        admin_work_items.notion_work_queue, "create_work_queue_task",
        lambda task, *, failure_evidence, context_links: "https://notion.so/page-123",
    )

    resp = client.post("/api/admin/work-items/wi-1/dispatch-notion", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["url"] == "https://notion.so/page-123"
    # the demand's own text + category flow into the task engineer
    assert captured["kwargs"]["text"] == "spinner forever"
    assert captured["kwargs"]["category"] == "bug"


def test_dispatch_notion_missing_item_404(monkeypatch):
    client = _client(monkeypatch, row=None)
    resp = client.post("/api/admin/work-items/nope/dispatch-notion", json={})
    assert resp.status_code == 404


def test_dispatch_notion_engineer_failure_502(monkeypatch):
    client = _client(monkeypatch)

    def _boom(**kwargs):
        raise ValueError("model returned junk")
    monkeypatch.setattr(admin_work_items, "engineer_task", _boom)
    resp = client.post("/api/admin/work-items/wi-1/dispatch-notion", json={})
    assert resp.status_code == 502
    assert "draft the task" in resp.json()["detail"].lower()


def test_dispatch_notion_not_configured_503(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_work_items, "engineer_task", lambda **k: {"title": "t"})

    def _raise(*a, **k):
        raise notion_work_queue.NotionNotConfigured("NOTION_TOKEN is not set")
    monkeypatch.setattr(admin_work_items.notion_work_queue, "create_work_queue_task", _raise)
    resp = client.post("/api/admin/work-items/wi-1/dispatch-notion", json={})
    assert resp.status_code == 503


def test_dispatch_notion_api_error_502(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(admin_work_items, "engineer_task", lambda **k: {"title": "t"})

    def _raise(*a, **k):
        raise notion_work_queue.NotionApiError("Notion API 400: bad")
    monkeypatch.setattr(admin_work_items.notion_work_queue, "create_work_queue_task", _raise)
    resp = client.post("/api/admin/work-items/wi-1/dispatch-notion", json={})
    assert resp.status_code == 502
