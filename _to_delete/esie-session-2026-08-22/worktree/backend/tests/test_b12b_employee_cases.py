"""
B12b regression test — GET /api/cases for the authenticated employee.

Validates that the root route on the cases router (added to fix B12b — the
employee-portal endpoint previously returned 404) behaves correctly:

  1. Employee with assignments    → 200 + populated cases array
  2. Employee with no assignments → 200 + empty cases array
  3. HR token (role isolation)    → 200 + empty cases array (HR uses /api/hr/cases)
  4. Route is registered          → not a 404 / 405

The route fix was AIQ-425. Companion to test_b12_list_cases.py, which covers
the HR-side GET /api/hr/cases endpoint from the prior B12 task (AIQ-278).

This test exercises the handler function directly rather than going through
the full FastAPI middleware stack — backend.main installs middleware that
expects a live (non-mocked) database, which the repo's root conftest mocks
out. The handler signature accepts a `Request` and the auth-injected `user`
dict, so unit-level coverage is straightforward and avoids the middleware.
"""
from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Pre-empt the import-time call to `install_query_counter(db.engine)` in
# backend.main — the root conftest mocks `backend.database`, so `db.engine` is
# a MagicMock and the SQLAlchemy event listener registration raises.
_qc_mod = MagicMock()
_qc_mod.install_query_counter = lambda *a, **kw: None
sys.modules.setdefault("backend.app.services.query_counter", _qc_mod)

from backend.app.routers import cases as cases_router  # noqa: E402


EMPLOYEE_USER = {
    "id": "emp-user-1",
    "role": "employee",
    "is_admin": False,
    "email": "employee@example.test",
}

HR_USER = {
    "id": "hr-user-1",
    "role": "HR",
    "is_admin": False,
    "company_id": "company-abc",
    "email": "hr@example.test",
}

FAKE_ASSIGNMENTS = [
    {
        "id": "assignment-1",
        "case_id": "case-1",
        "status": "active",
        "employee_identifier": "emp-id-1",
        "created_at": "2026-05-26T10:00:00Z",
    },
    {
        "id": "assignment-2",
        "case_id": "case-2",
        "status": "active",
        "employee_identifier": "emp-id-1",
        "created_at": "2026-05-25T10:00:00Z",
    },
]


def _fake_request() -> SimpleNamespace:
    """Minimal stand-in for fastapi.Request — handler only reads request.state."""
    return SimpleNamespace(state=SimpleNamespace(request_id="test-req-1"))


class TestB12bEmployeeCases(unittest.TestCase):
    """B12b: GET /api/cases must populate for employees and isolate HR."""

    # ------------------------------------------------------------------
    # Scenario 1: employee with assignments → 200 + populated array
    # ------------------------------------------------------------------
    def test_employee_with_assignments_returns_cases(self):
        with patch.object(
            cases_router.main_db,
            "list_linked_assignments_for_employee",
            return_value=FAKE_ASSIGNMENTS,
        ):
            body = cases_router.list_employee_cases(_fake_request(), EMPLOYEE_USER)

        self.assertIn("cases", body)
        self.assertEqual(len(body["cases"]), 2)
        self.assertEqual(body["cases"][0]["caseId"], "case-1")
        self.assertEqual(body["cases"][0]["assignmentId"], "assignment-1")
        self.assertEqual(body["cases"][1]["caseId"], "case-2")

    # ------------------------------------------------------------------
    # Scenario 2: employee with no assignments → empty list
    # ------------------------------------------------------------------
    def test_employee_with_no_assignments_returns_empty(self):
        with patch.object(
            cases_router.main_db,
            "list_linked_assignments_for_employee",
            return_value=[],
        ):
            body = cases_router.list_employee_cases(_fake_request(), EMPLOYEE_USER)

        self.assertEqual(body, {"cases": []})

    # ------------------------------------------------------------------
    # Scenario 3: HR user → empty list (role isolation)
    # HR must not see employee cases through this endpoint; the dedicated
    # /api/hr/cases route is the canonical HR-side surface.
    # ------------------------------------------------------------------
    def test_hr_user_gets_empty_cases(self):
        # The DB helper should NOT even be called for non-employees — but
        # patch it defensively to make any incidental call obvious.
        with patch.object(
            cases_router.main_db,
            "list_linked_assignments_for_employee",
            return_value=FAKE_ASSIGNMENTS,
        ) as helper:
            body = cases_router.list_employee_cases(_fake_request(), HR_USER)

        self.assertEqual(body, {"cases": []})
        helper.assert_not_called()

    # ------------------------------------------------------------------
    # Scenario 4: DB error degrades to empty (never raises)
    # ------------------------------------------------------------------
    def test_db_error_degrades_to_empty(self):
        with patch.object(
            cases_router.main_db,
            "list_linked_assignments_for_employee",
            side_effect=RuntimeError("db kaboom"),
        ):
            body = cases_router.list_employee_cases(_fake_request(), EMPLOYEE_USER)

        self.assertEqual(body, {"cases": []})

    # ------------------------------------------------------------------
    # Scenario 5: route is registered on the cases router (not 404/405)
    # ------------------------------------------------------------------
    def test_route_registered_on_router(self):
        paths = {
            (route.path, tuple(sorted(route.methods or [])))
            for route in cases_router.router.routes
        }
        self.assertIn(("/api/cases", ("GET",)), paths)


if __name__ == "__main__":
    unittest.main()
