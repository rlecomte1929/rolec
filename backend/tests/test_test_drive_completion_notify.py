"""AIQ-1547 — test-drive completion notifies the admin IN-APP, not via Resend.

Verifies the channel gate: default (unset) → in-app only, ZERO email; 'email' → email
only; 'both' → both. Also that the notification carries the /admin/test-drive deep link
and the thank-you mailto, and that referral PII is gated on consent.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import backend.app.services.test_drive_notifications as tdn

_ADMIN = "4e275218-b362-419e-9120-17e5f039a8da"


class TestTestDriveCompletionNotify(unittest.TestCase):
    def _run(self, channel=None, **kwargs):
        env = {}
        if channel is not None:
            env["RELOPASS_TEST_DRIVE_NOTIFY_CHANNEL"] = channel
        with patch.dict(os.environ, env, clear=False), \
                patch.object(tdn, "_resolve_admin_user_ids", return_value=[_ADMIN]), \
                patch.object(tdn, "_write_inapp", return_value=True) as write, \
                patch("backend.app.services.test_drive_emails.send_test_drive_survey_emails") as email:
            if channel is None:
                os.environ.pop("RELOPASS_TEST_DRIVE_NOTIFY_CHANNEL", None)
            call = dict(
                tester_name="Alex", tester_email="alex@example.test", corridor_id="FR_NO",
                campaign="qa", q1_overall=5, q3_problem_fit="yes", pilot_interest="maybe",
                referral_name="Ref", referral_contact="ref@x.test", referral_consent=True,
            )
            call.update(kwargs)
            out = tdn.notify_test_drive_completion(**call)
        return out, write, email

    def test_default_channel_is_inapp_and_sends_zero_email(self):
        out, write, email = self._run(channel=None)
        self.assertEqual(out["channel"], "inapp")   # unset defaults to inapp
        self.assertEqual(out["inapp"], 1)
        write.assert_called_once()                  # one in-app row for the admin
        email.assert_not_called()                   # ZERO Resend

    def test_notification_content(self):
        _out, write, _email = self._run(channel=None)
        _uid, title, _body, metadata = write.call_args.args
        self.assertIn("Test-drive completed", title)
        self.assertEqual(metadata["link"], "/admin/test-drive")
        self.assertTrue(metadata["thank_you_mailto"].startswith("mailto:alex@example.test"))

    def test_referral_pii_gated_on_consent(self):
        _out, write, _email = self._run(channel=None, referral_consent=False)
        _uid, _title, _body, metadata = write.call_args.args
        self.assertNotIn("referral_name", metadata)
        self.assertNotIn("referral_contact", metadata)

    def test_email_channel_sends_email_no_inapp(self):
        out, write, email = self._run(channel="email")
        self.assertEqual(out["channel"], "email")
        write.assert_not_called()
        email.assert_called_once()

    def test_both_channel_does_inapp_and_email(self):
        out, write, email = self._run(channel="both")
        self.assertEqual(out["channel"], "both")
        write.assert_called_once()
        email.assert_called_once()

    def test_unknown_channel_falls_back_to_inapp(self):
        out, _write, email = self._run(channel="carrier-pigeon")
        self.assertEqual(out["channel"], "inapp")
        email.assert_not_called()

    # ── multi-referral ────────────────────────────────────────────────────────
    # A tester can leave several intros. The notification used to name only referrals[0],
    # because it was fed the legacy mirrored scalars.

    def test_every_consented_referral_reaches_the_notification(self):
        _out, write, _email = self._run(channel=None, referrals=[
            {"name": "Marie", "company_role": "Head of Mobility", "contact": "marie@x.test",
             "consent": True},
            {"name": "Jan", "company_role": "HRBP", "contact": "jan@x.test", "consent": True},
        ])
        _uid, _title, _body, metadata = write.call_args.args
        self.assertEqual([r["name"] for r in metadata["referrals"]], ["Marie", "Jan"])
        self.assertEqual(metadata["referral_count"], 2)
        self.assertEqual(metadata["referral_consented_count"], 2)
        # The flat legacy keys still carry the first consented person for existing readers.
        self.assertEqual(metadata["referral_name"], "Marie")
        self.assertEqual(metadata["referral_contact"], "marie@x.test")

    def test_consent_is_per_person_not_per_survey(self):
        """The load-bearing case: an unconsented person must NOT ride along on a consented
        one, and a consented person must NOT be hidden behind an unconsented one."""
        _out, write, _email = self._run(channel=None, referrals=[
            {"name": "NoConsent", "contact": "no@x.test", "consent": False},
            {"name": "YesConsent", "contact": "yes@x.test", "consent": True},
        ])
        _uid, _title, _body, metadata = write.call_args.args
        names = [r["name"] for r in metadata["referrals"]]
        self.assertEqual(names, ["YesConsent"])
        self.assertNotIn("no@x.test", str(metadata))
        # Counts stay honest about the person who was withheld — they name nobody.
        self.assertEqual(metadata["referral_count"], 2)
        self.assertEqual(metadata["referral_consented_count"], 1)
        # Legacy keys follow the first CONSENTED person, not merely the first.
        self.assertEqual(metadata["referral_name"], "YesConsent")

    def test_all_unconsented_withholds_every_name(self):
        _out, write, _email = self._run(channel=None, referrals=[
            {"name": "A", "contact": "a@x.test", "consent": False},
            {"name": "B", "contact": "b@x.test", "consent": False},
        ])
        _uid, _title, _body, metadata = write.call_args.args
        self.assertNotIn("referrals", metadata)
        self.assertNotIn("referral_name", metadata)
        self.assertFalse(metadata["referral_consent"])
        self.assertEqual(metadata["referral_count"], 2)
        self.assertEqual(metadata["referral_consented_count"], 0)

    def test_legacy_scalars_only_still_work(self):
        """An old caller passing no `referrals` list is wrapped into a 1-element list."""
        _out, write, _email = self._run(channel=None)  # base call has the legacy scalars
        _uid, _title, _body, metadata = write.call_args.args
        self.assertEqual([r["name"] for r in metadata["referrals"]], ["Ref"])
        self.assertEqual(metadata["referral_name"], "Ref")
        self.assertEqual(metadata["referral_count"], 1)


if __name__ == "__main__":
    unittest.main()
