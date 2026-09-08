"""
[P3-02a] Tests for the production crawl-scheduler cron endpoint.

POST /api/crons/process-crawl-schedules is CRON_SECRET-guarded and processes all
due crawl schedules. We mock process_due_schedules to keep the test DB-free.
"""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient

from backend.main import app

CRON_PATH = "/api/crons/process-crawl-schedules"


class TestProcessCrawlSchedulesCron(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_rejects_when_secret_not_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CRON_SECRET", None)
            r = self.client.post(CRON_PATH)
        self.assertEqual(r.status_code, 503)

    def test_rejects_invalid_token(self):
        with patch.dict(os.environ, {"CRON_SECRET": "right"}):
            r = self.client.post(CRON_PATH, headers={"Authorization": "Bearer wrong"})
        self.assertEqual(r.status_code, 401)

    def test_processes_due_schedules_and_summarizes(self):
        fake_results = [
            {"schedule_id": "s1", "status": "succeeded", "run_id": "r1"},
            {"schedule_id": "s2", "status": "failed", "error": "boom"},
            {"schedule_id": "s3", "status": "skipped", "reason": "lock_failed"},
        ]
        with patch.dict(os.environ, {"CRON_SECRET": "right"}), \
             patch("backend.app.routers.crons.process_due_schedules",
                   return_value=fake_results) as mock_proc, \
             patch("backend.app.routers.crons.notify_superseded_rules",
                   return_value={"notified": 0}):
            r = self.client.post(CRON_PATH, headers={"Authorization": "Bearer right"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["processed"], 3)
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["failed"], 1)
        mock_proc.assert_called_once()

    # [AIQ-872] The daily crawl tick also fires the rule-change notifier.
    def test_fires_rule_change_notifier_on_tick(self):
        with patch.dict(os.environ, {"CRON_SECRET": "right"}), \
             patch("backend.app.routers.crons.process_due_schedules", return_value=[]), \
             patch("backend.app.routers.crons.notify_superseded_rules",
                   return_value={"notified": 2, "skipped_idempotent": 1}) as mock_notify:
            r = self.client.post(CRON_PATH, headers={"Authorization": "Bearer right"})
        self.assertEqual(r.status_code, 200)
        mock_notify.assert_called_once()
        self.assertEqual(
            r.json()["rule_change_notifications"],
            {"notified": 2, "skipped_idempotent": 1},
        )

    def test_notifier_error_is_non_fatal(self):
        with patch.dict(os.environ, {"CRON_SECRET": "right"}), \
             patch("backend.app.routers.crons.process_due_schedules", return_value=[]), \
             patch("backend.app.routers.crons.notify_superseded_rules",
                   side_effect=RuntimeError("db down")):
            r = self.client.post(CRON_PATH, headers={"Authorization": "Bearer right"})
        # Crawl cron must stay green even if the notifier blows up.
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["rule_change_notifications"], {"error": "notifier_failed"})


if __name__ == "__main__":
    unittest.main()
