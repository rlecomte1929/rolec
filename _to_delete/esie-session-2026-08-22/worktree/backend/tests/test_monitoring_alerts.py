"""
[P3-02c] Tests for the source-monitoring alert delivery service.

Slack (incoming webhook) + email fan-out for material changes and repeated
crawl failures. Channels are mocked; no network or DB required.
"""
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.services import monitoring_alerts


class TestSlackAlert(unittest.TestCase):
    def test_posts_to_webhook_when_configured(self):
        resp = MagicMock(status_code=200)
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.test/abc"}), \
             patch.object(monitoring_alerts.requests, "post", return_value=resp) as mock_post:
            ok = monitoring_alerts.send_slack_alert("hello world", severity="warning")
        self.assertTrue(ok)
        mock_post.assert_called_once()
        called_url = mock_post.call_args.args[0]
        self.assertEqual(called_url, "https://hooks.slack.test/abc")
        payload = mock_post.call_args.kwargs["json"]
        self.assertIn("hello world", payload["text"])

    def test_noop_when_webhook_not_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SLACK_WEBHOOK_URL", None)
            with patch.object(monitoring_alerts.requests, "post") as mock_post:
                ok = monitoring_alerts.send_slack_alert("hello")
        self.assertFalse(ok)
        mock_post.assert_not_called()

    def test_non_2xx_returns_false(self):
        resp = MagicMock(status_code=500)
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.test/abc"}), \
             patch.object(monitoring_alerts.requests, "post", return_value=resp):
            ok = monitoring_alerts.send_slack_alert("hello")
        self.assertFalse(ok)


class TestDispatch(unittest.TestCase):
    def test_fans_out_to_both_channels(self):
        with patch.object(monitoring_alerts, "send_slack_alert", return_value=True) as ms, \
             patch.object(monitoring_alerts, "send_email_alert", return_value=True) as me:
            result = monitoring_alerts.dispatch_monitoring_alert(
                "material_change", "Title", "Body", severity="warning")
        self.assertEqual(result["slack"], True)
        self.assertEqual(result["email"], True)
        self.assertEqual(result["event_type"], "material_change")
        ms.assert_called_once()
        me.assert_called_once()

    def test_alert_crawl_failure_message_mentions_source_and_count(self):
        with patch.object(monitoring_alerts, "dispatch_monitoring_alert",
                          return_value={"slack": True, "email": False}) as md:
            monitoring_alerts.alert_crawl_failure("oslo_kommune", 3, schedule_id="s1")
        args, kwargs = md.call_args
        joined = " ".join(str(a) for a in args)
        self.assertIn("oslo_kommune", joined)
        self.assertIn("3", joined)
        self.assertEqual(kwargs.get("severity"), "critical")

    def test_alert_material_change_message_mentions_source(self):
        with patch.object(monitoring_alerts, "dispatch_monitoring_alert",
                          return_value={"slack": True, "email": False}) as md:
            monitoring_alerts.alert_material_change("oslo_kommune", 2, country_code="NO")
        joined = " ".join(str(a) for a in md.call_args.args)
        self.assertIn("oslo_kommune", joined)


class TestEmailAlert(unittest.TestCase):
    def test_noop_when_no_recipient(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPS_ALERT_EMAIL", None)
            ok = monitoring_alerts.send_email_alert("subj", "title", "body")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
