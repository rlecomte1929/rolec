"""AIQ-1353 — backend multi-role read layer.

Two halves:
1. Real UsersMixin.get_user_roles over in-memory SQLite (junction rows / empty /
   table-absent fallback).
2. get_current_user populates user['roles'] + user['primary_role'] from the
   junction, falling back to the legacy users.role, and keeps ADMIN on the
   admin/cron short-circuits.

Root conftest mocks backend.database, so the DB-layer test imports the real
UsersMixin directly; the get_current_user test patches backend.app.auth_deps.db.
"""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest import mock

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402

from backend.db.users import UsersMixin  # noqa: E402 (real, not the mocked db)


class _DB(UsersMixin):
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _row_to_dict(row):
        return dict(row._mapping) if row is not None else None


_SCHEMA = """
CREATE TABLE users (id TEXT PRIMARY KEY, role TEXT);
CREATE TABLE user_roles (id TEXT, user_id TEXT, role TEXT, is_primary BOOLEAN);
INSERT INTO users (id, role) VALUES ('u1', 'HR'), ('u2', 'EMPLOYEE');
INSERT INTO user_roles (id, user_id, role, is_primary) VALUES
  ('r1', 'u1', 'HR', 1), ('r2', 'u1', 'EMPLOYEE', 0);
"""


class GetUserRolesDBTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in _SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        self.db = _DB(self.engine)

    def test_multi_role_rows_returned(self):
        rows = self.db.get_user_roles("u1")
        self.assertEqual({r["role"] for r in rows}, {"HR", "EMPLOYEE"})
        self.assertEqual([r["role"] for r in rows if r["is_primary"]], ["HR"])

    def test_no_rows_returns_empty(self):
        self.assertEqual(self.db.get_user_roles("u2"), [])
        self.assertEqual(self.db.get_user_roles("ghost"), [])
        self.assertEqual(self.db.get_user_roles(""), [])

    def test_missing_table_returns_empty(self):
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE user_roles"))
        self.assertEqual(self.db.get_user_roles("u1"), [])  # never raises


class GetCurrentUserRolesTests(unittest.TestCase):
    """get_current_user roles[] / primary_role + admin/cron short-circuits."""

    def _call(self, mock_db, token="Bearer x"):
        from backend.app import auth_deps
        auth_deps.reset_identity_caches_for_tests()
        with mock.patch.object(auth_deps, "db", mock_db), \
             mock.patch.object(auth_deps, "_resolve_auth_uuid", return_value=None):
            return asyncio.run(auth_deps.get_current_user(request=None, authorization=token))

    def _base_mock(self, user, role_rows=None):
        m = mock.MagicMock()
        payload = dict(user)
        payload["role_rows"] = list(role_rows or [])
        m.get_user_context_by_token.return_value = payload
        m.get_admin_session.return_value = None
        m.get_profile_record.return_value = {"role": user.get("role")}
        return m

    def test_multi_role_from_junction(self):
        m = self._base_mock(
            {"id": "u1", "role": "HR", "email": "h@x"},
            role_rows=[
                {"role": "HR", "is_primary": True},
                {"role": "EMPLOYEE", "is_primary": False},
            ],
        )
        u = self._call(m)
        self.assertEqual(set(u["roles"]), {"HR", "EMPLOYEE"})
        self.assertEqual(u["primary_role"], "HR")
        self.assertEqual(u["role"], "HR")  # legacy field kept

    def test_legacy_fallback_when_no_junction(self):
        m = self._base_mock({"id": "u2", "role": "EMPLOYEE", "email": "e@x"}, role_rows=[])
        u = self._call(m)
        self.assertEqual(u["roles"], ["EMPLOYEE"])
        self.assertEqual(u["primary_role"], "EMPLOYEE")

    def test_fallback_role_is_held_when_junction_omits_it(self):
        m = self._base_mock(
            {"id": "u1", "role": "HR", "email": "h@x"},
            role_rows=[{"role": "EMPLOYEE", "is_primary": False}],
        )
        u = self._call(m)
        self.assertEqual(set(u["roles"]), {"HR", "EMPLOYEE"})
        self.assertEqual(u["primary_role"], "HR")

    def test_admin_short_circuit_keeps_admin(self):
        m = self._base_mock({"id": "a1", "role": "ADMIN", "email": "a@x"}, role_rows=[])
        u = self._call(m)
        self.assertIn("ADMIN", u["roles"])
        self.assertEqual(u["primary_role"], "ADMIN")

    def test_cron_path_returns_admin_roles(self):
        with mock.patch.dict(os.environ, {"CRON_SECRET": "s3cr3t"}):
            u = self._call(mock.MagicMock(), token="Bearer s3cr3t")
        self.assertEqual(u["role"], "ADMIN")
        self.assertEqual(u["roles"], ["ADMIN"])
        self.assertEqual(u["primary_role"], "ADMIN")


if __name__ == "__main__":
    unittest.main()
