"""
C1-11c-be · Tests for the 6 HR case detail endpoints.

Coverage:
  - Happy path for each of the 6 routes returns the expected shape
  - Cross-tenant access returns 404 (NOT 403) for at least one route
  - Missing case returns 404
  - rce.* table missing / empty does not 500 the response (graceful
    degrade — endpoints return empty arrays / zero counts)
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, get_current_user, UserRole

# ---------------------------------------------------------------------------
# Fake users + cases
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

_CASE_A: Dict[str, Any] = {
    "id": "case-a",
    "company_id": "company-a",
    "hr_user_id": "user-hr-a",
    "employee_id": "emp-a",
    "origin_country_code": "IN",
    "dest_country_code": "DE",
    "corridor": "IN_DE",
    "status": "in_progress",
    "stage": "documents",
    "target_start_date": None,
    "actual_start_date": None,
    "target_close_date": None,
    "nationality": None,
}

_EMP_USER: Dict[str, Any] = {
    "id": "emp-a",
    "name": "Priya Sharma",
    "email": "priya@example.test",
}

_HR_COMPANY: Dict[str, str] = {
    "user-hr-a": "company-a",
    "user-hr-b": "company-b",
}


def _make_dependency_override(fake_user: Dict[str, Any]):
    async def _override(request=None, authorization=None) -> Dict[str, Any]:  # type: ignore[override]
        return fake_user
    return _override


class _BaseCase(unittest.TestCase):
    def _client_for(self, fake_user: Dict[str, Any]) -> TestClient:
        app.dependency_overrides[get_current_user] = _make_dependency_override(fake_user)
        return TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _patches(self, case: Optional[Dict[str, Any]] = _CASE_A, hr_user_id: str = "user-hr-a"):
        company_id = _HR_COMPANY.get(hr_user_id)
        return [
            patch(
                "backend.app.routers.hr_case_detail.db.get_relocation_case",
                side_effect=lambda cid: case if (case and cid == case["id"]) else None,
            ),
            patch(
                "backend.app.routers.hr_case_detail.db.get_user_by_id",
                side_effect=lambda uid: _EMP_USER if uid == _EMP_USER["id"] else None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
            # Force the rce.* queries to raise — the router's try/except
            # then catches and returns empty arrays / zeroes. This isolates
            # the route + auth + DTO behaviour from a live database while
            # still proving the graceful-degrade contract.
            patch(
                "backend.app.routers.hr_case_detail.db.engine",
                new=_make_failing_engine(),
            ),
        ]


def _make_failing_engine() -> Any:
    """Return an object whose `.connect()` raises — used to force the
    router's except-Exception → empty-list fallback path."""
    class _FailingEngine:
        def connect(self):
            raise RuntimeError("simulated DB unavailable")

    return _FailingEngine()


# ---------------------------------------------------------------------------
# Per-endpoint happy-path tests (no rce.* data — verifies graceful degrade)
# ---------------------------------------------------------------------------


class TestOverviewEndpoint(_BaseCase):
    def test_overview_returns_case_meta_for_own_company(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2], self._patches()[3]:
            resp = client.get(
                "/api/hr/cases/case-a/overview",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["overview"]
        self.assertEqual(data["case_id"], "case-a")
        self.assertEqual(data["employee"]["display_name"], "Priya Sharma")
        self.assertEqual(data["corridor"], "IN_DE")
        self.assertEqual(data["status"], "in_progress")
        # rce.family_members raises → degrade to empty list (no 500)
        self.assertEqual(data["family_members"], [])

    def test_overview_returns_404_for_cross_tenant(self) -> None:
        # HR-B requests case-a, which belongs to company-a → must be 404
        client = self._client_for(_HR_B)
        with (
            patch(
                "backend.app.routers.hr_case_detail.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.get(
                "/api/hr/cases/case-a/overview",
                headers={"Authorization": "Bearer hr-b-token"},
            )
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("company-a", resp.text)

    def test_overview_returns_404_for_missing_case(self) -> None:
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_detail.db.get_relocation_case",
                return_value=None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.get(
                "/api/hr/cases/missing-id/overview",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 404)


class TestDocumentsEndpoint(_BaseCase):
    def test_documents_degrades_to_empty_list(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2], self._patches()[3]:
            resp = client.get(
                "/api/hr/cases/case-a/documents",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"documents": []})


class TestStepsEndpoint(_BaseCase):
    def test_steps_degrades_to_empty_list(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2], self._patches()[3]:
            resp = client.get(
                "/api/hr/cases/case-a/steps",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"steps": []})


class TestContradictionsSummaryEndpoint(_BaseCase):
    def test_summary_degrades_to_zero_counts(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2], self._patches()[3]:
            resp = client.get(
                "/api/hr/cases/case-a/contradictions/summary",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        summary = resp.json()["summary"]
        self.assertEqual(summary["case_id"], "case-a")
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(summary["resolved"], 0)


class TestContradictionsListEndpoint(_BaseCase):
    def test_contradictions_list_degrades_to_empty(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2], self._patches()[3]:
            resp = client.get(
                "/api/hr/cases/case-a/contradictions",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"contradictions": []})


class TestContradictionHistoryEndpoint(_BaseCase):
    def test_history_degrades_to_empty(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2], self._patches()[3]:
            resp = client.get(
                "/api/hr/cases/case-a/contradictions/cid-x/history",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"corrections": []})


if __name__ == "__main__":
    unittest.main()
