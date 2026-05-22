"""
B5 security regression test — GET /api/hr/cases/{case_id} company isolation.

Four scenarios:
  1. HR user from company-a  → GET case owned by company-a  → 200
  2. HR user from company-b  → GET case owned by company-a  → 404  (cross-tenant blocked)
  3. Admin user              → GET case owned by company-a  → 200  (admin bypass)
  4. HR user from company-a  → GET nonexistent case         → 404
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, get_current_user, UserRole

# ---------------------------------------------------------------------------
# Fake user fixtures
# ---------------------------------------------------------------------------

_HR_A: Dict[str, Any] = {
    "id": "user-hr-a",
    "role": UserRole.HR.value,
    "email": "hr-a@company-a.test",
    "is_admin": False,
}

_HR_B: Dict[str, Any] = {
    "id": "user-hr-b",
    "role": UserRole.HR.value,
    "email": "hr-b@company-b.test",
    "is_admin": False,
}

_ADMIN: Dict[str, Any] = {
    "id": "user-admin",
    "role": UserRole.ADMIN.value,
    "email": "admin@relopass.com",
    "is_admin": True,
}

# Fake case belonging to company-a
_CASE_A: Dict[str, Any] = {
    "id": "case-a",
    "company_id": "company-a",
    "hr_user_id": "user-hr-a",
    "employee_id": "emp-a",
    "status": "created",
}

# company_id map for HR users
_HR_COMPANY: Dict[str, str] = {
    "user-hr-a": "company-a",
    "user-hr-b": "company-b",
}


def _make_dependency_override(fake_user: Dict[str, Any]):
    """Return a dependency override that injects *fake_user* as the current user."""
    async def _override(request=None, authorization=None) -> Dict[str, Any]:  # type: ignore[override]
        return fake_user
    return _override


class TestB5CompanyIsolation(unittest.TestCase):
    """Verify that GET /api/hr/cases/{case_id} enforces company-scoped access."""

    def _client_for(self, fake_user: Dict[str, Any]) -> TestClient:
        app.dependency_overrides[get_current_user] = _make_dependency_override(fake_user)
        return TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Helpers – patch only the db methods actually called by get_case
    # ------------------------------------------------------------------
    def _patch_db(self, case: Optional[Dict[str, Any]]):
        """
        Patch the three db methods used by get_case + _get_hr_company_id:
          - get_case_by_id   → returns *case*
          - get_hr_company_id → returns company_id from _HR_COMPANY map
          - get_profile_record → returns profile so _get_hr_company_id fallback works
        """
        patches = [
            patch(
                "backend.main.db.get_case_by_id",
                side_effect=lambda cid: case if (case and cid == case["id"]) else None,
            ),
            patch(
                "backend.main.db.get_hr_company_id",
                side_effect=lambda uid: _HR_COMPANY.get(uid),
            ),
            patch(
                "backend.main.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ]
        return patches

    # ------------------------------------------------------------------
    # Scenario 1: own-company HR → 200
    # ------------------------------------------------------------------
    def test_own_company_hr_can_access_case(self) -> None:
        client = self._client_for(_HR_A)
        with (
            patch("backend.main.db.get_case_by_id", return_value=_CASE_A),
            patch("backend.main.db.get_hr_company_id", return_value="company-a"),
            patch("backend.main.db.get_profile_record", return_value={"id": "user-hr-a", "company_id": "company-a"}),
        ):
            response = client.get(
                "/api/hr/cases/case-a",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "case-a")
        self.assertEqual(data["company_id"], "company-a")

    # ------------------------------------------------------------------
    # Scenario 2: cross-company HR → 404 (must NOT leak case existence)
    # ------------------------------------------------------------------
    def test_cross_company_hr_gets_404(self) -> None:
        client = self._client_for(_HR_B)
        with (
            patch("backend.main.db.get_case_by_id", return_value=_CASE_A),
            patch("backend.main.db.get_hr_company_id", return_value="company-b"),
            patch("backend.main.db.get_profile_record", return_value={"id": "user-hr-b", "company_id": "company-b"}),
        ):
            response = client.get(
                "/api/hr/cases/case-a",
                headers={"Authorization": "Bearer hr-b-token"},
            )
        self.assertEqual(response.status_code, 404, "Cross-company case access must return 404")
        # Must not reveal the real company ID in the error body
        body_text = response.text
        self.assertNotIn("company-a", body_text)

    # ------------------------------------------------------------------
    # Scenario 3: admin → 200 regardless of company
    # ------------------------------------------------------------------
    def test_admin_can_access_any_case(self) -> None:
        client = self._client_for(_ADMIN)
        with (
            patch("backend.main.db.get_case_by_id", return_value=_CASE_A),
            # _get_hr_company_id will be called; admin lookup may return None
            patch("backend.main.db.get_hr_company_id", return_value=None),
            patch("backend.main.db.get_profile_record", return_value={"id": "user-admin", "company_id": None}),
        ):
            response = client.get(
                "/api/hr/cases/case-a",
                headers={"Authorization": "Bearer admin-token"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "case-a")

    # ------------------------------------------------------------------
    # Scenario 4: nonexistent case → 404 for own-company HR
    # ------------------------------------------------------------------
    def test_nonexistent_case_returns_404(self) -> None:
        client = self._client_for(_HR_A)
        with (
            patch("backend.main.db.get_case_by_id", return_value=None),
            patch("backend.main.db.get_hr_company_id", return_value="company-a"),
            patch("backend.main.db.get_profile_record", return_value={"id": "user-hr-a", "company_id": "company-a"}),
        ):
            response = client.get(
                "/api/hr/cases/nonexistent-case-id",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
