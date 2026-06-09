"""
[AIQ-907] Propagate backend password changes to Supabase Auth.

Backend login/register dispatch sync_relopass_user_to_supabase_auth with the
plaintext password. Before this change, when the Supabase Auth user already
existed the sync no-oped, so a backend password change never reached Supabase
and signInWithPassword drifted to a 400 (this bit admin@ + employee@ on
2026-06-09). Covered here:

  - set_supabase_auth_password resolves the uid then updates the password via
    the GoTrue admin API (admin.update_user_by_id); idempotent + fail-soft.
  - the create-path duplicate branch re-syncs the password, so every login
    self-heals Supabase drift.
  - _resolve_auth_user_id_by_email reads auth.users directly (the GoTrue admin
    list_users endpoint is broken past page 1 on this project — AIQ-907 review).
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import supabase_auth_sync as s  # noqa: E402


def _fake_client(*, update_raises: bool = False, create_exc: Exception | None = None):
    client = mock.MagicMock()
    if update_raises:
        client.auth.admin.update_user_by_id.side_effect = RuntimeError("boom")
    if create_exc is not None:
        client.auth.admin.create_user.side_effect = create_exc
    return client


def _dup_error():
    exc = Exception("Email address has already been registered")
    setattr(exc, "code", "email_exists")
    return exc


# ── auth.users DB-read resolver fakes ─────────────────────────────────────────
class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        self.queries.append((str(stmt), params))
        return _FakeResult(self._row)


class _FakeEngine:
    def __init__(self, row):
        self.conn = _FakeConn(row)

    def connect(self):
        return self.conn


class ResolveAuthUserIdTests(unittest.TestCase):
    def _with_row(self, row):
        import backend.database as bdb
        return mock.patch.object(bdb.db, "engine", _FakeEngine(row))

    def test_resolves_uid_from_auth_users(self):
        with self._with_row(("5669fcbe-uid",)):
            self.assertEqual(s._resolve_auth_user_id_by_email("Employee@X.com"), "5669fcbe-uid")

    def test_returns_none_when_no_row(self):
        with self._with_row(None):
            self.assertIsNone(s._resolve_auth_user_id_by_email("missing@x.com"))

    def test_empty_email_returns_none_without_db(self):
        self.assertIsNone(s._resolve_auth_user_id_by_email("  "))

    def test_db_error_is_fail_soft(self):
        import backend.database as bdb
        boom = mock.MagicMock()
        boom.connect.side_effect = RuntimeError("db down")
        with mock.patch.object(bdb.db, "engine", boom):
            self.assertIsNone(s._resolve_auth_user_id_by_email("x@y.com"))  # no raise


class SetSupabaseAuthPasswordTests(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {"DISABLE_SUPABASE_AUTH_SYNC": ""})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_updates_existing_user_password(self):
        client = _fake_client()
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value="uid-123"):
            ok = s.set_supabase_auth_password("HR@testco.com", "NewPass!1")
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_called_once_with("uid-123", {"password": "NewPass!1"})

    def test_returns_false_when_no_matching_auth_user(self):
        client = _fake_client()
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value=None):
            ok = s.set_supabase_auth_password("missing@testco.com", "NewPass!1")
        self.assertFalse(ok)
        client.auth.admin.update_user_by_id.assert_not_called()

    def test_fail_soft_when_update_raises(self):
        client = _fake_client(update_raises=True)
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value="uid-123"):
            ok = s.set_supabase_auth_password("hr@testco.com", "NewPass!1")
        self.assertFalse(ok)  # did not raise

    def test_skips_when_sync_disabled(self):
        client = _fake_client()
        with mock.patch.dict(os.environ, {"DISABLE_SUPABASE_AUTH_SYNC": "1"}), \
             mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value="uid-123"):
            ok = s.set_supabase_auth_password("hr@testco.com", "NewPass!1")
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_not_called()

    def test_skips_short_password(self):
        client = _fake_client()
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value="uid-123"):
            ok = s.set_supabase_auth_password("hr@testco.com", "abc")
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_not_called()


class SyncResyncsPasswordOnDuplicateTests(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {"DISABLE_SUPABASE_AUTH_SYNC": ""})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_duplicate_user_triggers_password_resync(self):
        client = _fake_client(create_exc=_dup_error())
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value="uid-123"):
            ok = s.sync_relopass_user_to_supabase_auth(
                "hr@testco.com", "RotatedPass!2", relopass_user_id="rp-1"
            )
        self.assertTrue(ok)  # create-path contract: user exists -> True
        client.auth.admin.update_user_by_id.assert_called_once_with("uid-123", {"password": "RotatedPass!2"})

    def test_fresh_create_does_not_call_update(self):
        client = _fake_client()  # create_user succeeds (no side_effect)
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client), \
             mock.patch.object(s, "_resolve_auth_user_id_by_email", return_value="uid-123"):
            ok = s.sync_relopass_user_to_supabase_auth(
                "new@testco.com", "FreshPass!1", relopass_user_id="rp-2"
            )
        self.assertTrue(ok)
        client.auth.admin.create_user.assert_called_once()
        client.auth.admin.update_user_by_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
