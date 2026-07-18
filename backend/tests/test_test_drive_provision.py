"""AIQ-1420 (TD-2) + AIQ-1441 (TD-13) — test-drive provisioning endpoint tests.

Pins the contract of POST /api/test-drive/provision:
  1. Campaign flag off                → 404 (dark by default)
  2. Flag on + wrong token supplied   → 403 (token validated only when supplied)
  2b. Flag on + no token supplied     → 200 (public self-serve; token is optional)
  3. Flag on + valid token + input    → 200, two credential sets, both accounts
     created (HR then EMPLOYEE), company seeded + linked, test_sessions written
  4. Bad tester_segment               → 422 (Pydantic)
  5. Route is registered in BOTH app instances (dual-layer per CLAUDE.md)
  6. No corridor_id → auto-assigned from locked set (TD-13)
  7. Explicit corridor_id → honoured verbatim (TD-13)
  8. Unknown corridor_id → coerced to auto-assign (whitelist against locked set)

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
        "tester_email": "alice@example.com",
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

    def test_no_token_supplied_is_open(self):
        """Token is optional: omitting it provisions even when a secret is configured."""
        from backend.app.routers.test_drive import _LOCKED_CORRIDORS
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(invite_token=None))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn(resp.json()["corridor_id"], _LOCKED_CORRIDORS)

    def test_no_token_and_no_secret_is_open(self):
        """No configured secret + no supplied token → still open (public self-serve)."""
        db = _db_mock()
        env = {"RELOPASS_TEST_DRIVE_ENABLED": "1", "RELOPASS_TEST_DRIVE_INVITE_TOKEN": ""}
        with patch.dict(os.environ, env, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(invite_token=None))
        self.assertEqual(resp.status_code, 200, resp.text)

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

    def test_provision_seeds_published_policy(self):
        # [AIQ-1621] Provisioning a test-drive pair seeds a PUBLISHED default policy for the
        # new company, so the employee benefit flow is active without the tester building one.
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"), \
                patch("backend.app.routers.test_drive._seed_default_published_policy") as seed:
            resp = self.client.post("/api/test-drive/provision", json=_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        seed.assert_called_once()
        self.assertEqual(seed.call_args.args[0], "company-1")  # company_id

    def test_seed_helper_publishes_the_canonical_default(self):
        # [AIQ-1621] The seed helper ensures a draft (auto-seeds the canonical default matrix)
        # then publishes it — so GET /api/hr/policy-config/published returns a live policy.
        from backend.app.routers import test_drive as td
        with patch.object(td, "db", MagicMock()), \
                patch(
                    "backend.app.services.policy_config_matrix_service.PolicyConfigMatrixService"
                ) as Svc:
            td._seed_default_published_policy("company-1", "hr-1")
        svc = Svc.return_value
        svc.ensure_draft.assert_called_once_with("company-1", created_by="hr-1")
        svc.publish_draft.assert_called_once_with(
            "company-1", policy_version_id=None, created_by="hr-1"
        )

    def test_seed_helper_never_raises_on_failure(self):
        # Best-effort: a seed failure must never break provisioning.
        from backend.app.routers import test_drive as td
        with patch.object(td, "db", MagicMock()), \
                patch(
                    "backend.app.services.policy_config_matrix_service.PolicyConfigMatrixService",
                    side_effect=RuntimeError("boom"),
                ):
            td._seed_default_published_policy("company-1", "hr-1")  # must not raise

    def test_no_segment_defaults_null_not_prospect(self):
        """TD-FIX-2 (AIQ-1503): single-link provision with no segment writes NULL to
        test_sessions, not a silent 'prospect'."""
        db = _db_mock()
        body = _body()
        body.pop("tester_segment", None)
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=body)
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        sess_inserts = [
            c for c in conn.execute.call_args_list if "INSERT INTO test_sessions" in str(c.args[0])
        ]
        self.assertEqual(len(sess_inserts), 1)
        self.assertIsNone(sess_inserts[0].args[1]["tester_segment"])

    def test_bad_segment_returns_422(self):
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision", json=_body(tester_segment="bogus"))
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_persists_tester_contact(self):
        """TD-M0 (AIQ-1556): provision stores the tester's real name + email on the session row."""
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post(
                "/api/test-drive/provision",
                json=_body(first_name="Alice", tester_email="alice@example.com"),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        sess_inserts = [
            c for c in conn.execute.call_args_list if "INSERT INTO test_sessions" in str(c.args[0])
        ]
        self.assertEqual(len(sess_inserts), 1)
        params = sess_inserts[0].args[1]
        self.assertEqual(params["tester_name"], "Alice")
        self.assertEqual(params["tester_email"], "alice@example.com")

    def test_missing_email_is_allowed_and_stored_as_null(self):
        """AIQ-1556 correction: the email is OPTIONAL — declining it must not block the test.

        The relocation data is synthetic, so nothing here forces real PII. A tester who
        does not consent to be contacted still gets the full run; the session simply
        carries no contact and stays anonymous (and is skipped by the TD-M5 follow-up
        queue). This inverts the original TD-M0 assertion, which required the email.
        """
        db = _db_mock()
        body = _body()
        body.pop("tester_email", None)
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=body)
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        sess_inserts = [
            c for c in conn.execute.call_args_list if "INSERT INTO test_sessions" in str(c.args[0])
        ]
        self.assertEqual(len(sess_inserts), 1)
        # A true NULL, not '' — the follow-up queue filters on IS NOT NULL / <> ''.
        self.assertIsNone(sess_inserts[0].args[1]["tester_email"])

    def test_blank_email_is_normalised_to_null(self):
        """AIQ-1556: an empty string is the same choice as omitting it — store NULL, not ''."""
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(tester_email="   "))
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        sess_inserts = [
            c for c in conn.execute.call_args_list if "INSERT INTO test_sessions" in str(c.args[0])
        ]
        self.assertIsNone(sess_inserts[0].args[1]["tester_email"])

    def test_invalid_email_returns_422(self):
        """A malformed address that was actually typed is still rejected (unchanged).

        Optional does not mean unvalidated: if the tester opts in, the address has to be
        usable — otherwise the follow-up they consented to would silently never arrive.
        """
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision", json=_body(tester_email="notanemail"))
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

    def test_unknown_corridor_coerced_to_autoassign(self):
        """A corridor_id not in the locked set is ignored and auto-assigned instead."""
        from backend.app.routers.test_drive import _LOCKED_CORRIDORS
        db_mock = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db_mock), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(corridor_id="'; DROP--"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn(resp.json()["corridor_id"], _LOCKED_CORRIDORS)

    def test_route_registered_in_both_apps(self):
        from backend.main import app as prod_app
        from backend.app.main import app as modular_app
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            paths = [r.path for r in a.routes if "test-drive" in getattr(r, "path", "")]
            self.assertIn("/api/test-drive/provision", paths, f"route missing in {label}")


if __name__ == "__main__":
    unittest.main()
