"""
H4 · API-level authorization tests for GET /api/policy/summary.

The campaign API runner has no Policy coverage; the existing test_policy_summary.py
is service-level (it never mounts the app). This module adds HTTP-level coverage of
the *authorization boundary* in policy_summary._resolve_company_id, which runs
before any DB access:

  - admin must pass ?company_id=…           → 400
  - HR cross-company query override denied   → 403  (tenant-isolation guard)
  - HR with no company_id on profile         → 403

All three short-circuit before db.engine is touched, so no DB/fixtures are needed.

App-mounted harness: override backend.app.auth_deps.get_current_user and disable
the per-request query counter + rate limits before importing backend.main.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import unittest
from typing import Any, Dict

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user


def _user(role: str, company_id=None) -> Dict[str, Any]:
    return {"id": f"user-{role}", "role": role, "company_id": company_id,
            "email": f"{role}@x.test"}


class PolicySummaryAuthzTest(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _client(self, user: Dict[str, Any]) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app, raise_server_exceptions=False)

    def test_admin_without_company_id_is_400(self) -> None:
        client = self._client(_user("admin"))
        resp = client.get("/api/policy/summary")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("company_id", resp.json()["detail"])

    def test_hr_cross_company_query_override_denied_403(self) -> None:
        client = self._client(_user("hr", company_id="company-a"))
        resp = client.get("/api/policy/summary", params={"company_id": "company-b"})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Cross-company", resp.json()["detail"])

    def test_hr_without_company_id_on_profile_403(self) -> None:
        client = self._client(_user("hr", company_id=None))
        resp = client.get("/api/policy/summary")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("company_id", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
