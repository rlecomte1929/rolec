"""[WS2] Behavioral tenant-isolation tests for the HR case-scope guards.

The source-guard tests (test_hr_assign_tenant_scope.py, test_hr_mutation_tenant_scope.py)
assert each mutation *endpoint* CALLS a scope check — they guard the wiring.
This file guards the BOUNDARY LOGIC itself: given a two-tenant fixture, it
exercises the real `_hr_can_access_assignment` / `_assert_hr_can_mutate_case`
functions from backend.main and asserts that company A's HR cannot reach
company B's assignment/case, while same-tenant + admin + owner paths still work.

If someone "simplifies" the company comparison, flips a branch, or returns the
wrong default, these tests fail — which the grep-style source-guards cannot catch.

Why a fake db and not sqlite: the real accessors (assignment_belongs_to_company,
get_assignment_by_case_id, get_case_by_id) are Postgres-specific SQL in
database.py and don't run on sqlite. The security DECISION lives in the two
helper functions; the fake db reproduces the accessors' semantics faithfully so
the test isolates and verifies that decision logic. The accessors themselves are
covered by the live two-tenant probe (scripts/verify_tenant_isolation.py).
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

from fastapi import HTTPException

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backend.main as main  # noqa: E402


# ── Two-tenant fixture ──────────────────────────────────────────────────────
# Company A: HR "hr-a", case "case-a" via assignment "asgn-a".
# Company B: HR "hr-b", case "case-b" via assignment "asgn-b".
_HR_COMPANY = {"hr-a": "company-a", "hr-b": "company-b"}
_ASSIGNMENTS = {
    "asgn-a": {"id": "asgn-a", "hr_user_id": "hr-a", "company_id": "company-a"},
    "asgn-b": {"id": "asgn-b", "hr_user_id": "hr-b", "company_id": "company-b"},
    # Owned by hr-a but parked under company-b — exercises the owner-override path.
    "asgn-owned": {"id": "asgn-owned", "hr_user_id": "hr-a", "company_id": "company-b"},
}
_CASE_ASSIGNMENT = {"case-a": "asgn-a", "case-b": "asgn-b"}
_CASES = {
    "case-a": {"id": "case-a", "company_id": "company-a", "hr_user_id": "hr-a"},
    "case-b": {"id": "case-b", "company_id": "company-b", "hr_user_id": "hr-b"},
}


class _FakeDB:
    """Faithful in-memory stand-in for the db accessors the guards call."""

    def get_user_by_id(self, uid):  # only hit on impersonation (unused here)
        return None

    def get_hr_company_id(self, uid):
        return _HR_COMPANY.get(uid)

    def get_profile_record(self, uid):
        return {}

    def assignment_belongs_to_company(self, assignment_id, company_id):
        a = _ASSIGNMENTS.get(assignment_id)
        return bool(a and a.get("company_id") == company_id)

    def get_assignment_by_case_id(self, case_id, request_id=None):
        return _ASSIGNMENTS.get(_CASE_ASSIGNMENT.get(case_id))

    def get_case_by_id(self, case_id):
        return _CASES.get(case_id)


HR_A = {"id": "hr-a", "role": "hr"}
HR_B = {"id": "hr-b", "role": "hr"}
ADMIN = {"id": "admin-1", "role": "hr", "is_admin": True}


class TenantIsolationBehavioralTest(unittest.TestCase):
    def setUp(self):
        self._patch = mock.patch.object(main, "db", _FakeDB())
        self._patch.start()
        self.addCleanup(self._patch.stop)

    # ── _hr_can_access_assignment ───────────────────────────────────────────
    def test_same_company_hr_can_access_own_assignment(self):
        self.assertTrue(main._hr_can_access_assignment(_ASSIGNMENTS["asgn-a"], HR_A))

    def test_cross_tenant_hr_cannot_access_other_companys_assignment(self):
        # The ISO-3 leak: HR from company A must NOT reach company B's assignment.
        self.assertFalse(main._hr_can_access_assignment(_ASSIGNMENTS["asgn-b"], HR_A))

    def test_admin_can_access_any_assignment(self):
        self.assertTrue(main._hr_can_access_assignment(_ASSIGNMENTS["asgn-b"], ADMIN))

    def test_owner_hr_can_access_assignment_in_another_company(self):
        # Owner override: hr-a owns asgn-owned even though it sits under company-b.
        self.assertTrue(main._hr_can_access_assignment(_ASSIGNMENTS["asgn-owned"], HR_A))

    # ── _assert_hr_can_mutate_case ──────────────────────────────────────────
    def test_same_tenant_mutate_allowed(self):
        # No raise == allowed.
        main._assert_hr_can_mutate_case("case-a", HR_A)

    def test_cross_tenant_mutate_raises_404(self):
        with self.assertRaises(HTTPException) as ctx:
            main._assert_hr_can_mutate_case("case-b", HR_A)
        # 404 (not 403) so we never leak that the case exists.
        self.assertEqual(ctx.exception.status_code, 404)

    def test_admin_mutate_any_case_allowed(self):
        main._assert_hr_can_mutate_case("case-b", ADMIN)

    def test_unknown_case_raises_404(self):
        with self.assertRaises(HTTPException) as ctx:
            main._assert_hr_can_mutate_case("case-does-not-exist", HR_A)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_symmetric_b_cannot_reach_a(self):
        # Isolation is symmetric — B's HR is equally walled off from A.
        self.assertFalse(main._hr_can_access_assignment(_ASSIGNMENTS["asgn-a"], HR_B))
        with self.assertRaises(HTTPException) as ctx:
            main._assert_hr_can_mutate_case("case-a", HR_B)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
