"""
Tests for the transactional assignment invite email (sent when HR assigns a case).

Pure unittest — no network. Resend is mocked; the dev/no-key path and the
never-raises contract are explicitly asserted (assignment must not roll back on
an email failure).
"""
from __future__ import annotations

import unittest
from unittest import mock

from backend.app.services import assignment_invite_email as m


class TestRender(unittest.TestCase):
    def _render(self, **over):
        kw = dict(
            to_email="lucas@testco.com",
            employee_name="Lucas Petit",
            hr_name="Sophie Martin",
            company_name="TechCorp International",
            invite_token="abc-123-token",
            account_exists=False,
        )
        kw.update(over)
        return m.render_assignment_invite_email(**kw)

    def test_subject_uses_company_name(self):
        subject, _, _ = self._render()
        self.assertEqual(subject, "Your relocation with TechCorp International has started")

    def test_body_avoids_system_noun_and_sets_expectations(self):
        # [TASK-026] employee-facing copy: drop the "case" system noun and say
        # what to expect, in both the new-account and existing-account variants.
        for account_exists in (False, True):
            _, plain, html = self._render(account_exists=account_exists)
            self.assertNotIn("relocation case", plain)
            self.assertIn("set up", plain)
            self.assertIn("plan, documents, and next steps", plain)
            self.assertIn("plan, documents, and next steps", html)

    def test_register_link_for_new_account(self):
        _, plain, html = self._render(account_exists=False)
        self.assertIn("mode=register", plain)
        self.assertIn("email=lucas%40testco.com", plain)  # email pre-fill, url-encoded
        self.assertIn("mode=register", html)

    def test_login_link_for_existing_account(self):
        _, plain, _ = self._render(account_exists=True)
        self.assertIn("mode=login", plain)
        self.assertNotIn("mode=register", plain)

    def test_includes_name_and_case_code(self):
        _, plain, _ = self._render()
        self.assertIn("Lucas Petit", plain)
        self.assertIn("abc-123-token", plain)  # fallback case code present

    def test_no_code_block_when_token_missing(self):
        _, plain, _ = self._render(invite_token=None)
        self.assertNotIn("case code", plain.lower())

    def test_falls_back_to_email_local_part_when_no_name(self):
        _, plain, _ = self._render(employee_name=None)
        self.assertIn("Hi lucas,", plain)


class TestSend(unittest.TestCase):
    def test_skips_when_no_email(self):
        self.assertEqual(m.send_assignment_invite_email(to_email="")["status"], "skipped")
        self.assertEqual(m.send_assignment_invite_email(to_email="not-an-email")["status"], "skipped")

    def test_dev_fallback_logs_when_no_key(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("RESEND_API_KEY", None)
            res = m.send_assignment_invite_email(
                to_email="lucas@testco.com", company_name="TechCorp", invite_token="t1"
            )
        self.assertEqual(res["status"], "logged")
        self.assertEqual(res["mode"], "register")

    def test_sent_on_resend_ok(self):
        fake_resp = mock.MagicMock(ok=True, status_code=200)
        with mock.patch.dict("os.environ", {"RESEND_API_KEY": "re_test"}, clear=False), \
             mock.patch.object(m.http_requests, "post", return_value=fake_resp) as post:
            res = m.send_assignment_invite_email(to_email="lucas@testco.com", account_exists=True)
        self.assertEqual(res["status"], "sent")
        self.assertEqual(res["mode"], "login")
        post.assert_called_once()

    def test_failed_on_resend_non_2xx(self):
        fake_resp = mock.MagicMock(ok=False, status_code=422, text="bad")
        with mock.patch.dict("os.environ", {"RESEND_API_KEY": "re_test"}, clear=False), \
             mock.patch.object(m.http_requests, "post", return_value=fake_resp):
            res = m.send_assignment_invite_email(to_email="lucas@testco.com")
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["http_status"], 422)

    def test_never_raises_on_exception(self):
        with mock.patch.dict("os.environ", {"RESEND_API_KEY": "re_test"}, clear=False), \
             mock.patch.object(m.http_requests, "post", side_effect=RuntimeError("network down")):
            res = m.send_assignment_invite_email(to_email="lucas@testco.com")
        self.assertEqual(res["status"], "error")  # suppressed, not raised


class TestSmokeTest(unittest.TestCase):
    """The admin smoke test uses the same Resend path as the HR invite."""

    def test_skips_when_no_email(self):
        self.assertEqual(m.send_smoke_test_email("")["status"], "skipped")

    def test_no_key_reports_no_key(self):
        import os
        with mock.patch.dict("os.environ", {}, clear=False):
            os.environ.pop("RESEND_API_KEY", None)
            res = m.send_smoke_test_email("admin@relopass.com")
        self.assertEqual(res["status"], "no_key")

    def test_sent_via_same_resend_endpoint(self):
        fake_resp = mock.MagicMock(ok=True, status_code=200)
        with mock.patch.dict("os.environ", {"RESEND_API_KEY": "re_test"}, clear=False), \
             mock.patch.object(m.http_requests, "post", return_value=fake_resp) as post:
            res = m.send_smoke_test_email("admin@relopass.com")
        self.assertEqual(res["status"], "sent")
        self.assertEqual(post.call_args.args[0], "https://api.resend.com/emails")

    def test_never_raises(self):
        with mock.patch.dict("os.environ", {"RESEND_API_KEY": "re_test"}, clear=False), \
             mock.patch.object(m.http_requests, "post", side_effect=RuntimeError("down")):
            res = m.send_smoke_test_email("admin@relopass.com")
        self.assertEqual(res["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
