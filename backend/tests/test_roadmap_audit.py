"""
P1-08 · Tests for the roadmap audit-trail layer.

Covers the parts that do not need a live PostgreSQL/rce.* schema:
  - append_roadmap_audit validates generated_by (P1-08b)
  - GET /api/cases/{id}/audit (P1-08c): cross-tenant 404, missing 404,
    graceful degrade to empty steps, as_of passthrough
  - GET /api/admin/cases/{id}/audit-export.json (P1-08e): 403 for non-admin,
    schema-versioned shape on degrade
  - POST /api/admin/rule-change-notifications/run (P1-08d): 403 for non-admin,
    counts shape

Live-DB behaviour (reconstruction returns old vs new rule text either side of a
change; notification fires for affected cases) is verified by the reviewer
against a fixture DB — see Execution Notes.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app, UserRole

# IMPORTANT (CLAUDE.md): the app routers depend on backend.app.auth_deps.get_current_user,
# NOT backend.main.get_current_user. Overriding the wrong reference silently never fires.
from backend.app.auth_deps import get_current_user

# ---------------------------------------------------------------------------
# Fake users + cases (mirrors test_hr_case_audit.py)
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
    "email": "admin@relopass.test",
    "is_admin": True,
}

_CASE_A: Dict[str, Any] = {
    "id": "case-a",
    "company_id": "company-a",
    "hr_user_id": "user-hr-a",
    "employee_id": "emp-a",
    "status": "in_progress",
}

_HR_COMPANY = {"user-hr-a": "company-a", "user-hr-b": "company-b", "user-admin": "company-a"}


def _override(fake_user: Dict[str, Any]):
    async def _f(request=None, authorization=None):  # type: ignore[override]
        return fake_user
    return _f


def _profile_patch():
    return patch(
        "backend.app.auth_deps.db.get_profile_record",
        side_effect=lambda uid: {"id": uid, "company_id": _HR_COMPANY.get(uid)},
    )


class _Base(unittest.TestCase):
    def _client(self, user: Dict[str, Any]) -> TestClient:
        app.dependency_overrides[get_current_user] = _override(user)
        return TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# P1-08b — writer validation (pure, no DB)
# ---------------------------------------------------------------------------


class TestAppendValidation(unittest.TestCase):
    def test_rejects_bad_generated_by(self) -> None:
        from backend.app.services.roadmap_audit_service import append_roadmap_audit

        with self.assertRaises(ValueError):
            append_roadmap_audit(
                case_id="c", rule_version_id="rv", generated_by="ROBOT"
            )


# ---------------------------------------------------------------------------
# P1-08c — as_of reconstruction endpoint
# ---------------------------------------------------------------------------


class TestReconstruct(_Base):
    def test_cross_tenant_returns_404(self) -> None:
        client = self._client(_HR_B)
        with patch(
            "backend.app.routers.roadmap_audit.db.get_relocation_case",
            return_value=_CASE_A,
        ), _profile_patch():
            resp = client.get(
                "/api/cases/case-a/audit", headers={"Authorization": "Bearer t"}
            )
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("company-a", resp.text)

    def test_missing_case_returns_404(self) -> None:
        client = self._client(_HR_A)
        with patch(
            "backend.app.routers.roadmap_audit.db.get_relocation_case",
            return_value=None,
        ), _profile_patch():
            resp = client.get(
                "/api/cases/nope/audit", headers={"Authorization": "Bearer t"}
            )
        self.assertEqual(resp.status_code, 404)

    def test_degrades_to_empty_steps(self) -> None:
        client = self._client(_HR_A)
        with patch(
            "backend.app.routers.roadmap_audit.db.get_relocation_case",
            return_value=_CASE_A,
        ), _profile_patch(), patch(
            "backend.app.routers.roadmap_audit.reconstruct_roadmap_as_of",
            side_effect=RuntimeError("no rce schema"),
        ):
            resp = client.get(
                "/api/cases/case-a/audit", headers={"Authorization": "Bearer t"}
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["case_id"], "case-a")
        self.assertEqual(body["steps"], [])
        self.assertIsNone(body["as_of"])

    def test_as_of_passthrough(self) -> None:
        client = self._client(_HR_A)
        captured: Dict[str, Any] = {}

        def _fake(case_id, as_of):
            captured["as_of"] = as_of
            return [{"step_id": "s1"}]

        with patch(
            "backend.app.routers.roadmap_audit.db.get_relocation_case",
            return_value=_CASE_A,
        ), _profile_patch(), patch(
            "backend.app.routers.roadmap_audit.reconstruct_roadmap_as_of",
            side_effect=_fake,
        ):
            resp = client.get(
                "/api/cases/case-a/audit?as_of=2026-01-15",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["as_of"], "2026-01-15")
        self.assertEqual(captured["as_of"].isoformat(), "2026-01-15")

    def test_invalid_as_of_returns_422(self) -> None:
        client = self._client(_HR_A)
        with patch(
            "backend.app.routers.roadmap_audit.db.get_relocation_case",
            return_value=_CASE_A,
        ), _profile_patch():
            resp = client.get(
                "/api/cases/case-a/audit?as_of=not-a-date",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 422)


# ---------------------------------------------------------------------------
# P1-08e — legal export endpoint (admin only)
# ---------------------------------------------------------------------------


class TestExport(_Base):
    def test_non_admin_forbidden(self) -> None:
        client = self._client(_HR_A)
        with _profile_patch():
            resp = client.get(
                "/api/admin/cases/case-a/audit-export.json",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 403)

    def test_admin_gets_schema_versioned_export(self) -> None:
        client = self._client(_ADMIN)
        with patch(
            "backend.app.routers.roadmap_audit.export_case_audit",
            return_value={
                "schema_version": "1.0",
                "case_id": "case-a",
                "exported_at": "2026-06-04T00:00:00Z",
                "entry_count": 0,
                "audit_log": [],
            },
        ):
            resp = client.get(
                "/api/admin/cases/case-a/audit-export.json",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["schema_version"], "1.0")
        self.assertEqual(body["case_id"], "case-a")
        self.assertIn("audit_log", body)

    def test_degrade_returns_empty_export(self) -> None:
        client = self._client(_ADMIN)
        with patch(
            "backend.app.routers.roadmap_audit.export_case_audit",
            side_effect=RuntimeError("no rce schema"),
        ):
            resp = client.get(
                "/api/admin/cases/case-a/audit-export.json",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["entry_count"], 0)
        self.assertEqual(body["audit_log"], [])


# ---------------------------------------------------------------------------
# P1-08d — rule-change notifier trigger (admin only)
# ---------------------------------------------------------------------------


class TestNotifierTrigger(_Base):
    def test_non_admin_forbidden(self) -> None:
        client = self._client(_HR_A)
        with _profile_patch():
            resp = client.post(
                "/api/admin/rule-change-notifications/run",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 403)

    def test_admin_gets_counts(self) -> None:
        client = self._client(_ADMIN)
        with patch(
            "backend.app.routers.roadmap_audit.notify_superseded_rules",
            return_value={
                "affected_pairs": 2,
                "notifications_created": 3,
                "skipped_idempotent": 1,
                "skipped_no_recipient": 0,
            },
        ):
            resp = client.post(
                "/api/admin/rule-change-notifications/run",
                headers={"Authorization": "Bearer t"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["notifications_created"], 3)
        self.assertEqual(body["affected_pairs"], 2)


if __name__ == "__main__":
    unittest.main()
