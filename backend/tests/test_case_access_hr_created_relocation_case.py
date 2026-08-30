"""AIQ-2031 — GET /api/cases/{id} 404s for the HR user who created the case,
until an employee is assigned.

`_assert_case_access` (the shared tenant guard behind GET /api/cases/{id}) knew
only two id homes: public.cases (legacy seed) and case_assignments →
relocation_cases. An HR-created case lives in public.relocation_cases from
creation — `hr_user_id` + `company_id` are set — but has NO public.cases row and
NO case_assignments row until an employee is assigned. So the guard resolved
nothing and raised 404 for the very HR user who created the case, while PATCH
(create-on-missing, which skips the guard) and GET /api/hr/cases/{id} both
succeeded (VERIFIED PROD 2026-08-20).

These tests pin the added relocation_cases fallback: the creator, same-company HR
and admin are granted; a cross-tenant HR, and a non-owner employee, are forbidden
(403); an unknown id is still 404; and the pre-existing assignment path is
unchanged. Deterministic: in-memory SQLite with the case_service engine patched.
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


def _u() -> str:
    return str(uuid.uuid4())


_SCHEMA = """
CREATE TABLE cases (id TEXT, company_id TEXT, employee_id TEXT, hr_owner_id TEXT);
CREATE TABLE case_assignments (id TEXT, employee_user_id TEXT, hr_user_id TEXT, canonical_case_id TEXT, case_id TEXT);
CREATE TABLE relocation_cases (id TEXT, hr_user_id TEXT, employee_id TEXT, company_id TEXT, status TEXT);
CREATE TABLE profiles (id TEXT, company_id TEXT);
"""


class HrCreatedRelocationCaseAccessTests(unittest.TestCase):
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
        self.hr_uuid = _u()
        self.case_id = _u()  # relocation_cases.id (also the canonical case id)

    # --- seeding -----------------------------------------------------------
    def _seed_relocation_case(self, **over):
        row = {
            "id": self.case_id, "hr_user_id": self.hr_uuid, "employee_id": None,
            "company_id": self.company_id, "status": "draft",
        }
        row.update(over)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO relocation_cases (id, hr_user_id, employee_id, company_id, status) "
                     "VALUES (:id, :hr_user_id, :employee_id, :company_id, :status)"),
                row,
            )

    def _seed_profile(self, pid, company_id):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, company_id) VALUES (:id, :co)"),
                {"id": pid, "co": company_id},
            )

    def _seed_assignment(self, **over):
        row = {
            "id": _u(), "employee_user_id": None, "hr_user_id": None,
            "canonical_case_id": self.case_id, "case_id": self.case_id,
        }
        row.update(over)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_assignments (id, employee_user_id, hr_user_id, canonical_case_id, case_id) "
                     "VALUES (:id, :employee_user_id, :hr_user_id, :canonical_case_id, :case_id)"),
                row,
            )

    def _user(self, uid, role, is_admin=False):
        return {"id": uid, "auth_uuid": uid, "role": role, "is_admin": is_admin}

    # --- the fix -----------------------------------------------------------
    def test_hr_creator_reads_own_unassigned_case(self):
        """The core regression (fails on origin/main with 404)."""
        self._seed_relocation_case()
        resolved = case_service._assert_case_access(
            self._user(self.hr_uuid, "HR"), self.case_id
        )
        self.assertEqual(resolved, self.case_id)

    def test_same_company_hr_reads_unassigned_case(self):
        self._seed_relocation_case()  # created by self.hr_uuid
        other_hr = _u()
        self._seed_profile(other_hr, self.company_id)  # same company
        resolved = case_service._assert_case_access(
            self._user(other_hr, "HR"), self.case_id
        )
        self.assertEqual(resolved, self.case_id)

    def test_admin_reads_unassigned_case(self):
        self._seed_relocation_case()
        resolved = case_service._assert_case_access(
            self._user(_u(), "ADMIN", is_admin=True), self.case_id
        )
        self.assertEqual(resolved, self.case_id)

    # --- negative / isolation ---------------------------------------------
    def test_cross_tenant_hr_forbidden(self):
        self._seed_relocation_case()  # company co-1
        foreign_hr = _u()
        self._seed_profile(foreign_hr, "co-OTHER")  # different company
        with self.assertRaises(HTTPException) as ctx:
            case_service._assert_case_access(self._user(foreign_hr, "HR"), self.case_id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_non_owner_employee_forbidden(self):
        self._seed_relocation_case()
        with self.assertRaises(HTTPException) as ctx:
            case_service._assert_case_access(self._user(_u(), "EMPLOYEE"), self.case_id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unknown_case_id_404(self):
        # nothing seeded for this id in any table
        with self.assertRaises(HTTPException) as ctx:
            case_service._assert_case_access(self._user(self.hr_uuid, "HR"), _u())
        self.assertEqual(ctx.exception.status_code, 404)

    # --- regression: the pre-existing assignment path is unchanged ---------
    def test_assignment_path_still_grants_employee(self):
        emp = _u()
        self._seed_relocation_case(employee_id=None)
        self._seed_assignment(employee_user_id=emp)  # employee owns via assignment
        resolved = case_service._assert_case_access(self._user(emp, "EMPLOYEE"), self.case_id)
        self.assertEqual(resolved, self.case_id)


if __name__ == "__main__":
    unittest.main()
