"""
AUTH-ID-2 (AIQ — case-access guard): legacy session id ↔ Supabase UUID in the
shared case-access guard.

`case_service._assert_case_access` is the guard behind the dossier / case-read
endpoints. It compares the caller against uuid-typed ownership columns
(`employee_user_id`, `hr_user_id`, `employee_id`, `hr_owner_id`) and the
`profiles` company. Before AUTH-ID-2 it compared the raw `user["id"]` — a
non-UUID text id for legacy/seed accounts — so a legacy employee was wrongly
denied access to their OWN case (the guard is fail-safe and never 500s, so the
symptom was a false 403, not a crash).

AUTH-ID-2 matches ownership against the caller's canonical `auth_uuid`
(resolved by AUTH-ID-1) as well as their raw id. These tests pin that:
  - a legacy employee whose auth_uuid matches the case owner is GRANTED;
  - an unmappable legacy caller (auth_uuid=None) is cleanly FORBIDDEN (403);
  - UUID-native callers and the admin / HR-company paths are unchanged.

Deterministic: in-memory SQLite, the case_service engine patched. No network.
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
CREATE TABLE case_assignments (id TEXT, employee_user_id TEXT, hr_user_id TEXT, canonical_case_id TEXT);
CREATE TABLE relocation_cases (id TEXT, company_id TEXT);
CREATE TABLE profiles (id TEXT, company_id TEXT);
"""


class CaseAccessAuthUuidTests(unittest.TestCase):
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
        self.employee_uuid = _u()
        self.hr_uuid = _u()
        self.case_id = _u()  # a public.cases id (UUID, passes _UUID_RE)

    def _seed_case(self, **over):
        row = {
            "id": self.case_id, "company_id": self.company_id,
            "employee_id": self.employee_uuid, "hr_owner_id": None,
        }
        row.update(over)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO cases (id, company_id, employee_id, hr_owner_id) "
                     "VALUES (:id, :company_id, :employee_id, :hr_owner_id)"),
                row,
            )

    def _seed_assignment(self, assignment_id, **over):
        row = {
            "id": assignment_id, "employee_user_id": self.employee_uuid,
            "hr_user_id": None, "canonical_case_id": _u(),
        }
        row.update(over)
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO case_assignments "
                     "(id, employee_user_id, hr_user_id, canonical_case_id) "
                     "VALUES (:id, :employee_user_id, :hr_user_id, :canonical_case_id)"),
                row,
            )

    def _seed_profile(self, pid, company_id):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO profiles (id, company_id) VALUES (:id, :c)"),
                {"id": pid, "c": company_id},
            )

    # --- cases path ---------------------------------------------------------

    def test_legacy_employee_with_matching_auth_uuid_is_granted(self):
        self._seed_case()
        user = {"id": "seed-emp-testingapril", "auth_uuid": self.employee_uuid, "role": "EMPLOYEE"}
        # Must not raise.
        case_service._assert_case_access(user, self.case_id)

    def test_unmappable_legacy_caller_is_forbidden_not_500(self):
        self._seed_case()
        user = {"id": "seed-emp-testingapril", "auth_uuid": None, "role": "EMPLOYEE"}
        with self.assertRaises(HTTPException) as ctx:
            case_service._assert_case_access(user, self.case_id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_uuid_native_employee_unchanged(self):
        self._seed_case()
        user = {"id": self.employee_uuid, "auth_uuid": self.employee_uuid, "role": "EMPLOYEE"}
        case_service._assert_case_access(user, self.case_id)  # granted

    def test_non_owner_is_forbidden(self):
        self._seed_case()
        user = {"id": "seed-emp-other", "auth_uuid": _u(), "role": "EMPLOYEE"}
        with self.assertRaises(HTTPException) as ctx:
            case_service._assert_case_access(user, self.case_id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_bypass_unchanged(self):
        self._seed_case()
        user = {"id": "admin-legacy", "auth_uuid": None, "is_admin": True, "role": "ADMIN"}
        case_service._assert_case_access(user, self.case_id)  # granted

    def test_legacy_hr_company_match_via_auth_uuid(self):
        # HR owns no row directly but belongs to the case's company; the profiles
        # lookup must resolve via auth_uuid (legacy text id would never match).
        self._seed_case(employee_id=_u())  # not this HR user
        self._seed_profile(self.hr_uuid, self.company_id)
        user = {"id": "seed-hr-legacy", "auth_uuid": self.hr_uuid, "role": "HR"}
        case_service._assert_case_access(user, self.case_id)  # granted by company match

    # --- assignment path (no cases row → resolve case_assignments) ----------

    def test_legacy_employee_owns_assignment_via_auth_uuid(self):
        assignment_id = _u()
        self._seed_assignment(assignment_id)  # employee_user_id = self.employee_uuid
        user = {"id": "seed-emp-testingapril", "auth_uuid": self.employee_uuid, "role": "EMPLOYEE"}
        case_service._assert_case_access(user, assignment_id)  # granted

    def test_assignment_unmappable_legacy_forbidden(self):
        assignment_id = _u()
        self._seed_assignment(assignment_id)
        user = {"id": "seed-emp-testingapril", "auth_uuid": None, "role": "EMPLOYEE"}
        with self.assertRaises(HTTPException) as ctx:
            case_service._assert_case_access(user, assignment_id)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
