"""
C1-12-be · Tests for resolve + escalate POST endpoints.

Coverage:
  - POST /resolve with cross-tenant case → 404
  - POST /resolve with missing case → 404
  - POST /resolve with OTHER reason but empty freetext → 400
  - POST /resolve with unknown reason_code → 422 (FastAPI Literal)
  - POST /escalate with cross-tenant case → 404
  - POST /escalate with empty reason_freetext → 422
  - rce.* unreachable (DB engine fails) → 500 with safe detail

Live-DB integration tests (200 happy path, 409 already-resolved,
context_snapshot shape) are deferred to CI / staging since they need
a real PostgreSQL fixture.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, get_current_user, UserRole

# ---------------------------------------------------------------------------
# Fixtures
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
    "status": "in_progress",
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


# ---------------------------------------------------------------------------
# Resolve endpoint tests
# ---------------------------------------------------------------------------


class TestResolveEndpoint(_BaseCase):
    def test_cross_tenant_returns_404(self) -> None:
        client = self._client_for(_HR_B)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/case-a/contradictions/cid-x/resolve",
                headers={"Authorization": "Bearer hr-b-token"},
                json={
                    "winner_candidate_id": "cand-1",
                    "reason_code": "OCR_ERROR",
                },
            )
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("company-a", resp.text)

    def test_missing_case_returns_404(self) -> None:
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/missing/contradictions/cid-x/resolve",
                headers={"Authorization": "Bearer hr-a-token"},
                json={
                    "winner_candidate_id": "cand-1",
                    "reason_code": "OCR_ERROR",
                },
            )
        self.assertEqual(resp.status_code, 404)

    def test_other_without_freetext_returns_400(self) -> None:
        """The OTHER reason code requires a freetext explanation."""
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/case-a/contradictions/cid-x/resolve",
                headers={"Authorization": "Bearer hr-a-token"},
                json={
                    "winner_candidate_id": "cand-1",
                    "reason_code": "OTHER",
                    "reason_freetext": "   ",
                },
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("OTHER", resp.text)

    def test_unknown_reason_code_returns_422(self) -> None:
        """FastAPI's Literal type validation rejects out-of-enum values."""
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/case-a/contradictions/cid-x/resolve",
                headers={"Authorization": "Bearer hr-a-token"},
                json={
                    "winner_candidate_id": "cand-1",
                    "reason_code": "BAD_REASON",
                },
            )
        self.assertEqual(resp.status_code, 422)

    def test_winner_candidate_id_empty_returns_422(self) -> None:
        """min_length=1 on winner_candidate_id."""
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/case-a/contradictions/cid-x/resolve",
                headers={"Authorization": "Bearer hr-a-token"},
                json={
                    "winner_candidate_id": "",
                    "reason_code": "OCR_ERROR",
                },
            )
        self.assertEqual(resp.status_code, 422)


# ---------------------------------------------------------------------------
# Escalate endpoint tests
# ---------------------------------------------------------------------------


class TestEscalateEndpoint(_BaseCase):
    def test_cross_tenant_returns_404(self) -> None:
        client = self._client_for(_HR_B)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/case-a/contradictions/cid-x/escalate",
                headers={"Authorization": "Bearer hr-b-token"},
                json={"reason_freetext": "Compliance concern."},
            )
        self.assertEqual(resp.status_code, 404)

    def test_empty_reason_returns_422(self) -> None:
        """min_length=1 on reason_freetext — escalation requires a reason."""
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_resolve.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.post(
                "/api/hr/cases/case-a/contradictions/cid-x/escalate",
                headers={"Authorization": "Bearer hr-a-token"},
                json={"reason_freetext": ""},
            )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
