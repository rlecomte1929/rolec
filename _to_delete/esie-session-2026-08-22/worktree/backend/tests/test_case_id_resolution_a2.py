"""AIQ-1704 A2: case-scoped reads resolve the id before their case-keyed query.

The bug class: a case-scoped endpoint receives an assignment id (the form the
employee roadmap / HR case-detail URLs carry) but keys its SQL on case_id, so it
matched no rows and returned an empty list — a silent wrong answer. A2 routes each
offender through the canonical resolver (resolve_case_ids / _canonical_case_id_or_404)
and fails closed on an unknown id.

Two guards:
  * behavioural — list_case_milestones now resolves an assignment PK to its canonical
    case id (was silent-empty); exercises the REAL method against sqlite.
  * wiring — each repointed endpoint actually calls the resolver (source-level, so it
    can't silently regress). The full HTTP id-matrix is B3 (Subtask 4).
"""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.db.cases import CasesMixin
from backend.db.misc import MiscMixin


class _RealDB(MiscMixin, CasesMixin):
    def __init__(self, engine):
        self.engine = engine
        self._initialized = True
        self._init_lock = threading.Lock()


class MilestonesResolveAssignmentPk(unittest.TestCase):
    """list_case_milestones must resolve an assignment PK — case_milestones has no
    assignment column, so before A2 an assignment-id timeline URL rendered empty."""

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
            c.execute(text("CREATE TABLE wizard_cases (id TEXT)"))
            c.execute(text(
                "CREATE TABLE case_milestones "
                "(id TEXT, case_id TEXT, canonical_case_id TEXT, milestone_type TEXT, "
                " title TEXT, description TEXT, target_date TEXT, actual_date TEXT, "
                " status TEXT, sort_order INTEGER, created_at TEXT, updated_at TEXT, "
                " owner TEXT, criticality TEXT, notes TEXT, source TEXT, service_key TEXT)"
            ))
            # assignment PK 'assign-9' differs from the canonical case id 'canon-9'.
            c.execute(text(
                "INSERT INTO case_assignments VALUES ('assign-9','raw-9','canon-9','emp-9')"
            ))
            # the milestone is keyed on the canonical case id, as prod rows are.
            c.execute(text(
                "INSERT INTO case_milestones "
                "(id, case_id, canonical_case_id, milestone_type, title, sort_order) "
                "VALUES ('m1','raw-9','canon-9','visa','Apply for visa',1)"
            ))

    def test_assignment_pk_resolves_to_the_cases_milestones(self):
        # THE FIX: an assignment id used to match no case_milestones row → empty timeline.
        rows = self.db.list_case_milestones("assign-9")
        self.assertEqual(len(rows), 1, "assignment id must resolve to the case's milestones")
        self.assertEqual(rows[0]["title"], "Apply for visa")

    def test_case_id_and_canonical_still_resolve(self):
        self.assertEqual(len(self.db.list_case_milestones("canon-9")), 1)
        self.assertEqual(len(self.db.list_case_milestones("raw-9")), 1)

    def test_unknown_id_degrades_to_empty_not_error(self):
        # A db-layer read degrades to [] (the endpoint layer is what 4xxs).
        self.assertEqual(self.db.list_case_milestones("does-not-exist"), [])


class EndpointResolutionWiring(unittest.TestCase):
    """Each repointed case-scoped read must route its id through the resolver, so a
    future edit can't silently reintroduce the raw-id query."""

    def test_cases_read_endpoints_resolve_the_id(self):
        from backend.app.routers import cases_read
        for fn in (cases_read.get_budget_summary,
                   cases_read.list_case_messages,
                   cases_read.list_case_vendors):
            src = inspect.getsource(fn)
            self.assertIn(
                "_canonical_case_id_or_404", src,
                f"{fn.__name__} must resolve the id before its case-keyed query",
            )

    def test_hr_providers_resolves_the_id(self):
        from backend.app.routers import hr_coordination
        src = inspect.getsource(hr_coordination.get_case_providers)
        self.assertIn("resolve_case_ids", src,
                      "get_case_providers must resolve the id before reading provider_tasks")

    def test_canonical_helper_fails_closed(self):
        from backend.app.routers import cases_read
        src = inspect.getsource(cases_read._canonical_case_id_or_404)
        self.assertIn("resolve_case_ids", src)
        self.assertIn("404", src, "an unresolvable id must 404 (fail closed), never silent-empty")


if __name__ == "__main__":
    unittest.main()
