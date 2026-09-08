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

    def _session_campaign(self, db):
        conn = db.engine.begin.return_value.__enter__.return_value
        sess = [c for c in conn.execute.call_args_list
                if "INSERT INTO test_sessions" in str(c.args[0])]
        self.assertEqual(len(sess), 1)
        return sess[0].args[1]["campaign"]

    def test_no_campaign_stores_unattributed_never_insead(self):
        # [campaign attribution] A provision with no campaign must NEVER be filed under the live
        # 'insead-2026' cohort — even if RELOPASS_TEST_DRIVE_CAMPAIGN is set to insead-2026. The
        # env fallback is removed; an absent campaign is 'unattributed'.
        db = _db_mock()
        with patch.dict(os.environ,
                        {**_ENABLED_ENV, "RELOPASS_TEST_DRIVE_CAMPAIGN": "insead-2026"}, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body())  # no campaign
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._session_campaign(db), "unattributed")

    def test_explicit_insead_campaign_is_preserved(self):
        # The real cohort link legitimately passes ?campaign=insead-2026 — it must pass through.
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(campaign="insead-2026"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._session_campaign(db), "insead-2026")

    def test_explicit_qa_campaign_is_preserved(self):
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision", json=_body(campaign="qa-x"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._session_campaign(db), "qa-x")

    def test_provision_seeds_vendor_selections(self):
        # [AIQ-1651] Provisioning also seeds company_vendor_selections for the corridor's
        # destination country, so Services → Recommendations shows suppliers, not "Movers (0)".
        db = _db_mock()
        with patch.dict(os.environ, _ENABLED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"), \
                patch("backend.app.routers.test_drive._seed_default_vendor_selections") as seed:
            resp = self.client.post("/api/test-drive/provision", json=_body(corridor_id="FR_NO"))
        self.assertEqual(resp.status_code, 200, resp.text)
        seed.assert_called_once()
        self.assertEqual(seed.call_args.args[0], "company-1")  # company_id
        self.assertEqual(seed.call_args.args[1], "NO")  # FR_NO → host_country

    def test_seed_vendor_selections_issues_cvs_insert(self):
        # [AIQ-1651] The helper INSERTs selected=true rows into company_vendor_selections,
        # scoped to the destination country. (The mock harness has no live DB, so we assert the
        # write is issued; the real rows are verified live in Phase 5.)
        from backend.app.routers import test_drive as td
        db = MagicMock()
        with patch.object(td, "db", db):
            td._seed_default_vendor_selections("company-1", "NO", "hr-1")
        conn = db.engine.begin.return_value.__enter__.return_value
        cvs_inserts = [
            c for c in conn.execute.call_args_list
            if "INSERT INTO company_vendor_selections" in str(c.args[0])
        ]
        self.assertEqual(len(cvs_inserts), 1)
        self.assertEqual(cvs_inserts[0].args[1]["company_id"], "company-1")
        self.assertEqual(cvs_inserts[0].args[1]["dest_country"], "NO")

    def test_seed_vendor_selections_skips_without_destination(self):
        # No destination country → no INSERT attempted, no raise.
        from backend.app.routers import test_drive as td
        db = MagicMock()
        with patch.object(td, "db", db):
            td._seed_default_vendor_selections("company-1", None, "hr-1")
        db.engine.begin.assert_not_called()

    def test_seed_vendor_selections_never_raises(self):
        # Best-effort: a seed failure must never break provisioning (logged loudly, not swallowed).
        from backend.app.routers import test_drive as td
        db = MagicMock()
        db.engine.begin.side_effect = RuntimeError("boom")
        with patch.object(td, "db", db):
            td._seed_default_vendor_selections("company-1", "NO", "hr-1")  # must not raise

    def test_seed_vendor_selections_zero_rows_logs_loud_error(self):
        # [AIQ-1652] 0 selections == an empty marketplace for the tester — the exact symptom this
        # seed prevents. It must be a LOUD structured ERROR naming company + corridor + destination,
        # never a quiet INFO (a silent empty marketplace becomes a false "no providers" verdict).
        from backend.app.routers import test_drive as td
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.rowcount = 0
        with patch.object(td, "db", db), \
                self.assertLogs("backend.app.routers.test_drive", level="ERROR") as logs:
            td._seed_default_vendor_selections("company-1", "ZZ", "hr-1", corridor="XX_ZZ")
        joined = "\n".join(logs.output)
        self.assertIn("0 selections", joined)
        self.assertIn("XX_ZZ", joined)  # corridor is named
        self.assertIn("company-1", joined)

    def test_seed_vendor_selections_success_log_names_corridor(self):
        # A successful seed logs the corridor too (structured observability).
        from backend.app.routers import test_drive as td
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.rowcount = 9
        with patch.object(td, "db", db), \
                self.assertLogs("backend.app.routers.test_drive", level="INFO") as logs:
            td._seed_default_vendor_selections("company-1", "NO", "hr-1", corridor="FR_NO")
        joined = "\n".join(logs.output)
        self.assertIn("seeded 9 vendor selection(s)", joined)
        self.assertIn("FR_NO", joined)

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
            # Task 4: the staged fixture rides the same router → present in BOTH apps.
            self.assertIn(
                "/api/test-drive/provision-staged", paths, f"staged route missing in {label}"
            )


def _staged_body(**overrides):
    body = {"first_name": "Quinn", "campaign": "qa-verify", "stage": "credentials"}
    body.update(overrides)
    return body


_STAGED_ENV = {"RELOPASS_TEST_DRIVE_ENABLED": "1", "RELOPASS_TEST_DRIVE_INVITE_TOKEN": ""}


class TestTestDriveProvisionStaged(unittest.TestCase):
    """Task 4 — QA-only staged provisioning. The gate must be HARD (flag on + `qa-*`
    campaign; reject insead-2026 and any non-qa campaign), and each stage must drive the
    REAL handlers. The stage orchestration is verified at the call level: which handlers
    run for which stage, cumulatively — the same functions an ordinary HTTP walk calls,
    which is what makes a seeded session and a hand-walked one produce equivalent rows."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    # ── Hard gate ──────────────────────────────────────────────────────────────
    def test_staged_flag_off_returns_404(self):
        with patch.dict(os.environ, {"RELOPASS_TEST_DRIVE_ENABLED": "false"}, clear=False):
            resp = self.client.post("/api/test-drive/provision-staged", json=_staged_body())
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_staged_rejects_missing_campaign(self):
        db = _db_mock()
        with patch.dict(os.environ, _STAGED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision-staged", json=_staged_body(campaign=None))
        self.assertEqual(resp.status_code, 404, resp.text)
        db.create_user.assert_not_called()  # rejected before any minting

    def test_staged_rejects_insead_campaign(self):
        db = _db_mock()
        with patch.dict(os.environ, _STAGED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision-staged", json=_staged_body(campaign="insead-2026"))
        self.assertEqual(resp.status_code, 404, resp.text)
        db.create_user.assert_not_called()

    def test_staged_rejects_non_qa_campaign(self):
        db = _db_mock()
        with patch.dict(os.environ, _STAGED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/provision-staged", json=_staged_body(campaign="prospect-x"))
        self.assertEqual(resp.status_code, 404, resp.text)
        db.create_user.assert_not_called()

    def test_staged_invalid_stage_returns_422(self):
        with patch.dict(os.environ, _STAGED_ENV, clear=False):
            resp = self.client.post("/api/test-drive/provision-staged", json=_staged_body(stage="bogus"))
        self.assertEqual(resp.status_code, 422, resp.text)

    # ── Accept path (credentials stage does not advance) ────────────────────────
    def test_staged_qa_credentials_mints_and_does_not_advance(self):
        db = _db_mock()
        with patch.dict(os.environ, _STAGED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"):
            resp = self.client.post("/api/test-drive/provision-staged", json=_staged_body(stage="credentials"))
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["stage"], "credentials")
        self.assertIsNone(data["case_id"])
        self.assertTrue(data["hr"]["username"].startswith("HR-"))
        self.assertTrue(data["employee"]["username"].startswith("EMP-"))
        self.assertEqual(data["campaign"], "qa-verify")
        self.assertEqual(db.create_user.call_count, 2)  # minted, but no case created

    def test_staged_default_stage_is_shortlist_ready(self):
        db = _db_mock()
        with patch.dict(os.environ, _STAGED_ENV, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._dispatch_supabase_sync"), \
                patch(
                    "backend.app.routers.test_drive._advance_to_stage",
                    return_value={"stage": "shortlist_ready", "case_id": "c1", "assignment_id": "a1"},
                ) as adv:
            body = _staged_body()
            body.pop("stage")  # omitted → default
            resp = self.client.post("/api/test-drive/provision-staged", json=body)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(adv.call_args.args[0], "shortlist_ready")
        self.assertEqual(resp.json()["stage"], "shortlist_ready")

    # ── Orchestration: each stage drives exactly the right REAL handlers ─────────
    def _ctx(self):
        return {
            "hr_id": "hr-1", "hr_email": "hr-x@probe.test", "hr_username": "HR-x-1",
            "emp_id": "emp-1", "emp_email": "emp-x@probe.test", "emp_username": "EMP-x-1",
            "first_name": "Quinn", "corridor_id": "FR_NO",
        }

    def _patch_handlers(self):
        import contextlib
        from types import SimpleNamespace

        stack = contextlib.ExitStack()
        handlers = {
            "create": stack.enter_context(
                patch("backend.main.create_case", return_value=SimpleNamespace(caseId="case-1"))
            ),
            "assign": stack.enter_context(
                patch("backend.main.assign_case", return_value=SimpleNamespace(assignmentId="asg-1"))
            ),
            "submit": stack.enter_context(patch("backend.main.submit_assignment")),
            "patch_c": stack.enter_context(patch("backend.app.routers.cases_write.patch_case")),
            "wait": stack.enter_context(
                patch("backend.app.routers.test_drive._wait_for_roadmap", return_value=7)
            ),
            "shortlist": stack.enter_context(
                patch(
                    "backend.app.routers.test_drive._build_shortlist_state",
                    return_value={"categories": ["movers"], "item_count": 2},
                )
            ),
        }
        return stack, handlers

    def test_advance_credentials_is_noop(self):
        from backend.app.routers.test_drive import _advance_to_stage
        stack, h = self._patch_handlers()
        with stack:
            out = _advance_to_stage("credentials", self._ctx())
        h["create"].assert_not_called()
        self.assertEqual(out, {"stage": "credentials"})

    def test_advance_case_created_creates_and_assigns(self):
        from backend.app.routers.test_drive import _advance_to_stage
        stack, h = self._patch_handlers()
        with stack:
            out = _advance_to_stage("case_created", self._ctx())
        h["create"].assert_called_once()
        h["assign"].assert_called_once()
        h["patch_c"].assert_not_called()
        h["submit"].assert_not_called()
        self.assertEqual(out["case_id"], "case-1")
        self.assertEqual(out["assignment_id"], "asg-1")

    def test_advance_intake_complete_patches_case(self):
        from backend.app.routers.test_drive import _advance_to_stage
        stack, h = self._patch_handlers()
        with stack:
            _advance_to_stage("intake_complete", self._ctx())
        h["patch_c"].assert_called_once()
        h["submit"].assert_not_called()

    def test_advance_roadmap_ready_submits_and_waits(self):
        from backend.app.routers.test_drive import _advance_to_stage
        stack, h = self._patch_handlers()
        with stack:
            out = _advance_to_stage("roadmap_ready", self._ctx())
        h["submit"].assert_called_once()
        h["wait"].assert_called_once()
        h["shortlist"].assert_not_called()
        self.assertEqual(out["milestones"], 7)

    def test_advance_shortlist_ready_builds_shortlist(self):
        from backend.app.routers.test_drive import _advance_to_stage
        stack, h = self._patch_handlers()
        with stack:
            out = _advance_to_stage("shortlist_ready", self._ctx())
        h["submit"].assert_called_once()
        h["shortlist"].assert_called_once()
        self.assertEqual(out["shortlist"], {"categories": ["movers"], "item_count": 2})


if __name__ == "__main__":
    unittest.main()
