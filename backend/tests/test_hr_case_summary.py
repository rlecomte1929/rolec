"""AIQ-1697 — HR AI case summary proxy endpoint.

Pins the tenant-safe proxy contract WITHOUT calling the real Edge Function:
  * the caller's company_id (from get_org_id_for_hr_user) — NOT any client value — is
    what gets forwarded to the function (the isolation property at this layer),
  * a function 404 (unknown / wrong-company case) maps to 404,
  * a non-HR caller is rejected 403 (dependency), never reaching the function,
  * unconfigured env → 503.

The router is mounted in a bare app; `requests.post` and the auth dependency are patched.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.routers import hr_case_summary as mod
from backend.app.auth_deps import get_org_id_for_hr_user

ASSIGNMENT = "assign-1"
HR_COMPANY = "company-A"


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload

    def json(self):
        return self._p


def _client(monkeypatch, *, company=HR_COMPANY, post=None, env=True):
    if env:
        monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    else:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    if post is not None:
        monkeypatch.setattr(mod.requests, "post", post)

    app = FastAPI()
    app.include_router(mod.router)
    # Simulate an authenticated HR user resolving to HR_COMPANY.
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: company
    return TestClient(app)


def test_hr_gets_summary_scoped_to_own_company(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers.get("Authorization")
        return _Resp(200, {"assignment_id": ASSIGNMENT, "company_id": HR_COMPANY,
                           "summary": {"status": "Active.", "blockers": [], "next_actions": [], "cost_variance": "not recorded"}})

    r = _client(monkeypatch, post=fake_post).get(f"/api/hr/cases/{ASSIGNMENT}/ai-summary")
    assert r.status_code == 200
    assert r.json()["summary"]["status"] == "Active."
    # The forwarded company_id is the caller's OWN company, not a client-supplied value.
    assert captured["json"] == {"assignment_id": ASSIGNMENT, "company_id": HR_COMPANY}
    assert captured["url"].endswith("/functions/v1/case-summary")
    assert captured["auth"] == "Bearer svc-key"


def test_function_404_maps_to_404(monkeypatch):
    # Case outside the caller's company (or unknown) → the function 404s → we 404.
    post = lambda *a, **k: _Resp(404, {"error": "Case not found"})
    r = _client(monkeypatch, post=post).get(f"/api/hr/cases/{ASSIGNMENT}/ai-summary")
    assert r.status_code == 404


def test_function_502_maps_to_502(monkeypatch):
    post = lambda *a, **k: _Resp(502, {"error": "Summary generation failed"})
    r = _client(monkeypatch, post=post).get(f"/api/hr/cases/{ASSIGNMENT}/ai-summary")
    assert r.status_code == 502


def test_non_hr_caller_is_forbidden(monkeypatch):
    # A caller who is not HR/Admin: the dependency raises 403 before any function call.
    def deny():
        raise HTTPException(status_code=403, detail="Admin or HR only")

    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    called = {"n": 0}
    monkeypatch.setattr(mod.requests, "post", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[get_org_id_for_hr_user] = deny
    r = TestClient(app).get(f"/api/hr/cases/{ASSIGNMENT}/ai-summary")
    assert r.status_code == 403
    assert called["n"] == 0  # never reached the edge function


def test_unconfigured_env_returns_503(monkeypatch):
    r = _client(monkeypatch, env=False).get(f"/api/hr/cases/{ASSIGNMENT}/ai-summary")
    assert r.status_code == 503
