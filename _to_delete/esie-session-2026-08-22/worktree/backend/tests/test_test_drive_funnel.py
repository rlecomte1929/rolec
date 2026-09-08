"""AIQ-1426 (TD-8) — funnel-event recorder tests.

Pins POST /api/test-drive/event:
  1. Campaign flag off      → 404
  2. Valid event            → 200 {ok}; funnel_events INSERT attempted
  3. Unknown event_type     → 400
  4. Extra field (forbid)   → 422
  5. Route in BOTH apps
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


class TestTestDriveFunnel(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_flag_off_returns_404(self):
        with patch.dict(os.environ, {"RELOPASS_TEST_DRIVE_ENABLED": "false"}, clear=False):
            resp = self.client.post("/api/test-drive/event", json={"event_type": "click"})
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_valid_event_records_row(self):
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post(
                "/api/test-drive/event",
                json={"event_type": "click", "corridor_id": "GB_US", "invite_token": "t", "metadata": {"utm": "li"}},
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["ok"])
        db.engine.begin.assert_called()
        conn = db.engine.begin.return_value.__enter__.return_value
        sql = str(conn.execute.call_args.args[0])
        self.assertIn("funnel_events", sql)

    def test_journey_stage_events_accepted(self):
        """TD-FIX-4 (AIQ-1505): the mid-journey stages are allow-listed (incl the new
        'intake-completed') so the frontend can record them at each milestone."""
        db = MagicMock()
        stages = ["hr-handoff", "intake-start", "intake-completed", "roadmap-reached", "vendor-selected"]
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            for et in stages:
                resp = self.client.post(
                    "/api/test-drive/event",
                    json={"event_type": et, "session_id": "11111111-1111-1111-1111-111111111111"},
                )
                self.assertEqual(resp.status_code, 200, f"{et}: {resp.text}")

    def test_friction_event_accepted_with_metadata(self):
        """TD-M1 (AIQ-1557): 'friction' is allow-listed and its {stage, reason, text}
        metadata (short scalar strings) is persisted on the funnel_events row."""
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post(
                "/api/test-drive/event",
                json={
                    "event_type": "friction",
                    "session_id": "11111111-1111-1111-1111-111111111111",
                    "metadata": {"stage": "intake", "reason": "confusing", "text": "lost me here"},
                },
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        conn = db.engine.begin.return_value.__enter__.return_value
        params = conn.execute.call_args.args[1]
        self.assertEqual(params["event_type"], "friction")
        self.assertIn("intake", params["metadata"])
        self.assertIn("confusing", params["metadata"])
        self.assertIn("lost me here", params["metadata"])

    def test_unknown_event_type_returns_400(self):
        db = MagicMock()
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/event", json={"event_type": "not-a-real-event"})
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_extra_field_rejected_422(self):
        with patch.dict(os.environ, _ENABLED, clear=False):
            resp = self.client.post(
                "/api/test-drive/event", json={"event_type": "click", "evil": "x"}
            )
        self.assertEqual(resp.status_code, 422, resp.text)

    def test_route_registered_in_both_apps(self):
        from backend.main import app as prod_app
        from backend.app.main import app as modular_app
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            paths = [r.path for r in a.routes if "test-drive/event" in getattr(r, "path", "")]
            self.assertIn("/api/test-drive/event", paths, f"event route missing in {label}")


if __name__ == "__main__":
    unittest.main()
