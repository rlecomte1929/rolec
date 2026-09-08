"""SECURITY regression: GET /api/cases/{case_id}/messages must authorize.

list_case_messages authenticated with only `get_current_user` and had NO
`_assert_case_access` call, so any logged-in user could read ANY case's message
thread (relocation PII) by id — a cross-tenant IDOR. The fix adds the same
access guard every sibling case-scoped read in the module already uses. These
tests prove the guard is wired AND effective (a denied access blocks the read
before the DB is ever touched).

Direct-call pattern (mirrors test_case_vendors.py) — exercises the handler's
authorization independent of the query.
"""

from __future__ import annotations

import inspect
import os
import unittest
import uuid
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi import HTTPException  # noqa: E402

from backend.app.routers import cases_read as router_module  # noqa: E402
from backend.app.routers.cases_read import list_case_messages  # noqa: E402

_USER = {"id": str(uuid.uuid4()), "role": "HR", "is_admin": False}


class CaseMessagesAccessGuard(unittest.TestCase):
    def test_denied_access_raises_and_returns_no_messages(self):
        # A non-owner: _assert_case_access raises 403 → the endpoint must propagate
        # it, never fall through to return the thread.
        with mock.patch.object(
            router_module, "_assert_case_access",
            side_effect=HTTPException(status_code=403, detail="forbidden"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                list_case_messages(case_id="some-other-companys-case", user=_USER)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_guard_runs_before_any_db_access(self):
        # If authorization fails, the query must never run (no PII leaves the DB).
        with mock.patch.object(
            router_module, "_assert_case_access",
            side_effect=HTTPException(status_code=403),
        ) as guard, mock.patch.object(router_module.main_db, "engine") as engine:
            with self.assertRaises(HTTPException):
                list_case_messages(case_id="c", user=_USER)
        guard.assert_called_once()
        engine.begin.assert_not_called()

    def test_authorized_caller_reaches_the_query(self):
        # Owner/HR/admin (guard passes): the handler proceeds to read (empty thread here).
        with mock.patch.object(router_module, "_assert_case_access", return_value=None), \
             mock.patch.object(router_module, "_canonical_case_id_or_404", side_effect=lambda c: c), \
             mock.patch.object(router_module.main_db, "engine") as engine:
            cm = engine.begin.return_value.__enter__.return_value
            cm.execute.return_value.mappings.return_value.all.return_value = []
            result = list_case_messages(case_id="my-case", user=_USER)
        self.assertEqual(result, [])

    def test_source_wires_the_guard(self):
        # A future edit that drops the guard fails here (matches the AIQ-1704 guard style).
        src = inspect.getsource(list_case_messages)
        self.assertIn(
            "_assert_case_access", src,
            "list_case_messages must authorize before returning case-message PII",
        )


if __name__ == "__main__":
    unittest.main()
