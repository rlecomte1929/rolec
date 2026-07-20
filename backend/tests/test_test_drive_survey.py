"""AIQ-1423 (TD-5) — completion-survey endpoint tests.

Pins POST /api/test-drive/survey:
  1. Campaign flag off        → 404
  2. Flag on + valid body     → 200 {ok, response_id}; survey_responses INSERT attempted
  3. Out-of-range q1_overall  → 422
  4. Bad q3_problem_fit enum  → 422
  5. Route registered in BOTH app instances

db patched at the router module level (no live DB), mirroring test_test_drive_provision.py.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

_ENABLED = {"RELOPASS_TEST_DRIVE_ENABLED": "1"}


def _body(**overrides):
    body = {
        "session_id": "11111111-1111-1111-1111-111111111111",
        "corridor_id": "GB_US",
        "tester_segment": "prospect",
        "tester_name": "Alex Tester",
        "tester_email": "alex@example.test",
        "tester_sector": "energy",
        "q1_overall": 4,
        "q3_problem_fit": "yes",
        "testimonial": "Coordinates the handoffs that usually break.",
        "testimonial_consent": True,
        "pilot_interest": "maybe",
    }
    body.update(overrides)
    return body


class TestTestDriveSurvey(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_flag_off_returns_404(self):
        with patch.dict(os.environ, {"RELOPASS_TEST_DRIVE_ENABLED": "false"}, clear=False):
            resp = self.client.post("/api/test-drive/survey", json=_body())
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_valid_submission_persists_row(self):
        db = MagicMock()
        # AIQ-1542: no prior survey row for this session (first submit) → straight INSERT.
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["response_id"])
        # exactly one INSERT into survey_responses (the AIQ-1542 dedupe SELECT also names the
        # table, so match the INSERT specifically).
        db.engine.begin.assert_called()
        conn = db.engine.begin.return_value.__enter__.return_value
        survey_calls = [c for c in conn.execute.call_args_list if "INSERT INTO survey_responses" in str(c.args[0])]
        self.assertEqual(len(survey_calls), 1)
        bound = survey_calls[0].args[1]
        self.assertEqual(bound["tester_sector"], "energy")
        self.assertTrue(bound["testimonial_consent"])
        self.assertEqual(bound["pilot_interest"], "maybe")

    def test_trust_intent_persists(self):
        """TD-M4 (AIQ-1559): trust_intent + why are written to the survey_responses INSERT."""
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post(
                "/api/test-drive/survey",
                json=_body(trust_intent="yes", trust_intent_why="clear roadmap"),
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        survey_calls = [c for c in conn.execute.call_args_list if "INSERT INTO survey_responses" in str(c.args[0])]
        self.assertEqual(len(survey_calls), 1)
        self.assertIn("trust_intent", str(survey_calls[0].args[0]))
        bound = survey_calls[0].args[1]
        self.assertEqual(bound["trust_intent"], "yes")
        self.assertEqual(bound["trust_intent_why"], "clear roadmap")

    def test_bad_trust_intent_returns_422(self):
        """TD-M4: the enum (yes|maybe|no) is validated at the API — garbage is rejected."""
        with patch.dict(os.environ, _ENABLED, clear=False):
            resp = self.client.post("/api/test-drive/survey", json=_body(trust_intent="definitely"))
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_segment_propagates_to_session(self):
        """TD-FIX-2 (AIQ-1503): the self-declared segment is written back onto test_sessions."""
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body(tester_segment="internal"))
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        seg_calls = [
            c for c in conn.execute.call_args_list
            if "UPDATE test_sessions SET tester_segment" in str(c.args[0])
        ]
        self.assertEqual(len(seg_calls), 1)
        self.assertEqual(seg_calls[0].args[1]["seg"], "internal")

    def test_no_session_skips_segment_propagation(self):
        """No session_id → nothing to stamp; the segment update is skipped."""
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post(
                "/api/test-drive/survey", json=_body(session_id=None, tester_segment="prospect")
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        seg_calls = [
            c for c in conn.execute.call_args_list
            if "UPDATE test_sessions SET tester_segment" in str(c.args[0])
        ]
        self.assertEqual(len(seg_calls), 0)

    def test_no_session_no_campaign_is_unattributed_not_live_cohort(self):
        """AIQ-1639: a session-less survey with no explicit campaign must NOT be filed into
        the live 'insead-2026' cohort — it lands with campaign NULL (unattributed). Proven
        even with RELOPASS_TEST_DRIVE_CAMPAIGN set: the survey endpoint ignores the env
        default (only /provision defaults the cohort)."""
        db = MagicMock()
        # first submit → no prior row → straight INSERT.
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        env = {**_ENABLED, "RELOPASS_TEST_DRIVE_CAMPAIGN": "insead-2026"}
        with patch.dict(os.environ, env, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body(session_id=None))
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        survey_calls = [c for c in conn.execute.call_args_list if "INSERT INTO survey_responses" in str(c.args[0])]
        self.assertEqual(len(survey_calls), 1)
        bound = survey_calls[0].args[1]
        self.assertIsNone(bound["campaign"])
        self.assertNotEqual(bound["campaign"], "insead-2026")

    def test_explicit_campaign_is_honored_without_session(self):
        """AIQ-1639: an explicitly-supplied campaign is still recorded even without a session
        — only the silent env default is removed, not caller-supplied attribution."""
        db = MagicMock()
        db.engine.begin.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post(
                "/api/test-drive/survey", json=_body(session_id=None, campaign="qa-x")
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        survey_calls = [c for c in conn.execute.call_args_list if "INSERT INTO survey_responses" in str(c.args[0])]
        self.assertEqual(len(survey_calls), 1)
        self.assertEqual(survey_calls[0].args[1]["campaign"], "qa-x")

    def test_out_of_range_q1_returns_422(self):
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body(q1_overall=9))
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_bad_problem_fit_returns_422(self):
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body(q3_problem_fit="maybe"))
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_malformed_session_id_returns_422(self):
        # AIQ-1540: a non-UUID session_id must 422 (it used to 500 on CAST(:id AS uuid)).
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body(session_id="not-a-uuid"))
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_resubmit_replaces_row_not_duplicates(self):
        # AIQ-1542: a second survey for the same session replaces the row (DELETE precedes the
        # INSERT) rather than duplicating it, and the one-time 'surveyed' event does not re-fire.
        db = MagicMock()
        conn = db.engine.begin.return_value.__enter__.return_value
        conn.execute.return_value.first.return_value = (1,)  # a prior survey row exists
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit:
            resp = self.client.post("/api/test-drive/survey", json=_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        self.assertTrue(any("DELETE FROM survey_responses" in s for s in sqls), "expected a dedupe DELETE")
        self.assertTrue(any("INSERT INTO survey_responses" in s for s in sqls), "expected the replacement INSERT")
        events = [kw.get("event_type") for _, kw in emit.call_args_list]
        self.assertNotIn("surveyed", events)  # a re-submit must not re-count the tester

    def test_route_registered_in_both_apps(self):
        from backend.main import app as prod_app
        from backend.app.main import app as modular_app
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            paths = [r.path for r in a.routes if "test-drive/survey" in getattr(r, "path", "")]
            self.assertIn("/api/test-drive/survey", paths, f"survey route missing in {label}")


if __name__ == "__main__":
    unittest.main()
