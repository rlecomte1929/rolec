"""Auth Page Config router — GET /api/public/auth-page-config (anon),
PUT /api/admin/auth-page-config (admin). Supabase client is faked; no network.
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import auth_page_config as apc  # noqa: E402
from backend.app.auth_deps import require_admin  # noqa: E402


class _Result:
    def __init__(self, data=None):
        self.data = data


class _Query:
    def __init__(self, data=None, sink=None):
        self._data, self._sink = data, sink

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def maybe_single(self):
        return self

    def upsert(self, payload, *a, **k):
        if self._sink is not None:
            self._sink.append(payload)
        return self

    def execute(self):
        return _Result(self._data)


class _FakeSB:
    def __init__(self, data=None, sink=None):
        self._data, self._sink = data, sink

    def table(self, _name):
        return _Query(self._data, self._sink)


def _client(admin: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(apc.router)
    if admin:
        app.dependency_overrides[require_admin] = lambda: {
            "id": "admin-1", "auth_uuid": "11111111-1111-1111-1111-111111111111", "is_admin": True,
        }
    return TestClient(app, raise_server_exceptions=False)


def test_get_public_returns_defaults_when_no_row(monkeypatch):
    monkeypatch.setattr(apc, "_get_supabase", lambda: _FakeSB(data=None))
    r = _client().get("/api/public/auth-page-config")
    assert r.status_code == 200
    body = r.json()
    assert body["rotSpeed"] == 1.9 and body["coastColor"] == "#1f8e8b"


def test_get_public_returns_200_even_when_supabase_fails(monkeypatch):
    def _boom():
        raise RuntimeError("supabase down")
    monkeypatch.setattr(apc, "_get_supabase", _boom)
    r = _client().get("/api/public/auth-page-config")
    assert r.status_code == 200, "public auth page must never block on this decorative config"
    assert r.json()["dotCount"] == 2800


def test_get_public_merges_stored_config(monkeypatch):
    monkeypatch.setattr(apc, "_get_supabase", lambda: _FakeSB(data={"config": {"rotSpeed": 5.0, "showArcs": False}}))
    body = _client().get("/api/public/auth-page-config").json()
    assert body["rotSpeed"] == 5.0 and body["showArcs"] is False
    assert body["coastColor"] == "#1f8e8b"  # unspecified field falls back to default


def test_put_requires_admin(monkeypatch):
    monkeypatch.setattr(apc, "_get_supabase", lambda: _FakeSB(sink=[]))
    r = _client(admin=False).put("/api/admin/auth-page-config", json={"rotSpeed": 2.0})
    assert r.status_code in (401, 403)


def test_put_admin_upserts_singleton_and_echoes(monkeypatch):
    sink: list = []
    monkeypatch.setattr(apc, "_get_supabase", lambda: _FakeSB(sink=sink))
    r = _client(admin=True).put("/api/admin/auth-page-config", json={"rotSpeed": 2.5, "dotCount": 1000})
    assert r.status_code == 200, r.text
    assert r.json()["rotSpeed"] == 2.5
    assert len(sink) == 1 and sink[0]["id"] == 1  # singleton row
    assert sink[0]["config"]["dotCount"] == 1000


def test_put_rejects_invalid_hex_color(monkeypatch):
    monkeypatch.setattr(apc, "_get_supabase", lambda: _FakeSB(sink=[]))
    r = _client(admin=True).put("/api/admin/auth-page-config", json={"coastColor": "red"})
    assert r.status_code == 422  # Pydantic hex-pattern validation
