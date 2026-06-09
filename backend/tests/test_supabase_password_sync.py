"""
[AIQ-907] Propagate backend password changes to Supabase Auth.

Backend login/register dispatch sync_relopass_user_to_supabase_auth with the
plaintext password. Before this change, when the Supabase Auth user already
existed the sync no-oped, so a backend password change never reached Supabase
and signInWithPassword drifted to a 400 (this bit admin@ + employee@ on
2026-06-09). These tests cover the new propagation:

  - set_supabase_auth_password updates an existing auth user via the GoTrue
    admin API (admin.update_user_by_id), and is idempotent + fail-soft.
  - the create-path duplicate branch now re-syncs the password, so every login
    self-heals Supabase drift.
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


class _FakeUser:
    def __init__(self, email: str, uid: str):
        self.email = email
        self.id = uid


class _FakeListResp:
    def __init__(self, users):
        self.users = users


def _fake_client(users, *, update_raises: bool = False, create_exc: Exception | None = None):
    client = mock.MagicMock()
    client.auth.admin.list_users.return_value = _FakeListResp(users)
    if update_raises:
        client.auth.admin.update_user_by_id.side_effect = RuntimeError("boom")
    if create_exc is not None:
        client.auth.admin.create_user.side_effect = create_exc
    return client


def _dup_error():
    exc = Exception("Email address has already been registered")
    setattr(exc, "code", "email_exists")
    return exc


class SetSupabaseAuthPasswordTests(unittest.TestCase):
    def setUp(self):
        # Ensure the sync isn't globally disabled by the ambient env.
        self._env = mock.patch.dict(os.environ, {"DISABLE_SUPABASE_AUTH_SYNC": ""})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_updates_existing_user_password(self):
        client = _fake_client([_FakeUser("hr@testco.com", "uid-123")])
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.set_supabase_auth_password("HR@testco.com", "NewPass!1")
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_called_once_with(
            "uid-123", {"password": "NewPass!1"}
        )

    def test_returns_false_when_no_matching_auth_user(self):
        client = _fake_client([_FakeUser("someone@else.com", "uid-x")])
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.set_supabase_auth_password("missing@testco.com", "NewPass!1")
        self.assertFalse(ok)
        client.auth.admin.update_user_by_id.assert_not_called()

    def test_fail_soft_when_update_raises(self):
        client = _fake_client([_FakeUser("hr@testco.com", "uid-123")], update_raises=True)
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.set_supabase_auth_password("hr@testco.com", "NewPass!1")
        self.assertFalse(ok)  # did not raise

    def test_skips_when_sync_disabled(self):
        client = _fake_client([_FakeUser("hr@testco.com", "uid-123")])
        with mock.patch.dict(os.environ, {"DISABLE_SUPABASE_AUTH_SYNC": "1"}), \
             mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.set_supabase_auth_password("hr@testco.com", "NewPass!1")
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_not_called()

    def test_skips_short_password(self):
        client = _fake_client([_FakeUser("hr@testco.com", "uid-123")])
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.set_supabase_auth_password("hr@testco.com", "abc")
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_not_called()


class SyncResyncsPasswordOnDuplicateTests(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {"DISABLE_SUPABASE_AUTH_SYNC": ""})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_duplicate_user_triggers_password_resync(self):
        client = _fake_client(
            [_FakeUser("hr@testco.com", "uid-123")], create_exc=_dup_error()
        )
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.sync_relopass_user_to_supabase_auth(
                "hr@testco.com", "RotatedPass!2", relopass_user_id="rp-1"
            )
        # Create path contract: user exists -> True; and the password was re-synced.
        self.assertTrue(ok)
        client.auth.admin.update_user_by_id.assert_called_once_with(
            "uid-123", {"password": "RotatedPass!2"}
        )

    def test_fresh_create_does_not_call_update(self):
        client = _fake_client([])  # create_user succeeds (no side_effect)
        with mock.patch.object(s, "get_supabase_admin_client", return_value=client):
            ok = s.sync_relopass_user_to_supabase_auth(
                "new@testco.com", "FreshPass!1", relopass_user_id="rp-2"
            )
        self.assertTrue(ok)
        client.auth.admin.create_user.assert_called_once()
        client.auth.admin.update_user_by_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
