"""Fix-trigger layer on the admin feedback console — Trigger fix + Auto-attempt.

Mounts the prod app (backend.main:app) so the test also proves the endpoints are
registered there. The DB session, Notion, and the autofix Edge Function are all faked
so no network/DB is touched; auth is overridden per the app-mounted harness.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ["FEEDBACK_FIX_TRIGGER_ENABLED"] = "1"

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import admin_feedback as af
from backend.app.services import notion_work_queue as nwq

_ADMIN = {"id": "admin-1", "role": "ADMIN", "is_admin": True}

# A dispatched row's (dispatch_ref, dispatch_status). The URL ends in a 32-char hex id.
_DISPATCHED = ("https://www.notion.so/Fix-the-thing-0123456789abcdef0123456789abcdef", "dispatched")
_PAGE_ID = "01234567-89ab-cdef-0123-456789abcdef"

# Mutable holder so each test can set the feedback_status row the fake DB returns.
_STATE: dict = {"row": _DISPATCHED}


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeSession:
    def execute(self, *_a, **_k):
        return _FakeResult(_STATE["row"])

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
    _STATE["row"] = _DISPATCHED
    monkeypatch.setattr(af, "record_admin_event", lambda *a, **k: None)
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _ADMIN
    app.dependency_overrides[af._get_db] = _fake_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(auth_deps.get_current_user, None)
    app.dependency_overrides.pop(af._get_db, None)


# ── page-id parsing (pure) ──────────────────────────────────────────────────────

def test_page_id_from_ref():
    assert nwq.page_id_from_ref(_DISPATCHED[0]) == _PAGE_ID
    assert nwq.page_id_from_ref("https://notion.so/0123456789abcdef0123456789abcdef") == _PAGE_ID
    assert nwq.page_id_from_ref(None) is None
    assert nwq.page_id_from_ref("https://notion.so/no-id-here") is None


# ── wiring ──────────────────────────────────────────────────────────────────────

def test_routes_registered_in_prod_app():
    paths = {r.path for r in app.routes}
    assert "/api/admin/feedback/{stream}/{item_id}/fix" in paths
    assert "/api/admin/feedback/{stream}/{item_id}/auto-attempt" in paths


def test_flag_off_returns_404(client, monkeypatch):
    monkeypatch.setenv("FEEDBACK_FIX_TRIGGER_ENABLED", "false")
    r = client.post("/api/admin/feedback/product/abc/fix")
    assert r.status_code == 404


# ── Trigger fix ─────────────────────────────────────────────────────────────────

def test_trigger_fix_flips_status_and_returns_command(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(nwq, "get_task_meta",
                        lambda pid: {"status": "Needs Decomposition", "complexity": "Low",
                                     "autonomy_tier": "🟡 Yellow", "aiq_id": "AIQ-77", "url": "u"})
    monkeypatch.setattr(nwq, "set_task_status",
                        lambda pid, status, notes=None: seen.update(pid=pid, status=status))
    r = client.post("/api/admin/feedback/product/abc/fix")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["skill"] == "relopass-dev-queue"
    assert body["command"] == "/relopass-dev-queue AIQ-77"
    assert seen == {"pid": _PAGE_ID, "status": "Ready for AI"}


def test_trigger_fix_requires_dispatch_first(client):
    _STATE["row"] = None  # no feedback_status row → not dispatched
    r = client.post("/api/admin/feedback/product/abc/fix")
    assert r.status_code == 409


# ── Auto-attempt ────────────────────────────────────────────────────────────────

def test_auto_attempt_rejects_red_or_complex(client, monkeypatch):
    monkeypatch.setattr(nwq, "get_task_meta",
                        lambda pid: {"complexity": "High", "autonomy_tier": "🔴 Red — full human gate",
                                     "aiq_id": "AIQ-9", "url": "u"})
    r = client.post("/api/admin/feedback/product/abc/auto-attempt")
    assert r.status_code == 422


def test_auto_attempt_fires_pipeline_for_trivial_green(client, monkeypatch):
    monkeypatch.setattr(nwq, "get_task_meta",
                        lambda pid: {"complexity": "Trivial", "autonomy_tier": "🟢 Green — auto",
                                     "aiq_id": "AIQ-9", "url": "u"})
    fired = {}

    def _fake_invoke(pid):
        fired["pid"] = pid
        return {"pipeline": {"ok": True}}

    monkeypatch.setattr(af, "_invoke_autofix_pipeline", _fake_invoke)
    r = client.post("/api/admin/feedback/product/abc/auto-attempt")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "dispatched"
    assert fired["pid"] == _PAGE_ID
