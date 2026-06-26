"""
[AIQ-1239] Tests for POST /api/auth/exchange-supabase-token.

The endpoint bridges a verified Supabase Auth JWT (passkey / WebAuthn, OAuth)
to a ReloPass session token. These pin the contract:

  1. Valid Supabase JWT + matching ReloPass user  → 200, session token issued.
  2. Invalid / tampered token                      → 401, no session.
  3. Valid token but no ReloPass user for the email → 401 (never auto-provisions).
  4. SUPABASE_JWT_SECRET unset                      → 503 (fail-closed).

The db layer is patched at the router module level (no live DB), mirroring
test_auth_register.py.
"""
from __future__ import annotations

import os
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import jwt as _pyjwt  # noqa: E402  (PyJWT — already a backend dependency)
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

_SECRET = "test-supabase-jwt-secret"


def _supabase_token(email: str, *, secret: str = _SECRET, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": "supabase-uid-123",
        "iss": "supabase",
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "iat": now,
        "exp": now - 10 if expired else now + 3600,
    }
    return _pyjwt.encode(payload, secret, algorithm="HS256")


def _user(**overrides):
    u = {
        "id": "relopass-user-1",
        "email": "hr@example.test",
        "username": "hruser",
        "role": "HR",
        "name": "HR Person",
        "company": "co-1",
    }
    u.update(overrides)
    return u


def _db_mock(user):
    db = MagicMock()
    db.get_user_by_email.return_value = user
    db.create_session.return_value = True
    db.ensure_profile_record.return_value = True
    db.get_profile_record.return_value = {"company_id": "co-1"}
    db.is_admin_allowlisted.return_value = False  # keep effective role = HR
    return db


class ExchangeSupabaseTokenTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_valid_token_issues_session(self):
        db = _db_mock(_user())
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}), \
                patch("backend.app.routers.auth.db", db), \
                patch("backend.app.routers.auth._is_admin_user", return_value=False):
            resp = self.client.post(
                "/api/auth/exchange-supabase-token",
                json={"access_token": _supabase_token("hr@example.test")},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["token"])  # a ReloPass session token was minted
        self.assertEqual(body["user"]["email"], "hr@example.test")
        self.assertEqual(body["user"]["role"], "HR")
        db.create_session.assert_called_once()
        # session bound to the resolved ReloPass user, not the Supabase uid
        args, _ = db.create_session.call_args
        self.assertEqual(args[1], "relopass-user-1")

    def test_invalid_token_is_rejected(self):
        db = _db_mock(_user())
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}), \
                patch("backend.app.routers.auth.db", db):
            resp = self.client.post(
                "/api/auth/exchange-supabase-token",
                json={"access_token": _supabase_token("hr@example.test", secret="wrong-secret")},
            )
        self.assertEqual(resp.status_code, 401, resp.text)
        db.create_session.assert_not_called()

    def test_expired_token_is_rejected(self):
        db = _db_mock(_user())
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}), \
                patch("backend.app.routers.auth.db", db):
            resp = self.client.post(
                "/api/auth/exchange-supabase-token",
                json={"access_token": _supabase_token("hr@example.test", expired=True)},
            )
        self.assertEqual(resp.status_code, 401, resp.text)
        db.create_session.assert_not_called()

    def test_unknown_user_is_rejected(self):
        db = _db_mock(None)  # no ReloPass account for this identity
        with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": _SECRET}), \
                patch("backend.app.routers.auth.db", db):
            resp = self.client.post(
                "/api/auth/exchange-supabase-token",
                json={"access_token": _supabase_token("ghost@example.test")},
            )
        self.assertEqual(resp.status_code, 401, resp.text)
        db.create_session.assert_not_called()

    def test_missing_secret_is_fail_closed(self):
        db = _db_mock(_user())
        env = {k: v for k, v in os.environ.items() if k != "SUPABASE_JWT_SECRET"}
        with patch.dict(os.environ, env, clear=True), \
                patch("backend.app.routers.auth.db", db):
            resp = self.client.post(
                "/api/auth/exchange-supabase-token",
                json={"access_token": "any.token.value"},
            )
        self.assertEqual(resp.status_code, 503, resp.text)


if __name__ == "__main__":
    unittest.main()
