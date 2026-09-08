"""
[P3-02c] Tests for alert wiring: consecutive-failure counting, the 3rd-failure
gate, and the test-alert cron endpoint.
"""
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from backend.app.services import crawl_scheduler_service as css


def _supabase_returning(rows):
    sb = MagicMock()
    (sb.table.return_value.select.return_value.eq.return_value
       .order.return_value.limit.return_value.execute.return_value.data) = rows
    return sb


class TestConsecutiveFailures(unittest.TestCase):
    def test_counts_leading_failures_only(self):
        rows = [{"status": "failed"}, {"status": "failed"}, {"status": "failed"},
                {"status": "succeeded"}, {"status": "failed"}]
        with patch.object(css, "_get_supabase", return_value=_supabase_returning(rows)):
            self.assertEqual(css.count_consecutive_failures("s1"), 3)

    def test_stops_at_first_success(self):
        rows = [{"status": "failed"}, {"status": "succeeded"}, {"status": "failed"}]
        with patch.object(css, "_get_supabase", return_value=_supabase_returning(rows)):
            self.assertEqual(css.count_consecutive_failures("s1"), 1)


class TestFailureGate(unittest.TestCase):
    def test_alerts_fire_at_third_consecutive_failure(self):
        with patch.object(css, "count_consecutive_failures", return_value=3), \
             patch("backend.app.services.monitoring_alerts.alert_crawl_failure") as mock_alert, \
             patch("backend.app.services.ops_notification_service.evaluate_crawl_failure_notification") as mock_ops:
            css._handle_schedule_failure("s1", "oslo_kommune", job_run_id="j1")
        mock_alert.assert_called_once()
        mock_ops.assert_called_once()

    def test_no_alert_below_threshold(self):
        with patch.object(css, "count_consecutive_failures", return_value=2), \
             patch("backend.app.services.monitoring_alerts.alert_crawl_failure") as mock_alert:
            css._handle_schedule_failure("s1", "oslo_kommune")
        mock_alert.assert_not_called()


class TestTestAlertEndpoint(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        self.client = TestClient(app)

    def test_rejects_invalid_token(self):
        with patch.dict(os.environ, {"CRON_SECRET": "right"}):
            r = self.client.post("/api/crons/test-monitoring-alert",
                                 headers={"Authorization": "Bearer wrong"})
        self.assertEqual(r.status_code, 401)

    def test_fires_test_alert_with_valid_token(self):
        fake = {"event_type": "test", "slack": True, "email": False}
        with patch.dict(os.environ, {"CRON_SECRET": "right"}), \
             patch("backend.app.routers.crons.send_test_alert", return_value=fake) as mock_send:
            r = self.client.post("/api/crons/test-monitoring-alert",
                                 headers={"Authorization": "Bearer right"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["slack"], True)
        mock_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
