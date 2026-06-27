"""
Tenant-isolation regression: POST /api/cases/{id}/quote-request (WZ4) and
POST /api/cases/{id}/messages (WZ5) must enforce case access.

Both handlers previously skipped the `_assert_case_access` guard that every
sibling case-write route uses, so ANY authenticated employee could write a
quote request or a message to a case they were not assigned to (a broken-access-
control / tenant-isolation gap). These tests pin the fix:

  - a non-assignee employee is FORBIDDEN (403) on both endpoints — exercised
    against the REAL guard with a seeded in-memory case;
  - each handler actually calls the guard with the route's own (user, case_id),
    so it can't be fed the wrong id and silently bypassed.

Deterministic: in-memory SQLite with the case_service engine patched. No network,
no live DB — the guard raises before any insert is reached.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import HTTPException  # noqa: E402

from backend.app.services import case_service  # noqa: E402
from backend.app.routers import cases_write  # noqa: E402
from backend.app.routers.cases import _MessageBody, _QuoteRequestBody  # noqa: E402


def _u() -> str:
    return str(uuid.uuid4())


# Same minimal schema the guard reads (mirrors test_auth_id_2_case_access.py).
_SCHEMA = """
CREATE TABLE cases (id TEXT, company_id TEXT, employee_id TEXT, hr_owner_id TEXT);
CREATE TABLE case_assignments (id TEXT, employee_user_id TEXT, hr_user_id TEXT, canonical_case_id TEXT, case_id TEXT);
CREATE TABLE relocation_cases (id TEXT, company_id TEXT);
CREATE TABLE profiles (id TEXT, company_id TEXT);
"""


class CaseWriteAccessGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in _SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        self._patch = mock.patch.object(case_service.main_db, "engine", self.engine)
        self._patch.start()
        self.addCleanup(self._patch.stop)

        self.company_id = "co-1"
        self.owner_uuid = _u()
        self.case_id = _u()  # a public.cases id (UUID, passes _UUID_RE)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id, hr_owner_id) "
                     "VALUES (:id, :c, :emp, NULL)"),
                {"id": self.case_id, "c": self.company_id, "emp": self.owner_uuid},
            )

        # An employee who is NOT the assignee / owner of the case.
        self.other_user = {"id": "seed-emp-other", "auth_uuid": _u(), "role": "EMPLOYEE"}

    # --- real guard: non-assignee is forbidden on both endpoints --------------

    def test_quote_request_forbidden_for_non_assignee(self):
        with self.assertRaises(HTTPException) as ctx:
            cases_write.create_case_quote_request(
                self.case_id, _QuoteRequestBody(services=["housing"]), self.other_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_post_message_forbidden_for_non_assignee(self):
        with self.assertRaises(HTTPException) as ctx:
            cases_write.post_case_message(
                self.case_id, _MessageBody(content="hello"), self.other_user
            )
        self.assertEqual(ctx.exception.status_code, 403)

    # --- wiring: each handler calls the guard with its own (user, case_id) ----

    def test_quote_request_invokes_guard_with_route_args(self):
        with mock.patch.object(cases_write, "_assert_case_access") as guard:
            guard.side_effect = HTTPException(status_code=403, detail="denied")
            with self.assertRaises(HTTPException):
                cases_write.create_case_quote_request(
                    self.case_id, _QuoteRequestBody(), self.other_user
                )
        guard.assert_called_once_with(self.other_user, self.case_id)

    def test_post_message_invokes_guard_with_route_args(self):
        with mock.patch.object(cases_write, "_assert_case_access") as guard:
            guard.side_effect = HTTPException(status_code=403, detail="denied")
            with self.assertRaises(HTTPException):
                cases_write.post_case_message(
                    self.case_id, _MessageBody(content="hi"), self.other_user
                )
        guard.assert_called_once_with(self.other_user, self.case_id)


if __name__ == "__main__":
    unittest.main()
