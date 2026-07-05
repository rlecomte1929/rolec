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
        with patch.dict(os.environ, _ENABLED, clear=False), \
                patch("backend.app.routers.test_drive.db", db):
            resp = self.client.post("/api/test-drive/survey", json=_body())
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["response_id"])
        # one INSERT into survey_responses attempted
        db.engine.begin.assert_called()
        conn = db.engine.begin.return_value.__enter__.return_value
        # The survey INSERT shares the mocked engine with TD-7/TD-8 funnel writes, so
        # find the survey_responses INSERT among the calls rather than asserting exactly once.
        survey_calls = [c for c in conn.execute.call_args_list if "survey_responses" in str(c.args[0])]
        self.assertEqual(len(survey_calls), 1)
        bound = survey_calls[0].args[1]
        self.assertEqual(bound["tester_sector"], "energy")
        self.assertTrue(bound["testimonial_consent"])
        self.assertEqual(bound["pilot_interest"], "maybe")

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

    def test_route_registered_in_both_apps(self):
        from backend.main import app as prod_app
        from backend.app.main import app as modular_app
        for a, label in ((prod_app, "backend.main"), (modular_app, "backend.app.main")):
            paths = [r.path for r in a.routes if "test-drive/survey" in getattr(r, "path", "")]
            self.assertIn("/api/test-drive/survey", paths, f"survey route missing in {label}")


if __name__ == "__main__":
    unittest.main()
