"""AIQ-1425 (TD-7) — survey → pipeline tests.

The survey endpoint's on-submit pipeline:
  1. Q7 referral → a prospect_candidates row (referred_by + corridor_id in raw_input_json,
     NEVER under 'notes'; status 'maybe'; enrichment not queued).
  2. Q6 pilot Yes/Maybe → a 'pilot-interested' funnel event; an 'intro' event for the referral.
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


class TestTestDriveReferral(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_referral_creates_prospect_and_pilot_event(self):
        db = MagicMock()
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


if __name__ == "__main__":
    unittest.main()
