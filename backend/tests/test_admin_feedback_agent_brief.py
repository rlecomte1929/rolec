"""Copyable Cursor/dev-queue brief — no Notion status flip."""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import admin_feedback as af

_ADMIN = {"id": "admin-1", "role": "ADMIN", "is_admin": True}
_REPLAY = "https://eu.posthog.com/replay/sess-xyz"


def test_build_agent_brief_includes_replay_and_merge_fence():
    out = af.build_agent_brief(
        report_id="BUG-x",
        stream="product",
        item_id="abc",
        reporter_text="Button is broken",
        dispatch_context="fails on save",
        diagnostics=af.format_diagnostics(
            {
                "posthog_id": "user-abc",
                "posthog_session_id": "sess-xyz",
                "posthog_replay_url": _REPLAY,
                "route": "/admin/countries",
            }
        ),
        notion_url="https://www.notion.so/page",
    )
    assert _REPLAY in out["brief"]
    assert "Do not merge to main" in out["brief"]
    assert "Button is broken" in out["brief"]
    assert "fails on save" in out["brief"]
    assert out["notion_url"] == "https://www.notion.so/page"
    assert out["command"] == "Work this ticket in Cursor"


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeSession:
    def execute(self, *_a, **_k):
        return _FakeResult(("admin notes", "https://www.notion.so/Fix-AIQ-99-deadbeefdeadbeefdeadbeefdeadbeef"))

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _fake_get_db():
    yield _FakeSession()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(
        af,
        "_load_product_fields",
        lambda _db, _id: {
            "message": "Button is broken",
            "category": "bug",
            "page_url": "/admin/countries",
            "has_screenshot": False,
            "reporter_name": "Ada",
            "report_id": "BUG-x",
            "client_context": {
                "posthog_replay_url": _REPLAY,
                "posthog_id": "user-abc",
                "posthog_session_id": "sess-xyz",
                "route": "/admin/countries",
            },
        },
    )
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _ADMIN
    app.dependency_overrides[af._get_db] = _fake_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(auth_deps.get_current_user, None)
    app.dependency_overrides.pop(af._get_db, None)


def test_agent_brief_route_registered():
    paths = {r.path for r in app.routes}
    assert "/api/admin/feedback/{stream}/{item_id}/agent-brief" in paths


def test_agent_brief_http_does_not_require_fix_flag(client):
    r = client.post("/api/admin/feedback/product/abc/agent-brief")
    assert r.status_code == 200, r.text
    body = r.json()
    assert _REPLAY in body["brief"]
    assert "Do not merge to main" in body["brief"]
    assert body["report_id"] == "BUG-x"
    assert "AIQ-99" in body["command"]
