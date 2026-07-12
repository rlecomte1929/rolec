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

    # ── TD-FIX-1 (AIQ-1502): belt-and-braces completion on survey submit ──────
    def _emitted_events(self, emit):
        return [c.kwargs.get("event_type") for c in emit.call_args_list]

    def test_survey_completes_incomplete_session(self):
        """Submitting the survey on a session with no completed_at marks it completed
        and emits a distinct 'completed' event alongside 'surveyed'."""
        db = _db_with_session({"completed_at": None})
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._process_survey_pipeline"), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit:
            resp = self.client.post(
                "/api/test-drive/survey",
                json={"session_id": "sess-1", "campaign": "insead-2026"},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        self.assertIn("UPDATE test_sessions", sqls)
        events = self._emitted_events(emit)
        self.assertIn("completed", events)  # belt-and-braces completion
        self.assertIn("surveyed", events)   # kept distinct

    def test_survey_does_not_recomplete_already_completed_session(self):
        """A session already completed (via the CTA) is not re-completed by the survey:
        no UPDATE, no second 'completed' event — only 'surveyed'."""
        db = _db_with_session({"completed_at": "2026-07-12T10:00:00"})
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db), \
                patch("backend.app.routers.test_drive._process_survey_pipeline"), \
                patch("backend.app.routers.test_drive._emit_funnel_event") as emit:
            resp = self.client.post(
                "/api/test-drive/survey",
                json={"session_id": "sess-1", "campaign": "insead-2026"},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        self.assertNotIn("UPDATE test_sessions", sqls)
        events = self._emitted_events(emit)
        self.assertNotIn("completed", events)
        self.assertIn("surveyed", events)


if __name__ == "__main__":
    unittest.main()
