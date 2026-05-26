"""
AUDIT-A2-followup regression test — `_assert_case_access` on budget-summary.

Mirrors the AIQ-355 / AUDIT-A2 fix on `get_case`: ensures cross-tenant or
unauthorised callers can't read another case's budget summary just by
passing a different case_id in the URL.

Test matrix (5 scenarios):

  1. Employee who owns the case      → 200, payload returned
  2. HR in the case's company        → 200, payload returned
  3. HR in a different company       → 403 'Not authorised for this case'
  4. Employee viewing a foreign case → 403
  5. Unknown case_id                 → 404 'Case not found'

Same pattern as test_b12b_employee_cases.py — handlers called directly to
sidestep the FastAPI middleware stack (which expects a live database the
root conftest mocks out).
"""
from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

# Pre-empt install_query_counter — same pattern used by other tests that
# import backend.app.routers (see test_b12b_employee_cases.py).
_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.routers import cases as cases_router  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────

EMPLOYEE_USER = {
    "id": "emp-user-1",
    "role": "employee",
    "is_admin": False,
    "email": "employee@example.test",
}

HR_USER_SAME_COMPANY = {
    "id": "hr-user-1",
    "role": "HR",
    "is_admin": False,
    "company_id": "company-abc",
    "email": "hr@company-abc.test",
}

HR_USER_OTHER_COMPANY = {
    "id": "hr-user-2",
    "role": "HR",
    "is_admin": False,
    "company_id": "company-xyz",
    "email": "hr@company-xyz.test",
}

OTHER_EMPLOYEE = {
    "id": "emp-user-99",
    "role": "employee",
    "is_admin": False,
    "email": "stranger@example.test",
}

# Case "case-1" belongs to employee-user-1 and lives in company-abc.
CASE_ROW = {
    "id": "case-1",
    "company_id": "company-abc",
    "employee_id": "emp-user-1",
    "hr_owner_id": None,
}

PROFILE_ROW_SAME_COMPANY = {"company_id": "company-abc"}
PROFILE_ROW_OTHER_COMPANY = {"company_id": "company-xyz"}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mock_engine_returning(case_row, profile_row):
    """Build a context-managed engine.connect() chain that returns the given rows.

    The order of execute() calls inside _assert_case_access is:
      1. SELECT id, company_id, employee_id, hr_owner_id FROM cases
      2. (HR branch only) SELECT company_id FROM profiles

    We return case_row first, then profile_row, regardless of branch — the
    HR-branch code only calls .execute the second time for HR roles, so
    employee tests never reach the second result.
    """
    case_mappings = MagicMock()
    case_mappings.first.return_value = case_row

    profile_mappings = MagicMock()
    profile_mappings.first.return_value = profile_row

    case_exec = MagicMock()
    case_exec.mappings.return_value = case_mappings
    profile_exec = MagicMock()
    profile_exec.mappings.return_value = profile_mappings

    conn = MagicMock()
    conn.execute.side_effect = [case_exec, profile_exec, case_exec, profile_exec]

    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = False

    engine = MagicMock()
    engine.connect.return_value = ctx
    return engine


def _mock_session_local_returning(case_obj):
    """Build a SessionLocal context manager that returns a session whose
    crud.get_case returns case_obj. The handler only needs the session
    to feed crud.get_case; nothing else is called on it."""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = False
    return ctx, session


# ── Tests ───────────────────────────────────────────────────────────────────

class TestBudgetSummaryAuth(unittest.TestCase):
    """AUDIT-A2-followup: budget-summary must respect case access boundaries."""

    def test_employee_owner_gets_200(self):
        engine = _mock_engine_returning(CASE_ROW, PROFILE_ROW_SAME_COMPANY)
        with patch.object(cases_router.main_db, "engine", engine), \
             patch.object(cases_router.main_db, "get_profile_record", return_value=PROFILE_ROW_SAME_COMPANY), \
             patch.object(cases_router, "main_db", new=cases_router.main_db), \
             patch.object(cases_router.main_db, "list_hr_policies_by_company", return_value=[]):
            ctx, session = _mock_session_local_returning(None)
            with patch.object(cases_router, "SessionLocal", return_value=ctx), \
                 patch.object(cases_router.crud, "get_case", return_value=None):
                body = cases_router.get_budget_summary("case-1", EMPLOYEE_USER)

        self.assertEqual(body["case_id"], "case-1")
        self.assertIn("categories", body)

    def test_hr_same_company_gets_200(self):
        engine = _mock_engine_returning(CASE_ROW, PROFILE_ROW_SAME_COMPANY)
        with patch.object(cases_router.main_db, "engine", engine), \
             patch.object(cases_router.main_db, "get_profile_record", return_value=PROFILE_ROW_SAME_COMPANY), \
             patch.object(cases_router.main_db, "list_hr_policies_by_company", return_value=[]):
            ctx, _ = _mock_session_local_returning(None)
            with patch.object(cases_router, "SessionLocal", return_value=ctx), \
                 patch.object(cases_router.crud, "get_case", return_value=None):
                body = cases_router.get_budget_summary("case-1", HR_USER_SAME_COMPANY)

        self.assertEqual(body["case_id"], "case-1")

    def test_hr_different_company_gets_403(self):
        engine = _mock_engine_returning(CASE_ROW, PROFILE_ROW_OTHER_COMPANY)
        with patch.object(cases_router.main_db, "engine", engine):
            with self.assertRaises(HTTPException) as ctx:
                cases_router.get_budget_summary("case-1", HR_USER_OTHER_COMPANY)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Not authorised", str(ctx.exception.detail))

    def test_other_employee_gets_403(self):
        engine = _mock_engine_returning(CASE_ROW, None)
        with patch.object(cases_router.main_db, "engine", engine):
            with self.assertRaises(HTTPException) as ctx:
                cases_router.get_budget_summary("case-1", OTHER_EMPLOYEE)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_missing_case_gets_404(self):
        engine = _mock_engine_returning(None, None)
        with patch.object(cases_router.main_db, "engine", engine):
            with self.assertRaises(HTTPException) as ctx:
                cases_router.get_budget_summary("nonexistent-case", EMPLOYEE_USER)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("not found", str(ctx.exception.detail).lower())


if __name__ == "__main__":
    unittest.main()
