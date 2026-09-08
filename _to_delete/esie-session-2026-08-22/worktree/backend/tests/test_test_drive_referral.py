"""AIQ-1425 (TD-7) — survey → pipeline tests.

The survey endpoint's on-submit pipeline:
  1. Q7 referral → a prospect_candidates row (referred_by + corridor_id in raw_input_json,
     NEVER under 'notes'; status 'maybe'; enrichment not queued).
  2. Q6 pilot Yes/Maybe → a 'pilot-interested' funnel event; an 'intro' event for the referral.

Multi-referral: the survey now takes a `referrals: [{name, company_role, contact, consent}]`
array. The full list is written to survey_responses.referrals (jsonb) and referrals[0] is
MIRRORED into the legacy referral_* scalar columns, which two live readers still depend on
(the admin panel's "intro" count and the daily Cowork warm-lead alert). An old-shape payload
that sends only the legacy scalars is wrapped back into a 1-element list.
"""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

_ENABLED = {"RELOPASS_TEST_DRIVE_ENABLED": "1"}


def _survey_body(**overrides):
    body = {
        "session_id": "11111111-1111-1111-1111-111111111111",
        "corridor_id": "GB_US",
        "tester_segment": "prospect",
        "tester_name": "Alex Tester",
        "tester_email": "alex@example.test",
        "pilot_interest": "maybe",
        "referral_name": "Jordan Peer",
        "referral_company_role": "Head of Mobility, Globex",
        "referral_contact": "jordan@globex.test",
        "referral_consent": True,
    }
    body.update(overrides)
    return body


def _insert_params(db):
    """The bound parameters of the single INSERT INTO survey_responses."""
    conn = db.engine.begin.return_value.__enter__.return_value
    inserts = [
        c for c in conn.execute.call_args_list if "INSERT INTO survey_responses" in str(c.args[0])
    ]
    assert len(inserts) == 1, f"expected exactly 1 survey INSERT, got {len(inserts)}"
    return inserts[0].args[1]


def _fresh_db():
    """A mocked db whose dedupe SELECT reports no prior row → first submit, pipeline runs."""
    db = MagicMock()
    db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
    return db


class TestTestDriveReferral(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_referral_creates_prospect_and_pilot_event(self):
        db = MagicMock()
        # AIQ-1542: first submit for this session (no prior survey row) → pipeline runs.
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit, \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post("/api/test-drive/survey", json=_survey_body())

        self.assertEqual(resp.status_code, 200, resp.text)

        # funnel events: surveyed + pilot-interested + intro
        events = [c.kwargs.get("event_type") for c in emit.call_args_list]
        self.assertIn("surveyed", events)
        self.assertIn("pilot-interested", events)
        self.assertIn("intro", events)

        # a prospect_candidates row was added, with referral PII in dedicated keys (not 'notes')
        session.add.assert_called_once()
        row = session.add.call_args.args[0]
        self.assertEqual(row.status, "maybe")
        self.assertTrue(row.company_name)
        raw = json.loads(row.raw_input_json)
        self.assertEqual(raw["referred_by"], "Alex Tester")
        self.assertEqual(raw["corridor_id"], "GB_US")
        self.assertEqual(raw["referral_contact"], "jordan@globex.test")
        self.assertNotIn("notes", raw)  # 'notes' is the LLM-enrichment field — must stay clean
        session.commit.assert_called_once()

    def test_no_referral_no_prospect(self):
        db = MagicMock()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit, \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post(
                "/api/test-drive/survey",
                json=_survey_body(referral_name="", referral_contact="", pilot_interest="no"),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        session.add.assert_not_called()
        events = [c.kwargs.get("event_type") for c in emit.call_args_list]
        self.assertNotIn("pilot-interested", events)
        self.assertNotIn("intro", events)


    def test_session_context_derives_campaign_and_corridor(self):
        """AIQ-1546: campaign + corridor are taken from the linked session (source of
        truth) and override the body's often-absent/stale values, flowing into the
        funnel events and the prospect row."""
        db = MagicMock()
        # AIQ-1542: first submit for this session (no prior survey row) → pipeline runs.
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=("qa-camp", "IN_DE")), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit, \
                patch("backend.app.db.SessionLocal", session_local):
            # Body carries NO corridor and a DIFFERENT campaign — the session must win.
            resp = self.client.post(
                "/api/test-drive/survey", json=_survey_body(corridor_id=None, campaign="body-camp"),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        intro = [c for c in emit.call_args_list if c.kwargs.get("event_type") == "intro"][0]
        self.assertEqual(intro.kwargs.get("corridor_id"), "IN_DE")
        self.assertEqual(intro.kwargs.get("campaign"), "qa-camp")
        raw = json.loads(session.add.call_args.args[0].raw_input_json)
        self.assertEqual(raw["corridor_id"], "IN_DE")
        self.assertEqual(raw["campaign"], "qa-camp")


    # ── multi-referral ────────────────────────────────────────────────────────
    def test_three_referrals_persist_and_first_mirrors_to_legacy_columns(self):
        """Acceptance 3: all three land in `referrals`; the legacy scalar columns hold the
        first, so the admin 'intro' count and the daily warm-lead alert keep working."""
        db = _fresh_db()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        referrals = [
            {"name": "Jordan Peer", "company_role": "Head of Mobility, Globex",
             "contact": "jordan@globex.test", "consent": True},
            {"name": "Sam Two", "company_role": "HRD, Initech", "contact": "sam@initech.test",
             "consent": False},
            {"name": "Robin Three", "company_role": "People Ops, Umbrella",
             "contact": "robin@umbrella.test", "consent": True},
        ]
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit, \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post(
                "/api/test-drive/survey",
                # Only the array — no legacy scalars. The mirror must come from referrals[0].
                json=_survey_body(
                    referral_name=None, referral_company_role=None,
                    referral_contact=None, referral_consent=False, referrals=referrals,
                ),
            )
        self.assertEqual(resp.status_code, 200, resp.text)

        params = _insert_params(db)
        stored = json.loads(params["referrals"])
        self.assertEqual(len(stored), 3)
        self.assertEqual([r["name"] for r in stored], ["Jordan Peer", "Sam Two", "Robin Three"])
        self.assertEqual(stored[1]["contact"], "sam@initech.test")
        self.assertEqual([r["consent"] for r in stored], [True, False, True])

        # Legacy columns mirror referrals[0] — NOT NULL, or the two live readers go blind.
        self.assertEqual(params["referral_name"], "Jordan Peer")
        self.assertEqual(params["referral_company_role"], "Head of Mobility, Globex")
        self.assertEqual(params["referral_contact"], "jordan@globex.test")
        self.assertTrue(params["referral_consent"])

        # One prospect_candidates row per referral; exactly one 'intro' event carrying the count.
        self.assertEqual(session.add.call_count, 3)
        names = [
            json.loads(c.args[0].raw_input_json)["referral_name"] for c in session.add.call_args_list
        ]
        self.assertEqual(names, ["Jordan Peer", "Sam Two", "Robin Three"])
        intros = [c for c in emit.call_args_list if c.kwargs.get("event_type") == "intro"]
        self.assertEqual(len(intros), 1)
        self.assertEqual(intros[0].kwargs["metadata"]["count"], 3)

    def test_old_shape_single_referral_lands_in_both(self):
        """Acceptance 4: a legacy client sends no array — the scalars are wrapped into a
        1-element `referrals` list AND kept in the legacy columns."""
        db = _fresh_db()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event"), \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post("/api/test-drive/survey", json=_survey_body())  # no `referrals`
        self.assertEqual(resp.status_code, 200, resp.text)

        params = _insert_params(db)
        stored = json.loads(params["referrals"])
        self.assertEqual(stored, [{
            "name": "Jordan Peer",
            "company_role": "Head of Mobility, Globex",
            "contact": "jordan@globex.test",
            "consent": True,
        }])
        self.assertEqual(params["referral_name"], "Jordan Peer")
        self.assertEqual(params["referral_contact"], "jordan@globex.test")
        self.assertTrue(params["referral_consent"])
        session.add.assert_called_once()

    def test_no_referrals_still_succeeds_with_empty_array(self):
        """Acceptance 5: an empty referral block never blocks the submit — `referrals` is []
        and the legacy columns are NULL/false."""
        db = _fresh_db()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit, \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post(
                "/api/test-drive/survey",
                json=_survey_body(
                    referral_name="", referral_company_role="", referral_contact="",
                    referral_consent=False, referrals=[],
                ),
            )
        self.assertEqual(resp.status_code, 200, resp.text)

        params = _insert_params(db)
        self.assertEqual(json.loads(params["referrals"]), [])
        self.assertIsNone(params["referral_name"])
        self.assertIsNone(params["referral_contact"])
        self.assertFalse(params["referral_consent"])
        session.add.assert_not_called()
        self.assertNotIn("intro", [c.kwargs.get("event_type") for c in emit.call_args_list])

    def test_blank_and_role_only_rows_are_dropped(self):
        """Untouched rows from the repeatable block, and a company/role with nobody to reach,
        must not become referrals — otherwise the admin 'intro' count counts ghosts."""
        db = _fresh_db()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event"), \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post(
                "/api/test-drive/survey",
                json=_survey_body(referrals=[
                    {"name": "  ", "company_role": "", "contact": "  ", "consent": False},
                    {"name": "", "company_role": "Some Co", "contact": "", "consent": True},
                    {"name": "Real Person", "company_role": "", "contact": "", "consent": False},
                ]),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        stored = json.loads(_insert_params(db)["referrals"])
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["name"], "Real Person")
        self.assertIsNone(stored[0]["company_role"])

    def test_over_cap_referrals_truncate_rather_than_422(self):
        """A survey must never fail on an optional field: an over-long list is truncated."""
        db = _fresh_db()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event"), \
                patch("backend.app.db.SessionLocal", session_local):
            resp = self.client.post(
                "/api/test-drive/survey",
                json=_survey_body(referrals=[
                    {"name": f"Person {i}", "contact": f"p{i}@x.test"} for i in range(25)
                ]),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(json.loads(_insert_params(db)["referrals"])), 10)

    def test_survey_hands_the_full_referral_list_to_the_notifier(self):
        """End-to-end wiring: the completion notification must receive EVERY referral, not
        just the legacy mirrored first one — otherwise the admin alert names one person."""
        db = _fresh_db()
        session = MagicMock()
        session_local = MagicMock()
        session_local.return_value.__enter__.return_value = session
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._session_context", return_value=(None, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event"), \
                patch("backend.app.db.SessionLocal", session_local), \
                patch("backend.app.services.test_drive_notifications."
                      "notify_test_drive_completion") as notify:
            resp = self.client.post("/api/test-drive/survey", json=_survey_body(referrals=[
                {"name": "Marie", "contact": "marie@x.test", "consent": True},
                {"name": "Jan", "contact": "jan@x.test", "consent": False},
                {"name": "Robin", "contact": "robin@x.test", "consent": True},
            ]))
        self.assertEqual(resp.status_code, 200, resp.text)
        notify.assert_called_once()
        passed = notify.call_args.kwargs["referrals"]
        self.assertEqual([r["name"] for r in passed], ["Marie", "Jan", "Robin"])
        self.assertEqual([r["consent"] for r in passed], [True, False, True])
        # The legacy scalars are still sent alongside, mirroring referrals[0].
        self.assertEqual(notify.call_args.kwargs["referral_name"], "Marie")

    def test_invalid_lead_in_email_rejected(self):
        """AIQ-1543: a non-empty but malformed lead-in email is rejected server-side (422)."""
        with patch.dict(os.environ, _ENABLED, clear=False):
            resp = self.client.post(
                "/api/test-drive/survey", json=_survey_body(tester_email="notanemail"),
            )
        self.assertEqual(resp.status_code, 422, resp.text)


if __name__ == "__main__":
    unittest.main()
