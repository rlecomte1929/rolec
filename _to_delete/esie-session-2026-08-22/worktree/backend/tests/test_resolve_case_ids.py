"""AIQ-1704 A1: db.resolve_case_ids — the canonical, fail-closed id-resolution boundary.

A route/URL may carry ANY of three id forms — the assignment PK (case_assignments.id),
the case_id, or the canonical_case_id. resolve_case_ids maps all three to one CaseIds
context so a case-scoped handler never has to guess which it was handed, and returns
None (never a guess) for an id that resolves to no assignment — so callers 4xx instead
of silently returning empty or failing open (the case-vs-assignment id confusion class).

Wraps get_assignment_by_case_id (already 3-form; see test_get_assignment_by_case_id.py),
adding the fail-closed contract + the resolved-id context. Exercises the REAL method off
the mixins against sqlite (backend.database's `db` singleton is a MagicMock under the
harness, backend/conftest.py).
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import threading
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.db.cases import CasesMixin, CaseIds
from backend.db.misc import MiscMixin


class _RealDB(MiscMixin, CasesMixin):
    def __init__(self, engine):
        self.engine = engine
        self._initialized = True  # skip init_db() in _exec
        self._init_lock = threading.Lock()


class ResolveCaseIdsTests(unittest.TestCase):
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
            # Empty wizard_cases so coalesce_case_lookup_id is a clean no-op.
            c.execute(text("CREATE TABLE wizard_cases (id TEXT)"))
            # canonical == case_id (the common case).
            c.execute(text(
                "INSERT INTO case_assignments VALUES ('assign-1','case-1','case-1','emp-1')"
            ))
            # canonical DIFFERS from case_id — proves resolve_case_ids returns the
            # canonical (what case-keyed tables use), not the raw case_id.
            c.execute(text(
                "INSERT INTO case_assignments VALUES ('assign-3','raw-3','canon-3','emp-3')"
            ))
            # Legacy row: canonical is NULL, only case_id carries the value.
            # [AIQ-1737·2] Intentional NULL — asserts the resolver still handles a legacy
            # NULL-canonical row (defensive fallback that outlives the data cleanup). Isolated
            # in-memory schema; AIQ-1732's prod NOT NULL(canonical_case_id) does not govern it.
            c.execute(text(
                "INSERT INTO case_assignments VALUES ('assign-2','legacy-case-2',NULL,'emp-2')"
            ))

    # --- all three id forms resolve to the SAME canonical context ---

    def test_resolves_from_assignment_pk(self):
        ids = self.db.resolve_case_ids("assign-1")
        self.assertIsInstance(ids, CaseIds)
        self.assertEqual(ids.assignment_id, "assign-1")
        self.assertEqual(ids.canonical_case_id, "case-1")

    def test_resolves_from_case_id(self):
        ids = self.db.resolve_case_ids("case-1")
        self.assertEqual(ids.assignment_id, "assign-1")
        self.assertEqual(ids.canonical_case_id, "case-1")

    def test_all_three_forms_agree(self):
        # assign-3 / raw-3 (case_id) / canon-3 (canonical) all point at one assignment.
        by_pk = self.db.resolve_case_ids("assign-3")
        by_case = self.db.resolve_case_ids("raw-3")
        by_canonical = self.db.resolve_case_ids("canon-3")
        self.assertEqual(by_pk, by_case)
        self.assertEqual(by_case, by_canonical)
        # canonical_case_id is preferred over the raw case_id.
        self.assertEqual(by_pk.canonical_case_id, "canon-3")
        self.assertEqual(by_pk.case_id, "raw-3")
        self.assertEqual(by_pk.assignment_id, "assign-3")

    def test_legacy_null_canonical_falls_back_to_case_id(self):
        ids = self.db.resolve_case_ids("legacy-case-2")
        self.assertEqual(ids.canonical_case_id, "legacy-case-2")
        self.assertEqual(ids.case_id, "legacy-case-2")
        self.assertEqual(ids.assignment_id, "assign-2")

    def test_context_carries_the_assignment_row(self):
        ids = self.db.resolve_case_ids("case-1")
        self.assertEqual(ids.assignment.get("employee_user_id"), "emp-1")

    # --- fail-closed: an unresolvable id returns None (caller 4xx) ---

    def test_unknown_id_returns_none(self):
        self.assertIsNone(self.db.resolve_case_ids("does-not-exist"))

    def test_blank_id_returns_none(self):
        self.assertIsNone(self.db.resolve_case_ids(""))


if __name__ == "__main__":
    unittest.main()
