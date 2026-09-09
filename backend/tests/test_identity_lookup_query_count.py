"""WS2 Task 2.7 — identity lookup query count, cache bypass, logout eviction.

Recording stub pattern matches ``test_employee_policy_caps_query_count.py``.
Auth is NOT overridden: these tests exercise ``auth_deps.get_current_user``.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import backend.app.auth_deps as auth_deps
import backend.app.routers.auth as auth_router
from backend.app.auth_deps import get_current_user, reset_identity_caches_for_tests
from backend.main import app as prod_app

TOKEN = "tok-identity-ws27"
USER_ID = "11111111-1111-1111-1111-111111111111"

IDENTITY_METHODS = {
    "get_user_context_by_token",
    "get_user_by_token",
    "get_user_by_id",
    "get_user_roles",
    "ensure_profile_record",
    "get_admin_session",
    "get_profile_record",
    "get_profile_by_email",
    "is_admin_allowlisted",
}

USER = {
    "id": USER_ID,
    "email": "admin@example.test",
    "role": "ADMIN",
    "name": "Ada Admin",
    "username": "ada",
}


class RecordingIdentityDb:
    """Stub db whose identity methods record their names."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.token_valid = True
        self.admin_session = None

    def _rec(self, name: str) -> None:
        self.calls.append(name)

    def identity_calls(self) -> list[str]:
        return [c for c in self.calls if c in IDENTITY_METHODS]

    def get_user_context_by_token(self, token: str):
        self._rec("get_user_context_by_token")
        if not self.token_valid or token != TOKEN:
            return None
        return {**USER, "role_rows": [{"role": "ADMIN", "is_primary": True}]}

    def get_user_by_token(self, token: str):
        self._rec("get_user_by_token")
        if not self.token_valid or token != TOKEN:
            return None
        return dict(USER)

    def get_user_by_id(self, user_id: str):
        self._rec("get_user_by_id")
        if str(user_id) == USER_ID:
            return dict(USER)
        return None

    def get_user_roles(self, user_id: str):
        self._rec("get_user_roles")
        return [{"role": "ADMIN", "is_primary": True}]

    def ensure_profile_record(self, **kwargs):
        self._rec("ensure_profile_record")

    def get_admin_session(self, token: str):
        self._rec("get_admin_session")
        return self.admin_session

    def get_profile_record(self, user_id):
        self._rec("get_profile_record")
        return None

    def get_profile_by_email(self, email):
        self._rec("get_profile_by_email")
        return None

    def is_admin_allowlisted(self, email):
        self._rec("is_admin_allowlisted")
        return False

    def delete_session_by_token(self, token: str) -> bool:
        self._rec("delete_session_by_token")
        return True

    def mark_welcome_seen(self, user_id: str) -> bool:
        self._rec("mark_welcome_seen")
        return True


_ping_app = FastAPI()


@_ping_app.get("/api/ping-identity")
def ping_identity(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "roles": user.get("roles")}


def _install(monkeypatch, rec: RecordingIdentityDb) -> None:
    reset_identity_caches_for_tests()
    monkeypatch.setattr(auth_deps, "db", rec)
    monkeypatch.setattr(auth_router, "db", rec)


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_identity_query_count_first_then_cached(monkeypatch):
    rec = RecordingIdentityDb()
    _install(monkeypatch, rec)
    client = TestClient(_ping_app)

    first = client.get("/api/ping-identity", headers=_auth_headers())
    assert first.status_code == 200, first.text
    first_identity = rec.identity_calls()
    assert "get_user_by_token" not in first_identity, first_identity
    assert "get_user_by_id" not in first_identity, first_identity
    assert "get_user_roles" not in first_identity, first_identity
    assert first_identity.count("get_user_context_by_token") == 1, first_identity
    assert len(first_identity) <= 3, first_identity

    rec.calls.clear()
    second = client.get("/api/ping-identity", headers=_auth_headers())
    assert second.status_code == 200, second.text
    assert rec.identity_calls() == [], rec.calls


def test_revoked_session_rejected_on_auth_prefix_within_ttl(monkeypatch):
    rec = RecordingIdentityDb()
    _install(monkeypatch, rec)
    ping_client = TestClient(_ping_app)
    assert ping_client.get("/api/ping-identity", headers=_auth_headers()).status_code == 200

    rec.token_valid = False
    rec.calls.clear()
    auth_client = TestClient(prod_app)
    response = auth_client.post("/api/auth/welcome-seen", headers=_auth_headers())
    assert response.status_code == 401, response.text
    assert "get_user_context_by_token" in rec.identity_calls(), rec.calls


def test_logout_evicts_token_from_identity_cache(monkeypatch):
    rec = RecordingIdentityDb()
    _install(monkeypatch, rec)
    ping_client = TestClient(_ping_app)
    auth_client = TestClient(prod_app)

    assert ping_client.get("/api/ping-identity", headers=_auth_headers()).status_code == 200
    rec.calls.clear()
    logout = auth_client.post("/api/auth/logout", headers=_auth_headers())
    assert logout.status_code == 200, logout.text

    rec.calls.clear()
    again = ping_client.get("/api/ping-identity", headers=_auth_headers())
    assert again.status_code == 200, again.text
    assert "get_user_context_by_token" in rec.identity_calls(), rec.calls
