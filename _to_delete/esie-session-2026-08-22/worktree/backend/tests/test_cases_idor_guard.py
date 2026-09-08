"""AIQ-1535 — GET /api/cases/{id} cross-tenant IDOR regression.

The prod handler for GET /api/cases/{id} is ``backend.routes.compat.compat_get_case`` (it
shadows the safe ``cases_read.get_case`` via first-match registration). Its legacy-session
branch reads through the service-role ``db`` connection, which BYPASSES RLS — so it MUST call
the shared ``_assert_case_access`` guard before returning any case body, or it leaks any
company's case (name, nationality, passport, salary band) to any authenticated session.

These tests pin that contract:
  * a guard 403 (foreign tenant) propagates and no case body is built;
  * a guard 404 (unknown/malformed id) propagates;
  * an owned case still returns 200.

They fail if the ``_assert_case_access(user, case_id)`` call is removed from the session branch.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

# A non-JWT token (no dots) forces the legacy-session branch — the RLS-bypassing path.
_HEADERS = {"Authorization": "Bearer session-token-no-dots"}
_SESSION_USER = {"id": "user-hr-a", "role": "HR", "email": "hr-a@company-a.test"}


class TestCasesIdorGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_cross_tenant_read_is_denied(self) -> None:
        # A case owned by another tenant → the shared guard raises 403. compat must surface it
        # and must NOT build/return the case body.
        def _deny(user, case_id):
            raise HTTPException(status_code=403, detail="Not authorised for this case")

        with patch("backend.routes.compat._get_user_from_session_token", return_value=_SESSION_USER), \
                patch("backend.routes.compat._assert_case_access", side_effect=_deny) as guard, \
                patch("backend.routes.compat._get_wizard_case_dto") as wiz:
            resp = self.client.get("/api/cases/case-owned-by-company-b", headers=_HEADERS)

        self.assertEqual(resp.status_code, 403, resp.text)
        guard.assert_called_once()
        # The guard runs BEFORE any case body is resolved — nothing downstream fired.
        wiz.assert_not_called()
        self.assertNotIn("profile_json", resp.text)  # no case body leaked

    def test_unknown_or_malformed_id_is_404(self) -> None:
        def _missing(user, case_id):
            raise HTTPException(status_code=404, detail="Case not found")

        with patch("backend.routes.compat._get_user_from_session_token", return_value=_SESSION_USER), \
                patch("backend.routes.compat._assert_case_access", side_effect=_missing), \
                patch("backend.routes.compat._get_wizard_case_dto") as wiz:
            resp = self.client.get("/api/cases/not-a-real-id", headers=_HEADERS)

        self.assertEqual(resp.status_code, 404, resp.text)
        wiz.assert_not_called()

    def test_owned_case_still_returns_200(self) -> None:
        # Guard passes (caller owns the case) → compat proceeds and returns the DTO.
        with patch("backend.routes.compat._get_user_from_session_token", return_value=_SESSION_USER), \
                patch("backend.routes.compat._assert_case_access", return_value=None) as guard, \
                patch("backend.routes.compat.db.resolve_case_status", return_value="in_progress"), \
                patch("backend.routes.compat._get_wizard_case_dto",
                      return_value={"id": "case-a", "status": "in_progress"}):
            resp = self.client.get("/api/cases/case-a", headers=_HEADERS)

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["id"], "case-a")
        guard.assert_called_once()


if __name__ == "__main__":
    unittest.main()
