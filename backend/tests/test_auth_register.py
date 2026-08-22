"""
AIQ-542 (B18b) regression tests — register must create-or-link a company.

Before this fix a self-serve HR signup that supplied ``company_name`` received a
token but no company link, so every subsequent HR API call failed with
"No company linked to your profile". These tests pin the create-or-link contract:

  1. New company_name        → company created, profile linked, id echoed back
  2. Existing company_name   → links to the existing id (case-insensitive), no dup
  3. No company_name         → no company link attempted (legacy behaviour)

The db layer is patched at the router module level (no live DB), mirroring
test_employee_messages.py.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
# Mirror test_employee_messages.py: backend.database is a MagicMock under the root
# conftest, so install_query_counter()'s event listener raises unless disabled.
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


def _base_db_mock() -> MagicMock:
    """A db mock whose register-path lookups all return 'not taken / created'."""
    db = MagicMock()
    db.get_user_by_username.return_value = None
    db.get_user_by_email.return_value = None
    db.create_user.return_value = True
    db.is_admin_allowlisted.return_value = False
    return db


def _register_body(**overrides):
    body = {
        "email": "newhr@example.test",
        "password": "Passw0rd!",
        "name": "New HR",
        "role": "HR",
    }
    body.update(overrides)
    return body


class TestRegisterCompanyLink(unittest.TestCase):
    """AIQ-542: register with company_name must never leave a token without a company."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    # ------------------------------------------------------------------
    # Scenario 1: brand-new company_name → created + linked + echoed back
    # ------------------------------------------------------------------
    def test_register_new_company_creates_link(self):
        db = _base_db_mock()
        db.create_company_for_self_serve_signup.return_value = "company-new-1"
        with patch("backend.app.routers.auth.db", db):
            resp = self.client.post("/api/auth/register",
                                    json=_register_body(company_name="Brand New Co"))

        self.assertEqual(resp.status_code, 200, resp.text)
        db.create_company_for_self_serve_signup.assert_called_once_with("Brand New Co", company_size=None)
        # profile linked to the resolved company id
        args, kwargs = db.set_profile_company.call_args
        self.assertEqual(args[1] if len(args) > 1 else kwargs["company_id"], "company-new-1")
        # company id surfaced in the response so the post-register state is never
        # "has token, has no company"
        self.assertEqual(resp.json()["user"]["company"], "company-new-1")

    # ------------------------------------------------------------------
    # [AIQ-2090] Scenario 2 INVERTED: a name that matches an existing company must
    # NOT join it. This used to call find_or_create_company_by_name, a
    # LOWER(TRIM(name)) match, so typing a customer's company name on this PUBLIC
    # form linked the new account into their workspace — their cases, their
    # employees, their policies. A typed string is not an authorisation check.
    # ------------------------------------------------------------------
    def test_register_with_an_existing_company_name_does_not_join_it(self):
        db = _base_db_mock()
        db.create_company_for_self_serve_signup.return_value = "brand-new-id"
        with patch("backend.app.routers.auth.db", db):
            resp = self.client.post("/api/auth/register",
                                    json=_register_body(company_name="Test company"))

        self.assertEqual(resp.status_code, 200, resp.text)
        # The name-matching helper must not be reachable from signup at all.
        self.assertFalse(
            hasattr(db.find_or_create_company_by_name, "assert_not_called")
            and db.find_or_create_company_by_name.called,
            "signup must never call the name-matching join",
        )
        db.create_company_for_self_serve_signup.assert_called_once_with(
            "Test company", company_size=None
        )
        self.assertEqual(resp.json()["user"]["company"], "brand-new-id")

    # ------------------------------------------------------------------
    # AIQ-829: HR signup forwards company_size → company create-or-link path
    # ------------------------------------------------------------------
    def test_register_hr_forwards_company_size(self):
        db = _base_db_mock()
        db.create_company_for_self_serve_signup.return_value = "company-sized-1"
        with patch("backend.app.routers.auth.db", db):
            resp = self.client.post(
                "/api/auth/register",
                json=_register_body(company_name="Sized Co", company_size="51-500"),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        db.create_company_for_self_serve_signup.assert_called_once_with("Sized Co", company_size="51-500")

    # ------------------------------------------------------------------
    # Scenario 3: no company_name → no link attempt (unchanged legacy path)
    # ------------------------------------------------------------------
    def test_register_no_company_name_returns_pending_state(self):
        db = _base_db_mock()
        with patch("backend.app.routers.auth.db", db):
            resp = self.client.post("/api/auth/register", json=_register_body())

        self.assertEqual(resp.status_code, 200, resp.text)
        db.create_company_for_self_serve_signup.assert_not_called()
        db.set_profile_company.assert_not_called()
        self.assertIsNone(resp.json()["user"]["company"])


if __name__ == "__main__":
    unittest.main()
