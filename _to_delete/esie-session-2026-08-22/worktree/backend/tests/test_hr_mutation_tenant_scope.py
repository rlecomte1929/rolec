"""Security guard: every HR case/assignment MUTATION endpoint must enforce the
tenant (company) boundary, so an HR from company A cannot mutate company B's
case/assignment.

The tenant-isolation probe found `assign_case` lacked this (HR A could assign on
B's case); an audit of the sibling mutation endpoints found 9 more with the same
gap. The handlers run parallel futures / raw SQL, so functional unit tests are
impractical here — guard at source (each handler must reference one of the
scope checks: `_hr_can_access_assignment` or `_assert_hr_can_mutate_case`, or for
the coordination router a company/org comparison). Behaviour verified live.
"""
from __future__ import annotations

import os
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _fn_body(src: str, marker: str, end_token: str) -> str:
    start = src.index(marker)
    end = src.index(end_token, start + len(marker))
    return src[start:end]


class HrMutationTenantScopeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(os.path.join(_REPO, "backend", "main.py"), encoding="utf-8") as fh:
            cls.main_src = fh.read()
        with open(os.path.join(_REPO, "backend", "app", "routers", "hr_coordination.py"), encoding="utf-8") as fh:
            cls.coord_src = fh.read()

    def _assert_main_scoped(self, fn: str) -> None:
        body = _fn_body(self.main_src, f"def {fn}(", "\n@app.")
        self.assertTrue(
            ("_hr_can_access_assignment" in body) or ("_assert_hr_can_mutate_case" in body),
            f"{fn} is missing a tenant-scope check (cross-tenant mutation risk)",
        )

    def test_update_assignment_identifier(self):
        self._assert_main_scoped("update_assignment_identifier")

    def test_run_compliance(self):
        self._assert_main_scoped("run_compliance")

    def test_hr_decision(self):
        self._assert_main_scoped("hr_decision")

    def test_run_case_compliance(self):
        self._assert_main_scoped("run_case_compliance")

    def test_create_policy_exception(self):
        self._assert_main_scoped("create_policy_exception")

    def test_record_compliance_action(self):
        self._assert_main_scoped("record_compliance_action")

    def test_review_employee_task(self):
        self._assert_main_scoped("review_employee_task")

    def test_create_case_task_for_hr(self):
        self._assert_main_scoped("create_case_task_for_hr")

    def test_coordination_assign_task_scoped(self):
        body = _fn_body(self.coord_src, "def assign_task(", "\n@router.")
        self.assertIn("company_id", body)
        self.assertIn("org_id", body)
        self.assertIn("Case not found", body)


class HrComplianceReadTenantScopeGuardTests(unittest.TestCase):
    """AIQ-1474: the /hr/compliance page's two READ endpoints (get_hr_policy,
    get_case_compliance) were missing the company/owner tenant-scope check their
    sibling write endpoints already enforce — a cross-tenant read (IDOR) given a
    valid id. Guard at source, same rationale as the mutation suite above."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(os.path.join(_REPO, "backend", "main.py"), encoding="utf-8") as fh:
            cls.main_src = fh.read()

    def _assert_read_scoped(self, fn: str) -> None:
        body = _fn_body(self.main_src, f"def {fn}(", "\n@app.")
        self.assertIn(
            "_hr_can_access_assignment",
            body,
            f"{fn} is missing a tenant-scope check (cross-tenant read / IDOR risk)",
        )

    def test_get_hr_policy_scoped(self):
        self._assert_read_scoped("get_hr_policy")

    def test_get_case_compliance_scoped(self):
        self._assert_read_scoped("get_case_compliance")


if __name__ == "__main__":
    unittest.main()
