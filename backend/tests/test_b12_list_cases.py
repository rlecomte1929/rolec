"""
B12 regression test — GET /api/hr/cases returns 200 (not 400/405).

Validates two scenarios:
  1. HR user with no company → 200 + {"cases": []}   (was: 400)
  2. HR user with a company → 200 + {"cases": [...]}  (normal path)

No live DB needed — db.list_relocation_cases is patched at the module level.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.main import app, get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _override(user_dict):
    """Return an async dependency override that yields user_dict."""
    async def _dep():
        return user_dict
    return _dep


HR_NO_COMPANY = {
    "id": "hr-no-company",
    "role": "HR",
    "is_admin": False,
    "company_id": None,
    "email": "hr@nowhere.test",
}

HR_WITH_COMPANY = {
    "id": "hr-with-company",
    "role": "HR",
    "is_admin": False,
    "company_id": "company-abc",
    "email": "hr@company.test",
}

FAKE_CASES = [
    {"id": "case-1", "company_id": "company-abc", "status": "created"},
]


class TestB12ListCases(unittest.TestCase):
    """B12: GET /api/hr/cases must not return 400 or 405."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()

    # ------------------------------------------------------------------
    # Scenario 1: HR with no company → 200 + empty list
    # ------------------------------------------------------------------
    def test_no_company_returns_200_empty(self):
        app.dependency_overrides[get_current_user] = _override(HR_NO_COMPANY)
        with patch("backend.main.db") as mock_db:
            mock_db.list_relocation_cases.return_value = []
            mock_db.get_profile_record.return_value = None
            resp = self.client.get("/api/hr/cases")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("cases", body)
        self.assertEqual(body["cases"], [])

    def test_no_company_does_not_return_400(self):
        app.dependency_overrides[get_current_user] = _override(HR_NO_COMPANY)
        with patch("backend.main.db") as mock_db:
            mock_db.list_relocation_cases.return_value = []
            mock_db.get_profile_record.return_value = None
            resp = self.client.get("/api/hr/cases")

        self.assertNotEqual(resp.status_code, 400)
        self.assertNotEqual(resp.status_code, 405)

    # ------------------------------------------------------------------
    # Scenario 2: HR with a company → 200 + case list
    # ------------------------------------------------------------------
    def test_with_company_returns_cases(self):
        app.dependency_overrides[get_current_user] = _override(HR_WITH_COMPANY)
        with patch("backend.main.db") as mock_db:
            mock_db.list_relocation_cases.return_value = FAKE_CASES
            mock_db.get_profile_record.return_value = None
            resp = self.client.get("/api/hr/cases")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("cases", body)
        self.assertEqual(len(body["cases"]), 1)
        self.assertEqual(body["cases"][0]["id"], "case-1")

    # ------------------------------------------------------------------
    # Scenario 3: endpoint is reachable (not 405 Method Not Allowed)
    # ------------------------------------------------------------------
    def test_endpoint_not_405(self):
        app.dependency_overrides[get_current_user] = _override(HR_WITH_COMPANY)
        with patch("backend.main.db") as mock_db:
            mock_db.list_relocation_cases.return_value = []
            mock_db.get_profile_record.return_value = None
            resp = self.client.get("/api/hr/cases")

        self.assertNotEqual(resp.status_code, 405)


if __name__ == "__main__":
    unittest.main()
