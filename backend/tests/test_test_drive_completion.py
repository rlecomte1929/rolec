"""AIQ-1422 (TD-4) — completion-detection endpoint tests.

Pins POST /api/test-drive/complete:
  1. Campaign flag off        → 404
  2. Unknown session          → 404
  3. State reached            → 200 {reached: True}; test_sessions UPDATE fires
  4. State not reached        → 200 {reached: False, nudge}; still completes (soft)
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
_SESSION_ROW = {
    "hr_username": "HR-alex-1a2b",
    "campaign": "insead-2026",
    "corridor_id": "GB_US",
    "tester_segment": "prospect",
}


def _db_with_session(row):
    """MagicMock db whose SELECT ... test_sessions returns `row` via .mappings().first()."""
    db = MagicMock()
    conn = db.engine.begin.return_value.__enter__.return_value
    conn.execute.return_value.mappings.return_value.first.return_value = row
    return db


class TestTestDriveCompletion(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_flag_off_returns_404(self):
        with patch.dict(os.environ, {"RELOPASS_TEST_DRIVE_ENABLED": "false"}, clear=False):
            resp = self.client.post("/api/test-drive/complete", json={"session_id": "s1"})
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_unknown_session_returns_404(self):
        db = _db_with_session(None)
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/complete", json={"session_id": "nope"})
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_reached_marks_complete(self):
        db = _db_with_session(dict(_SESSION_ROW))
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._check_completion_reached", return_value=(True, None)), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit:
            resp = self.client.post("/api/test-drive/complete", json={"session_id": "sess-1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["reached"])
        self.assertIsNone(data["nudge"])
        # the UPDATE ... test_sessions fired
        conn = db.engine.begin.return_value.__enter__.return_value
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        self.assertIn("UPDATE test_sessions", sqls)
        emit.assert_called()  # a 'completed' funnel event

    def test_not_reached_still_completes_with_nudge(self):
        db = _db_with_session(dict(_SESSION_ROW))
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._check_completion_reached", return_value=(False, "finish the case")), \
                patch("backend.app.routers.test_drive._emit_funnel_event"):
            resp = self.client.post("/api/test-drive/complete", json={"session_id": "sess-1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertFalse(data["reached"])
        self.assertEqual(data["nudge"], "finish the case")
        conn = db.engine.begin.return_value.__enter__.return_value
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        self.assertIn("UPDATE test_sessions", sqls)


class TestSurveyBackfillsCompletion(unittest.TestCase):
    """TD-FIX-1 (AIQ-1502) belt-and-braces: the survey page is reachable directly, so a
    submit on a session that never hit the /complete CTA must still mark it completed —
    with a 'completed' funnel event kept distinct from 'surveyed', fired at most once."""

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def _survey_body(self, **overrides):
        body = {
            "session_id": "11111111-1111-1111-1111-111111111111",
            "corridor_id": "GB_US",
            "tester_segment": "prospect",
            "q1_overall": 4,
        }
        body.update(overrides)
        return body

    def test_survey_marks_session_completed(self):
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit:
            resp = self.client.post("/api/test-drive/survey", json=self._survey_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        # An idempotent UPDATE ... completed_at IS NULL fired.
        conn = db.engine.begin.return_value.__enter__.return_value
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        self.assertIn("UPDATE test_sessions", sqls)
        self.assertIn("completed_at IS NULL", sqls)
        # Both funnel events fired and stayed distinct.
        events = [kw.get("event_type") for _, kw in emit.call_args_list]
        self.assertIn("completed", events)
        self.assertIn("surveyed", events)

    def test_survey_without_session_does_not_complete(self):
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit:
            resp = self.client.post("/api/test-drive/survey", json=self._survey_body(session_id=None))
        self.assertEqual(resp.status_code, 200, resp.text)
        events = [kw.get("event_type") for _, kw in emit.call_args_list]
        self.assertNotIn("completed", events)  # no session → nothing to backfill


if __name__ == "__main__":
    unittest.main()
