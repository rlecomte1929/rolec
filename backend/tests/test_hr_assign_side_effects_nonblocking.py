"""HR assign must not block on post-creation hooks (mobility link, case-person,
passport sync) or on the trailing case-participant/event/message writes.

Regression for the "timeout of 15000ms exceeded" axios error users hit on the
HR dashboard when Supabase pooler RTT spiked across the ~15 sequential DB ops
inside POST /api/hr/cases/{case_id}/assign. The fix defers six best-effort
side effects to a background pool. These tests verify that:

  1. create_assignment_with_contact_and_invites(defer_post_creation_hooks=True)
     returns immediately even if the underlying ensure_* services hang.
  2. run_assignment_post_creation_hooks swallows all per-hook exceptions
     (best-effort), matching pre-refactor behavior.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.database as dbmod
import backend.app.services.unified_assignment_creation as uac
from backend.database import Database
from backend.app.services.unified_assignment_creation import (
    create_assignment_with_contact_and_invites,
    run_assignment_post_creation_hooks,
)


def _seed_company(db: Database, company_id: str, name: str = "Test Co") -> None:
    now = datetime.utcnow().isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies (id, name, created_at) VALUES (:id, :n, :ca)"),
            {"id": company_id, "n": name, "ca": now},
        )


class HrAssignDeferredHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self._prev_engine = dbmod._engine
        self._prev_sqlite = dbmod._is_sqlite
        dbmod._engine = eng
        dbmod._is_sqlite = True
        self.db = Database()
        # The legacy DB initializes lazily via _exec, but _seed_company uses
        # engine.begin() directly. Force schema creation up front so the
        # test runs cleanly under a fresh in-memory engine.
        self.db.ensure_initialized()

    def tearDown(self) -> None:
        dbmod._engine = self._prev_engine
        dbmod._is_sqlite = self._prev_sqlite

    def test_create_assignment_with_defer_skips_post_creation_hooks(self) -> None:
        """defer_post_creation_hooks=True must NOT invoke the three ensure_* services."""
        co = f"co-defer-{uuid.uuid4().hex[:6]}"
        _seed_company(self.db, co)
        case_id = str(uuid.uuid4())
        self.db.create_case(case_id, "hr-defer", {}, company_id=co)

        calls: list[str] = []

        def _record(name: str):
            def _f(*_a, **_kw):
                calls.append(name)
            return _f

        # Each ensure_* is imported into unified_assignment_creation's namespace;
        # patch there so the deferral check is exercised.
        orig_mobility = uac.ensure_mobility_case_link_for_assignment
        orig_person = uac.ensure_employee_case_person_for_assignment
        orig_passport = uac.ensure_passport_case_document_for_assignment
        uac.ensure_mobility_case_link_for_assignment = _record("mobility")
        uac.ensure_employee_case_person_for_assignment = _record("person")
        uac.ensure_passport_case_document_for_assignment = _record("passport")
        try:
            r = create_assignment_with_contact_and_invites(
                self.db,
                company_id=co,
                hr_user_id="hr-defer",
                case_id=case_id,
                employee_identifier_raw="deferred@unico.example",
                employee_first_name=None,
                employee_last_name=None,
                employee_user_id=None,
                assignment_status="assigned",
                request_id=None,
                defer_post_creation_hooks=True,
            )
        finally:
            uac.ensure_mobility_case_link_for_assignment = orig_mobility
            uac.ensure_employee_case_person_for_assignment = orig_person
            uac.ensure_passport_case_document_for_assignment = orig_passport

        self.assertTrue(r.assignment_id)
        self.assertEqual(calls, [], "ensure_* hooks must be skipped when deferred")

    def test_create_assignment_default_runs_post_creation_hooks(self) -> None:
        """defer_post_creation_hooks=False (default) must run the three hooks."""
        co = f"co-inline-{uuid.uuid4().hex[:6]}"
        _seed_company(self.db, co)
        case_id = str(uuid.uuid4())
        self.db.create_case(case_id, "hr-inline", {}, company_id=co)

        calls: list[str] = []

        def _record(name: str):
            def _f(*_a, **_kw):
                calls.append(name)
            return _f

        orig_mobility = uac.ensure_mobility_case_link_for_assignment
        orig_person = uac.ensure_employee_case_person_for_assignment
        orig_passport = uac.ensure_passport_case_document_for_assignment
        uac.ensure_mobility_case_link_for_assignment = _record("mobility")
        uac.ensure_employee_case_person_for_assignment = _record("person")
        uac.ensure_passport_case_document_for_assignment = _record("passport")
        try:
            create_assignment_with_contact_and_invites(
                self.db,
                company_id=co,
                hr_user_id="hr-inline",
                case_id=case_id,
                employee_identifier_raw="inline@unico.example",
                employee_first_name=None,
                employee_last_name=None,
                employee_user_id=None,
                assignment_status="assigned",
                request_id=None,
            )
        finally:
            uac.ensure_mobility_case_link_for_assignment = orig_mobility
            uac.ensure_employee_case_person_for_assignment = orig_person
            uac.ensure_passport_case_document_for_assignment = orig_passport

        self.assertEqual(sorted(calls), ["mobility", "passport", "person"])

    def test_run_post_creation_hooks_swallows_each_failure(self) -> None:
        """A failing hook must not stop later hooks from running."""
        called: list[str] = []

        def _boom(*_a, **_kw):
            raise RuntimeError("simulated supabase outage")

        def _track(name: str):
            def _f(*_a, **_kw):
                called.append(name)
            return _f

        orig_mobility = uac.ensure_mobility_case_link_for_assignment
        orig_person = uac.ensure_employee_case_person_for_assignment
        orig_passport = uac.ensure_passport_case_document_for_assignment
        uac.ensure_mobility_case_link_for_assignment = _boom
        uac.ensure_employee_case_person_for_assignment = _track("person")
        uac.ensure_passport_case_document_for_assignment = _track("passport")
        try:
            # Should not raise.
            run_assignment_post_creation_hooks(self.db, "any-aid", request_id=None)
        finally:
            uac.ensure_mobility_case_link_for_assignment = orig_mobility
            uac.ensure_employee_case_person_for_assignment = orig_person
            uac.ensure_passport_case_document_for_assignment = orig_passport

        self.assertEqual(called, ["person", "passport"])

    def test_deferred_path_returns_before_hooks_would_finish(self) -> None:
        """Service returns promptly when hooks are deferred, even if they would hang."""
        co = f"co-fast-{uuid.uuid4().hex[:6]}"
        _seed_company(self.db, co)
        case_id = str(uuid.uuid4())
        self.db.create_case(case_id, "hr-fast", {}, company_id=co)

        def _hang(*_a, **_kw):
            time.sleep(30)

        orig_mobility = uac.ensure_mobility_case_link_for_assignment
        orig_person = uac.ensure_employee_case_person_for_assignment
        orig_passport = uac.ensure_passport_case_document_for_assignment
        uac.ensure_mobility_case_link_for_assignment = _hang
        uac.ensure_employee_case_person_for_assignment = _hang
        uac.ensure_passport_case_document_for_assignment = _hang
        try:
            t0 = time.perf_counter()
            r = create_assignment_with_contact_and_invites(
                self.db,
                company_id=co,
                hr_user_id="hr-fast",
                case_id=case_id,
                employee_identifier_raw="fast@unico.example",
                employee_first_name=None,
                employee_last_name=None,
                employee_user_id=None,
                assignment_status="assigned",
                request_id=None,
                defer_post_creation_hooks=True,
            )
            elapsed = time.perf_counter() - t0
        finally:
            uac.ensure_mobility_case_link_for_assignment = orig_mobility
            uac.ensure_employee_case_person_for_assignment = orig_person
            uac.ensure_passport_case_document_for_assignment = orig_passport

        self.assertTrue(r.assignment_id)
        # Should be well under 1s on an in-memory SQLite. 5s is generous and
        # still proves we didn't sleep through the hooks.
        self.assertLess(
            elapsed,
            5.0,
            f"deferred create returned in {elapsed:.2f}s — hooks still ran inline",
        )


if __name__ == "__main__":
    unittest.main()
