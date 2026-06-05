"""Regression: an employee can access an HR-created case by its case id.

Defect (found 2026-06-05 diagnosing why the employee roadmap/dossier are empty
platform-wide): ``_assert_case_access`` resolved the case→assignment link only by
``case_assignments.id`` (assignment id), so an employee passing a *case id* (the
canonical/relocation_cases id) for an HR-created case got **404** even though the
``case_assignments`` row correctly links them. The fix resolves by
``id`` / ``canonical_case_id`` / ``case_id`` and treats the assignment as the
authoritative employee↔case link — necessary because ``public.cases.employee_id``
holds a contact UUID, not the caller's (possibly legacy text) id.

The companion change — ``Database._ensure_canonical_case_from_wizard`` bridging
the wizard intake into the canonical ``public.cases`` row the trigger reads — is
a fail-safe data sync verified live on prod (it lives on the DB object that this
suite mocks, so it can't be exercised here without a real DB).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./ci_test_case_bridge.db")

import unittest
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.app.services import case_service
from backend.app.services.case_service import _assert_case_access

CASE = "cccccccc-cccc-cccc-cccc-cccccccccccc"
OTHER = "dddddddd-dddd-dddd-dddd-dddddddddddd"
EMP_UUID = "e0d4fd90-0000-0000-0000-000000000001"


class AssignmentBasedCaseAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        # Shared in-memory SQLite so tables persist across connections, injected
        # in place of the conftest-mocked main_db.engine.
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE case_assignments "
                "(id TEXT, case_id TEXT, canonical_case_id TEXT, employee_user_id TEXT, "
                "hr_user_id TEXT, employee_contact_id TEXT)"
            ))
            c.execute(text("CREATE TABLE relocation_cases (id TEXT, company_id TEXT)"))
            c.execute(text(
                "INSERT INTO case_assignments "
                "(id, case_id, canonical_case_id, employee_user_id, hr_user_id, employee_contact_id) "
                "VALUES ('asgn-1', :c, :c, 'emp-1', 'hr-1', :emp)"
            ), {"c": CASE, "emp": EMP_UUID})
            c.execute(text("INSERT INTO relocation_cases (id, company_id) VALUES (:c, 'co-1')"), {"c": CASE})
        self._p = mock.patch.object(case_service.main_db, "engine", self.engine)
        self._p.start()
        self.addCleanup(self._p.stop)

    def _add_cases_row(self, employee_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(text(
                "CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, company_id TEXT, "
                "employee_id TEXT, hr_owner_id TEXT)"
            ))
            c.execute(text(
                "INSERT INTO cases (id, company_id, employee_id) VALUES (:c, 'co-1', :e)"
            ), {"c": CASE, "e": employee_id})

    def test_owning_employee_granted_by_case_id_no_cases_row(self) -> None:
        # The fix: resolve via case_id/canonical_case_id (was: only ca.id → 404).
        try:
            _assert_case_access({"id": "emp-1", "role": "EMPLOYEE"}, CASE)
        except HTTPException as e:  # pragma: no cover
            self.fail(f"owning employee should be granted, got {e.status_code} {e.detail}")

    def test_owning_employee_granted_even_when_cases_row_has_contact_uuid(self) -> None:
        # public.cases.employee_id holds the CONTACT uuid (≠ caller id) — access
        # must still be granted via the authoritative assignment link.
        self._add_cases_row(employee_id=EMP_UUID)
        try:
            _assert_case_access({"id": "emp-1", "role": "EMPLOYEE"}, CASE)
        except HTTPException as e:  # pragma: no cover
            self.fail(f"owner should be granted via assignment, got {e.status_code}")

    def test_non_owner_employee_forbidden(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access({"id": "emp-99", "role": "EMPLOYEE"}, CASE)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unknown_case_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _assert_case_access({"id": "emp-1", "role": "EMPLOYEE"}, OTHER)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
