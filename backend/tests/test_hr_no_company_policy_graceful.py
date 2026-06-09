"""Regression: an HR not yet linked to a company gets graceful empty/onboarding
policy reads (HTTP 200), not 400 "User missing company association".

Implements the negative case from SKILL.md (relopass-e2e-test) Phase 0.5: a
missing precondition must degrade gracefully, never hard-fail. The class of bug
this guards: the HR policy surface 400'd on every read when an HR had no company
link, while the automated runner — which mints company-linked HR accounts —
stayed green. Found via the live persona sweep, 2026-06-05.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# CLAUDE.md: the app-layer routers (policy_config) depend on
# backend.app.auth_deps.get_current_user, while the main.py endpoints
# (list_policy_documents / list_company_policies) depend on main.py's OWN
# get_current_user — a different function. Override BOTH or half the routes 401.
from backend.main import app, UserRole, get_current_user as main_get_current_user
from backend.app.auth_deps import get_current_user
from backend.app.services.policy_config_matrix_service import PolicyConfigMatrixService


_HR_NO_COMPANY: Dict[str, Any] = {
    "id": "hr-not-onboarded",
    "role": UserRole.HR.value,
    "email": "new-hr@example.test",
    "is_admin": False,
}


def _override(user: Dict[str, Any]):
    async def _f(request=None, authorization=None):  # type: ignore[override]
        return user
    return _f


class HrNoCompanyPolicyGracefulTests(unittest.TestCase):
    """The 4 HR policy reads that load on the policy page must return a graceful
    onboarding state (200), not 400, when the HR has no company yet."""

    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = _override(_HR_NO_COMPANY)
        app.dependency_overrides[main_get_current_user] = _override(_HR_NO_COMPANY)
        # No company link for this HR, in either router's resolver.
        self._patches = [
            patch("backend.app.routers.policy_config._get_hr_company_id", lambda u: None),
            patch("backend.main._get_hr_company_id", lambda u: None),
        ]
        for p in self._patches:
            p.start()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()
        app.dependency_overrides.clear()

    def test_policy_config_returns_empty_scaffold_not_400(self) -> None:
        r = self.client.get("/api/hr/policy-config")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json().get("company_setup_required"))

    def test_policy_config_published_returns_empty_scaffold_not_400(self) -> None:
        # Found via the live policy-flow E2E sweep, 2026-06-09: /published was the
        # lone HR policy read still 400ing for a no-company HR while its three
        # siblings degraded gracefully.
        r = self.client.get("/api/hr/policy-config/published")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json().get("company_setup_required"))

    def test_policy_config_diff_returns_empty_not_400(self) -> None:
        r = self.client.get("/api/hr/policy-config/diff")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body.get("company_setup_required"))
        self.assertEqual(
            body["diff"]["summary"],
            {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
        )

    def test_policy_documents_returns_empty_list_not_400(self) -> None:
        r = self.client.get("/api/hr/policy-documents")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body.get("documents"), [])
        self.assertTrue(body.get("company_setup_required"))

    def test_company_policies_returns_empty_list_not_400(self) -> None:
        r = self.client.get("/api/company-policies")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body.get("policies"), [])
        self.assertTrue(body.get("company_setup_required"))


class EmptyPayloadServiceTests(unittest.TestCase):
    """The two new company-independent builders behind the graceful reads."""

    def setUp(self) -> None:
        # _db is unused by both methods (virtual scaffold rows have no ids -> no
        # override lookup; empty_diff is pure), so a MagicMock is sufficient.
        self.svc = PolicyConfigMatrixService(MagicMock())

    def test_empty_onboarding_payload_shape(self) -> None:
        p = self.svc.empty_onboarding_payload()
        self.assertTrue(p.get("company_setup_required"))
        self.assertIn("categories", p)  # mirrors the empty_scaffold read state

    def test_empty_diff_shape(self) -> None:
        d = self.svc.empty_diff()
        self.assertTrue(d.get("company_setup_required"))
        self.assertEqual(d["live"]["rows"], [])
        self.assertEqual(d["draft"]["rows"], [])
        self.assertEqual(
            d["diff"]["summary"],
            {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
        )


class EmployeeCompanyResolutionTests(unittest.TestCase):
    """_resolve_employee_company_id falls back to the case assignment when the
    profile isn't resolvable — a legacy/seed employee's non-UUID id can't look up
    the uuid-keyed profiles row, so the company came back empty (400 'Employee
    missing company' on the benefits/policy view)."""

    def setUp(self) -> None:
        from backend.app.routers import policy_config
        self.mod = policy_config

    def test_resolves_via_profile_when_present(self) -> None:
        with patch.object(self.mod.db, "get_profile_record", return_value={"company_id": "co-x"}):
            self.assertEqual(self.mod._resolve_employee_company_id({"id": "uuid-emp"}), "co-x")

    def test_falls_back_to_assignment_for_legacy_id(self) -> None:
        with patch.object(self.mod.db, "get_profile_record", return_value=None), \
             patch.object(self.mod.db, "get_assignment_for_employee", return_value={"id": "asgn-1"}), \
             patch.object(self.mod.db, "get_company_id_for_assignment_id", return_value="co-1"):
            self.assertEqual(self.mod._resolve_employee_company_id({"id": "seed-emp-testingapril"}), "co-1")

    def test_none_when_no_profile_and_no_assignment(self) -> None:
        with patch.object(self.mod.db, "get_profile_record", return_value=None), \
             patch.object(self.mod.db, "get_assignment_for_employee", return_value=None):
            self.assertIsNone(self.mod._resolve_employee_company_id({"id": "ghost"}))


if __name__ == "__main__":
    unittest.main()
