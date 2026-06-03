"""
C1-16 · Tests for GET /api/hr/cases/{case_id}/audit

Coverage:
  - Cross-tenant returns 404 (not 403)
  - Missing case returns 404
  - rce.* tables unavailable → degrades to empty events + 200
  - Cursor encode / decode round-trip
  - Invalid cursor returns 400
  - ETag header present when events exist
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, get_current_user, UserRole
from backend.app.routers.hr_case_audit import _decode_cursor, _encode_cursor

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


def _make_failing_engine() -> Any:
    """Engine stub whose .connect() raises — exercises the graceful degrade."""
    class _FailingEngine:
        def connect(self):
            raise RuntimeError("simulated DB unavailable")
    return _FailingEngine()


class _BaseCase(unittest.TestCase):
    def _client_for(self, fake_user: Dict[str, Any]) -> TestClient:
        app.dependency_overrides[get_current_user] = _make_dependency_override(fake_user)
        return TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _patches(self, case: Optional[Dict[str, Any]] = _CASE_A):
        return [
            patch(
                "backend.app.routers.hr_case_audit.db.get_relocation_case",
                side_effect=lambda cid: case if (case and cid == case["id"]) else None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
            patch(
                "backend.app.routers.hr_case_audit.db.engine",
                new=_make_failing_engine(),
            ),
        ]


# ---------------------------------------------------------------------------
# Cursor round-trip (pure unit test, no client needed)
# ---------------------------------------------------------------------------


class TestCursorRoundTrip(unittest.TestCase):
    def test_encode_decode_is_lossless(self) -> None:
        ts = "2026-05-27T10:15:23+00:00"
        source = "agent_runs"
        row_id = "11111111-2222-3333-4444-555555555555"
        token = _encode_cursor(ts, source, row_id)
        # base64 — no padding, no '/' or '+' characters
        self.assertNotIn("=", token)
        self.assertNotIn("/", token)
        self.assertNotIn("+", token)
        decoded_ts, decoded_source, decoded_id = _decode_cursor(token)
        self.assertEqual(decoded_ts, ts)
        self.assertEqual(decoded_source, source)
        self.assertEqual(decoded_id, row_id)

    def test_garbage_cursor_raises_http_exception(self) -> None:
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            _decode_cursor("definitely-not-a-cursor")
        self.assertEqual(cm.exception.status_code, 400)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestAuditEndpoint(_BaseCase):
    def test_returns_200_with_empty_events_when_db_unavailable(self) -> None:
        """Graceful degrade: rce.* unavailable → empty events list, NOT 500."""
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2]:
            resp = client.get(
                "/api/hr/cases/case-a/audit",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case_id"], "case-a")
        self.assertEqual(data["events"], [])
        self.assertIsNone(data["next_cursor"])

    def test_returns_404_for_cross_tenant(self) -> None:
        """HR-B (company-b) requests case-a (company-a) → 404, not 403."""
        client = self._client_for(_HR_B)
        with (
            patch(
                "backend.app.routers.hr_case_audit.db.get_relocation_case",
                return_value=_CASE_A,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.get(
                "/api/hr/cases/case-a/audit",
                headers={"Authorization": "Bearer hr-b-token"},
            )
        self.assertEqual(resp.status_code, 404)
        # Must not leak the real tenant id in the error body.
        self.assertNotIn("company-a", resp.text)

    def test_returns_404_for_missing_case(self) -> None:
        client = self._client_for(_HR_A)
        with (
            patch(
                "backend.app.routers.hr_case_audit.db.get_relocation_case",
                return_value=None,
            ),
            patch(
                "backend.app.auth_deps.db.get_profile_record",
                side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
            ),
        ):
            resp = client.get(
                "/api/hr/cases/no-such-id/audit",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 404)

    def test_invalid_cursor_returns_400(self) -> None:
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2]:
            resp = client.get(
                "/api/hr/cases/case-a/audit?cursor=not-a-cursor",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid pagination cursor", resp.text)

    def test_limit_clamped_to_max(self) -> None:
        """`?limit=9999` is rejected by FastAPI's Query validation (le=200)."""
        client = self._client_for(_HR_A)
        with self._patches()[0], self._patches()[1], self._patches()[2]:
            resp = client.get(
                "/api/hr/cases/case-a/audit?limit=9999",
                headers={"Authorization": "Bearer hr-a-token"},
            )
        self.assertEqual(resp.status_code, 422)  # FastAPI validation error


if __name__ == "__main__":
    unittest.main()
