"""AIQ-1347 — username login must be case-insensitive (parity with email).

Two halves:
1. Real `UsersMixin.get_user_by_username` / `get_user_by_identifier` SQL against an
   in-memory SQLite `users` table (the actual fix lives in the lookup query).
2. The `/api/auth/login` endpoint still rejects a wrong password and an unknown
   identifier with 401 (password verification path unchanged).

Root conftest mocks `backend.database`, so we import the real `UsersMixin`
directly and attach a real engine — bypassing the mock.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402

from backend.db.users import UsersMixin  # noqa: E402 (real, not the mocked db)


class _DB(UsersMixin):
    """Minimal harness: real UsersMixin lookups over a real engine."""

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _row_to_dict(row):
        return dict(row._mapping) if row is not None else None


_USERS_SCHEMA = """
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT,
    email TEXT,
    password_hash TEXT,
    role TEXT NOT NULL,
    name TEXT,
    created_at TEXT
);
"""


class UsernameLookupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            conn.execute(text(_USERS_SCHEMA))
            conn.execute(text(
                "INSERT INTO users (id, username, email, role, name, created_at) "
                "VALUES ('u1', 'HRManager', 'Boss@Acme.com', 'HR', 'Boss', '2026-01-01')"
            ))
        self.db = _DB(self.engine)

    def test_username_exact_case(self):
        u = self.db.get_user_by_username("HRManager")
        self.assertIsNotNone(u)
        self.assertEqual(u["id"], "u1")

    def test_username_different_case(self):
        for variant in ("hrmanager", "HRMANAGER", "  hrManager  "):
            u = self.db.get_user_by_username(variant)
            self.assertIsNotNone(u, f"{variant!r} should match case-insensitively")
            self.assertEqual(u["id"], "u1")

    def test_identifier_routes_username_case_insensitive(self):
        # no '@' -> username path
        u = self.db.get_user_by_identifier("hrmanager")
        self.assertEqual(u["id"], "u1")

    def test_identifier_email_still_case_insensitive(self):
        u = self.db.get_user_by_identifier("BOSS@ACME.COM")
        self.assertEqual(u["id"], "u1")

    def test_unknown_username_returns_none(self):
        self.assertIsNone(self.db.get_user_by_username("ghost"))
        self.assertIsNone(self.db.get_user_by_identifier("ghost"))

    def test_case_variant_pair_is_deterministic(self):
        # username UNIQUE is case-sensitive, so 'John'/'john' can coexist. The
        # exact-case-first tie-break must return a single deterministic row.
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, username, email, role, created_at) VALUES "
                "('j1', 'John', 'john1@x.com', 'HR', '2026-01-01'), "
                "('j2', 'john', 'john2@x.com', 'HR', '2026-01-01')"
            ))
        # exact case -> the exact row wins
        self.assertEqual(self.db.get_user_by_username("john")["id"], "j2")
        self.assertEqual(self.db.get_user_by_username("John")["id"], "j1")
        # non-exact case -> still resolves to exactly one row (no ambiguity/crash)
        picked = self.db.get_user_by_username("JOHN")
        self.assertIn(picked["id"], {"j1", "j2"})


class LoginPasswordPathTests(unittest.TestCase):
    """The endpoint still 401s on wrong password / unknown identifier (unchanged)."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        self.client = TestClient(app, raise_server_exceptions=False)

    def _db_with_user(self):
        from backend.app.routers.auth import _pwd_context
        db = MagicMock()
        db.get_user_by_identifier.return_value = {
            "id": "u1", "username": "hrmanager", "email": "boss@acme.com",
            "password_hash": _pwd_context.hash("Passw0rd!"), "role": "HR", "name": "Boss",
        }
        return db

    def test_wrong_password_401(self):
        with patch("backend.app.routers.auth.db", self._db_with_user()):
            resp = self.client.post(
                "/api/auth/login", json={"identifier": "hrmanager", "password": "WRONG"}
            )
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_unknown_identifier_401(self):
        db = MagicMock()
        db.get_user_by_identifier.return_value = None
        with patch("backend.app.routers.auth.db", db):
            resp = self.client.post(
                "/api/auth/login", json={"identifier": "nobody", "password": "Passw0rd!"}
            )
        self.assertEqual(resp.status_code, 401, resp.text)


if __name__ == "__main__":
    unittest.main()
