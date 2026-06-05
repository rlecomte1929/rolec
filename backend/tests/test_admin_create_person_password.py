"""B2: an admin-created person with an initial password must get a loginable
ReloPass `users` row (id = profile id), so /api/auth/login — which authenticates
against `users` — can find them. Without a password the behaviour is unchanged
(Supabase invite only). Password is validated up front, before any DB writes.

The conftest replaces backend.database with a MagicMock, so we assert the call
into db.create_user (with a hash that actually verifies) rather than hitting a DB.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_b2.db")

import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from passlib.context import CryptContext

from backend import main as M
from backend.main import AdminCreatePersonRequest, create_person

_PWD = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ADMIN = {"id": "admin-1"}


class _Req:
    state = SimpleNamespace(request_id="test-req")


class AdminCreatePersonPasswordTests(unittest.TestCase):
    def setUp(self) -> None:
        # invite_admin_created_user is best-effort; stub to a benign no-op so the
        # test never reaches Supabase.
        self._inv = mock.patch(
            "backend.app.services.supabase_auth_sync.invite_admin_created_user",
            return_value=SimpleNamespace(sent=False, error=None),
        )
        self._inv.start()
        self.addCleanup(self._inv.stop)
        M.db.reset_mock()
        M.db.get_profile_record.return_value = {"id": "p", "email": "x@y.com"}

    def test_password_creates_loginable_users_row(self) -> None:
        body = AdminCreatePersonRequest(
            email="hr@new.co", role="HR", company_id="c1", password="StrongPass1")
        resp = create_person(body, _Req(), ADMIN)
        M.db.create_user.assert_called_once()
        kw = M.db.create_user.call_args.kwargs
        self.assertEqual(kw["email"], "hr@new.co")
        self.assertEqual(kw["role"], "HR")
        # the stored hash must verify against the plaintext the admin set
        self.assertTrue(_PWD.verify("StrongPass1", kw["password_hash"]))
        # users.id == profiles.id so HR company resolution (hr_users.profile_id) matches
        self.assertEqual(kw["user_id"], M.db.create_profile.call_args.kwargs["person_id"])
        self.assertTrue(resp["login_ready"])

    def test_no_password_skips_users_row(self) -> None:
        body = AdminCreatePersonRequest(email="hr2@new.co", role="HR", company_id="c1")
        resp = create_person(body, _Req(), ADMIN)
        M.db.create_user.assert_not_called()
        self.assertFalse(resp["login_ready"])

    def test_short_password_rejected_before_any_write(self) -> None:
        body = AdminCreatePersonRequest(email="hr3@new.co", role="HR", password="short")
        with self.assertRaises(HTTPException) as ctx:
            create_person(body, _Req(), ADMIN)
        self.assertEqual(ctx.exception.status_code, 400)
        M.db.create_profile.assert_not_called()  # failed fast, no partial state
        M.db.create_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()
