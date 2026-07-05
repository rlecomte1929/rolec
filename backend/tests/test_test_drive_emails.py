"""AIQ-1424 (TD-6) — Test-Drive email fan-out tests.

  1. Dry-run (RESEND_API_KEY unset) → both composers 'logged'; notify body carries
     pilot interest + testimonial + referral (when consented) + Q1-Q4.
  2. Reply-to / from wiring (RESEND_API_KEY set, HTTP mocked): notify reply-to = tester;
     thank-you from = "Romain Lecomte <…>", reply-to = Romain.
  3. Consent gate: referral omitted from the notify body when referral_consent = false.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from backend.app.services.test_drive_emails import (
    render_notify_email,
    send_test_drive_survey_emails,
)

_SURVEY = dict(
    tester_name="Alex Tester",
    tester_email="alex@example.test",
    campaign="insead-2026",
    corridor_id="GB_US",
    tester_segment="prospect",
    company_role="Head of Mobility",
    sector="energy",
    q1_overall=4,
    q2_friction="the intake step",
    q3_problem_fit="yes",
    q4_change="fewer clicks",
    pilot_interest="yes",
    pilot_note="Q3 budget",
    testimonial="Coordinates the handoffs that usually break.",
    referral_name="Jordan Peer",
    referral_company_role="Head of Mobility, Globex",
    referral_contact="jordan@globex.test",
    referral_consent=True,
)


class TestTestDriveEmails(unittest.TestCase):
    def test_dry_run_returns_logged_with_full_notify_body(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESEND_API_KEY", None)
            out = send_test_drive_survey_emails(**_SURVEY)
            self.assertEqual(out["notify"], "logged")
            self.assertEqual(out["thank_you"], "logged")

            subject, plain, html = render_notify_email(**_SURVEY)
        self.assertIn("PILOT", subject)
        self.assertIn("Pilot interest: YES", plain)
        self.assertIn("Coordinates the handoffs", plain)
        self.assertIn("jordan@globex.test", plain)  # consented referral present
        self.assertIn("Q1 overall", plain)

    def test_reply_to_and_from_wiring(self):
        env = {"RESEND_API_KEY": "re_test", "EMAIL_FROM": "noreply@relopass.com"}
        with patch.dict(os.environ, env, clear=False), \
                patch("backend.app.services.assignment_invite_email.http_requests.post") as post:
            post.return_value = MagicMock(ok=True)
            send_test_drive_survey_emails(**_SURVEY)

        self.assertEqual(post.call_count, 2)
        notify = post.call_args_list[0].kwargs["json"]
        self.assertEqual(notify["to"], ["romain.lecomte@relopass.com"])
        self.assertEqual(notify["from"], "noreply@relopass.com")
        self.assertEqual(notify["reply_to"], "alex@example.test")

        thank = post.call_args_list[1].kwargs["json"]
        self.assertEqual(thank["to"], ["alex@example.test"])
        self.assertEqual(thank["from"], "Romain Lecomte <romain.lecomte@relopass.com>")
        self.assertEqual(thank["reply_to"], "romain.lecomte@relopass.com")

    def test_referral_consent_gate(self):
        _, with_consent, _ = render_notify_email(**{**_SURVEY, "referral_consent": True})
        self.assertIn("jordan@globex.test", with_consent)

        _, without, _ = render_notify_email(**{**_SURVEY, "referral_consent": False})
        self.assertNotIn("jordan@globex.test", without)
        self.assertIn("consent not granted", without)

    def test_no_tester_email_skips_thank_you(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESEND_API_KEY", None)
            out = send_test_drive_survey_emails(**{**_SURVEY, "tester_email": None})
        self.assertEqual(out["thank_you"], "skipped")
        self.assertEqual(out["notify"], "logged")


if __name__ == "__main__":
    unittest.main()
