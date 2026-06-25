"""Regression: db.resolve_case_status is the single shared status source.

The case LIST (GET /api/employee/cases) and DETAIL (GET /api/cases/{id}) both derive
status from db.resolve_case_status, so they can never disagree. The bug it closes:
they previously picked DIFFERENT assignment rows for multi-assignment cases (list was
employee-scoped, detail took the latest row globally) → e.g. list 'assigned' vs detail
'awaiting_intake'. The resolver is employee-scoped and deterministic (newest).
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


class ResolveCaseStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        self.db = _RealDB(self.engine)
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE case_assignments "
                "(id TEXT, case_id TEXT, canonical_case_id TEXT, employee_user_id TEXT, "
                " status TEXT, created_at TEXT)"
            ))
            # Case X: empA has two rows (older awaiting_intake, newer assigned);
            # empB has the newest row overall (submitted).
            for row in [
                ("a1", "X", "X", "empA", "awaiting_intake", "2026-01-01"),
                ("a2", "X", "X", "empA", "assigned", "2026-02-01"),
                ("a3", "X", "X", "empB", "submitted", "2026-03-01"),
            ]:
                c.execute(text(
                    "INSERT INTO case_assignments VALUES (:id,:c,:cc,:e,:s,:t)"
                ), dict(zip(("id", "c", "cc", "e", "s", "t"), row)))

    def test_employee_scoped_picks_that_employees_newest(self):
        # empA's newest is 'assigned' (NOT the global-newest 'submitted', NOT the
        # older 'awaiting_intake') — this is the row-selection fix.
        self.assertEqual(self.db.resolve_case_status("X", "empA"), "assigned")
        self.assertEqual(self.db.resolve_case_status("X", "empB"), "submitted")

    def test_unscoped_picks_newest_overall(self):
        self.assertEqual(self.db.resolve_case_status("X", None), "submitted")

    def test_resolves_by_assignment_id_too(self):
        # The list caseId can be the assignment id (when case_id is null).
        self.assertEqual(self.db.resolve_case_status("a2", "empA"), "assigned")

    def test_no_matching_assignment_returns_none(self):
        self.assertIsNone(self.db.resolve_case_status("NOPE"))
        self.assertIsNone(self.db.resolve_case_status("X", "empZ"))
        self.assertIsNone(self.db.resolve_case_status(""))

    def test_parity_across_every_lifecycle_state(self):
        # For every lifecycle status, a multi-employee case where empA holds that
        # status and empB holds a globally-newer DIFFERENT status. The detail (now
        # scoped to the requester) and the list (scoped to the employee) both call
        # resolve_case_status(case, empA) → empA's status; the unscoped HR view
        # gets empB's (global newest). This is the 5b16522e bug (approved vs
        # awaiting_intake) generalised to the full enum.
        states = [
            "created", "assigned", "awaiting_intake", "submitted",
            "approved", "rejected", "closed",
        ]
        with self.engine.begin() as c:
            for s in states:
                other = "submitted" if s == "approved" else "approved"
                ckey = f"case-{s}"
                c.execute(text(
                    "INSERT INTO case_assignments VALUES (:id,:k,:k,:e,:st,:t)"
                ), {"id": f"{ckey}-A", "k": ckey, "e": "empA", "st": s, "t": "2026-02-01"})
                c.execute(text(  # empB: globally newer, different status
                    "INSERT INTO case_assignments VALUES (:id,:k,:k,:e,:st,:t)"
                ), {"id": f"{ckey}-B", "k": ckey, "e": "empB", "st": other, "t": "2026-03-01"})
        for s in states:
            ckey = f"case-{s}"
            other = "submitted" if s == "approved" else "approved"
            # list & (now-scoped) detail both resolve empA's own status
            self.assertEqual(self.db.resolve_case_status(ckey, "empA"), s, s)
            # unscoped HR view = global newest (empB)
            self.assertEqual(self.db.resolve_case_status(ckey, None), other, s)


if __name__ == "__main__":
    unittest.main()
