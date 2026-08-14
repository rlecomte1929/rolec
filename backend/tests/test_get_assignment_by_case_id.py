"""Regression: db.get_assignment_by_case_id resolves by the assignment's OWN id.

require_case_access(case_id) → db.get_assignment_by_case_id(case_id); a None return is
a 404, and its callers (e.g. /api/payment/status → the roadmap paywall) fail OPEN on
that 404. The employee roadmap URL and the Stripe checkout success_url both key on
case_assignments.id, so the lookup MUST match that id — not only canonical_case_id /
case_id. Before the fix, an assignment-id case matched 0 rows → 404 → the paywall was
bypassable via exactly the URL testers land on. Mirrors resolve_case_status' `OR id`.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# backend.database (the `db` singleton) is a MagicMock under the test harness
# (backend/conftest.py), so exercise the REAL method off its mixins against sqlite.
from backend.db.cases import CasesMixin
from backend.db.misc import MiscMixin


class _RealDB(MiscMixin, CasesMixin):
    def __init__(self, engine):
        self.engine = engine
        self._initialized = True  # skip init_db() in _exec
        self._init_lock = threading.Lock()


class GetAssignmentByCaseIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        self.db = _RealDB(self.engine)
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE case_assignments "
                "(id TEXT, case_id TEXT, canonical_case_id TEXT, employee_user_id TEXT)"
            ))
            # Empty wizard_cases so coalesce_case_lookup_id is a clean no-op (matches
            # prod for a case with no wizard row) rather than swallowing a missing-table
            # exception.
            c.execute(text("CREATE TABLE wizard_cases (id TEXT)"))
            # Mirrors the live test case 732a7b07: assignment id DIFFERS from the case id.
            c.execute(text(
                "INSERT INTO case_assignments VALUES "
                "('assign-1','case-1','case-1','emp-1')"
            ))
            # A legacy row where canonical is NULL and only case_id matches.
            c.execute(text(
                "INSERT INTO case_assignments VALUES "
                "('assign-2','legacy-case-2',NULL,'emp-2')"
            ))

    def test_resolves_by_canonical_case_id(self):
        row = self.db.get_assignment_by_case_id("case-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], "assign-1")

    def test_resolves_by_case_id_when_canonical_null(self):
        row = self.db.get_assignment_by_case_id("legacy-case-2")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], "assign-2")

    def test_resolves_by_assignment_own_id(self):
        # THE FIX: the roadmap/checkout URLs use case_assignments.id. Before adding
        # `OR id = :cid`, this returned None → 404 → paywall fail-open.
        row = self.db.get_assignment_by_case_id("assign-1")
        self.assertIsNotNone(row, "assignment id must resolve — else require_case_access fails open")
        self.assertEqual(row["id"], "assign-1")

    def test_unknown_id_returns_none(self):
        self.assertIsNone(self.db.get_assignment_by_case_id("does-not-exist"))


if __name__ == "__main__":
    unittest.main()
