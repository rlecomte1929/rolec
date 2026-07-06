"""AIQ-1420 (TD-2) + AIQ-1441 (TD-13) — test-drive provisioning endpoint tests.

Pins the contract of POST /api/test-drive/provision:
  1. Campaign flag off                → 404 (dark by default)
  2. Flag on, missing/wrong token     → 403
  3. Flag on + valid token + input    → 200, two credential sets, both accounts
     created (HR then EMPLOYEE), company seeded + linked, test_sessions written
  4. Bad tester_segment               → 422 (Pydantic)
  5. Route is registered in BOTH app instances (dual-layer per CLAUDE.md)
  6. No corridor_id → auto-assigned from locked set (TD-13)
  7. Explicit corridor_id → honoured verbatim (TD-13)

The db layer is patched at the router module level (no live DB), mirroring
test_auth_register.py. Supabase sync is patched out so nothing touches the network.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
# backend.database is a MagicMock under the root conftest, so install_query_counter()'s
# event listener raises unless disabled (see test_auth_register.py).
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

_ENABLED_ENV = {
    "RELOPASS_TEST_DRIVE_ENABLED": "1",
    "RELOPASS_TEST_DRIVE_INVITE_TOKEN": "secret-token",
}


def _db_mock() -> MagicMock:
    db = MagicMock()
    db.create_user.return_value = True
    db.find_or_create_company_by_name.return_value = "company-1"
    return db


def _body(**overrides):
    body = {
        "first_name": "Alice",
        "invite_token": "secret-token",
        "tester_segment": "prospect",
    }
    body.update(overrides)
    return body


class TestTestDriveProvision(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_flag_off_returns_404(self):
        with patch.dict(os.environ, {"RELOPASS_TEST_DRIVE_ENABLED": "false"}, clear=False):
            resp = self.client.post("/api/test-drive/provision", json=_body())
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_bad_token_returns_403(self):
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision", json=_body(invite_token="wrong"))
        self.assertEqual(resp.status_code, 403, resp.text)
        db.create_user.assert_not_called()

    def test_missing_token_secret_returns_403(self):
        """If the server has no campaign secret configured, always 403 (never open)."""
        db = _db_mock()
        env = {"RELOPASS_TEST_DRIVE_ENABLED": "1", "RELOPASS_TEST_DRIVE_INVITE_TOKEN": ""}
        with patch.dict(os.environ, env, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision", json=_body())
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_happy_path_provisions_pair(self):
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync") as sync:
            resp = self.client.post("/api/test-drive/provision", json=_body())

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        # Two distinct credential sets with the expected role prefixes.
        self.assertTrue(data["hr"]["username"].startswith("HR-"))
        self.assertTrue(data["employee"]["username"].startswith("EMP-"))
        self.assertEqual(data["hr"]["role"], "HR")
        self.assertEqual(data["employee"]["role"], "EMPLOYEE")
        self.assertNotEqual(data["hr"]["password"], data["employee"]["password"])
        self.assertTrue(data["hr"]["email"].endswith("@probe.test"))
        self.assertTrue(data["corridor_id"], "corridor_id must be non-empty")
        self.assertTrue(data["session_id"])
        self.assertTrue(data["campaign"])

        # Two accounts created, HR then EMPLOYEE.
        self.assertEqual(db.create_user.call_count, 2)
        roles = [c.kwargs["role"] for c in db.create_user.call_args_list]
        self.assertEqual(roles, ["HR", "EMPLOYEE"])

        # Company seeded + both identities linked.
        db.find_or_create_company_by_name.assert_called_once()
        db.ensure_hr_user_for_profile.assert_called_once()
        db.ensure_employee_for_profile.assert_called_once()

        # Funnel row written + Supabase mirrored for both accounts.
        db.engine.begin.assert_called()
        self.assertEqual(sync.call_count, 2)

    def test_bad_segment_returns_422(self):
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision", json=_body(tester_segment="bogus"))
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_no_corridor_auto_assigns(self):
        """No corridor_id in body → server picks one of the 5 locked corridors."""
        from backend.app.routers.test_drive import _LOCKED_CORRIDORS
        db_mock = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db_mock), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn(resp.json()["corridor_id"], _LOCKED_CORRIDORS)

    def test_explicit_corridor_honoured(self):
        """Explicit corridor_id is passed through unchanged."""
        db_mock = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db_mock), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(corridor_id="IN_DE"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["corridor_id"], "IN_DE")

    def test_route_registered_in_both_apps(self):
        from backend.main import app as prod_app
        from backend.app.main import app as modular_app
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            paths = [r.path for r in a.routes if "test-drive" in getattr(r, "path", "")]
            self.assertIn("/api/test-drive/provision", paths, f"route missing in {label}")


if __name__ == "__main__":
    unittest.main()
