"""AIQ-1521 — dispatching a supplier magic link.

This is the code that decides whether an email leaves the building. The properties worth pinning
are the ones that stop us mailing a company we have no business mailing, and the ones that stop
us silently dropping a supplier the employee deliberately chose:

  * no address on record -> NOT contacted, NO token minted, and the employee is told
  * send_email=False     -> the link is minted but nothing is sent
  * an address is never invented; it comes from suppliers.contact_email or an explicit override
  * a Resend failure never loses the minted link (the RFQ survives a mail outage)

The end-to-end chain (create RFQ -> email -> open link with no account -> submit a quote) is
verified against real Postgres in prod, not here: this suite runs on a mocked db, which would
happily "pass" against a schema that does not exist. See the AIQ-1523 uuid/text bug for what
that class of false green costs.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-for-supplier-jwt")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import supplier_link_dispatch as sld  # noqa: E402
from backend.app.services.supplier_jwt import verify_supplier_token  # noqa: E402


def _target(email=None, name="Santa Fe Relocation"):
    return {
        "recipient_id": "rec-1",
        "vendor_id": "sup-1",
        "supplier_name": name,
        "email": email,
    }


class DispatchTests(unittest.TestCase):
    def setUp(self):
        # db.engine.begin() is a context manager yielding a connection we only ever .execute() on.
        self.engine = MagicMock()
        patcher = patch.object(sld, "db", MagicMock(engine=self.engine))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_address_on_record_is_reported_not_guessed(self):
        """The default state of the catalog: 90 suppliers, no contact_email. That must never
        become a send to some invented address, and must never be a silent drop either."""
        with patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email=None)], send_email=True
            )

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["error"], sld.NO_ADDRESS)
        self.assertFalse(results[0]["sent"])
        post.assert_not_called()          # nothing left the building
        self.engine.begin.assert_not_called()  # and no token was minted for them

    def test_send_email_false_mints_a_link_but_sends_nothing(self):
        """Minting is harmless; emailing a real company is not. They are separate decisions."""
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")], send_email=False
            )

        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[0]["sent"])
        self.assertIn("/supplier/quote?token=", results[0]["link"])
        post.assert_not_called()

    def test_the_minted_token_is_scoped_to_this_rfq_and_this_supplier(self):
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)):
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")], send_email=True
            )

        token = results[0]["link"].split("token=", 1)[1]
        claims = verify_supplier_token(token)
        self.assertEqual(claims["rfq_id"], "rfq-1")
        self.assertEqual(claims["vendor_id"], "sup-1")
        self.assertEqual(claims["recipient_id"], "rec-1")
        self.assertEqual(claims["app_role"], "supplier")
        self.assertTrue(results[0]["sent"])

    def test_a_resend_failure_never_loses_the_minted_link(self):
        """A mail outage must not cost the employee their RFQ — the link still exists and can be
        re-sent or handed over by hand."""
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", side_effect=RuntimeError("resend is down")):
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")], send_email=True
            )

        self.assertTrue(results[0]["ok"])       # the link was minted
        self.assertFalse(results[0]["sent"])    # it just did not go out
        self.assertIn("resend is down", results[0]["error"])
        self.assertIn("/supplier/quote?token=", results[0]["link"])

    def test_one_bad_supplier_does_not_stop_the_others(self):
        """The employee shortlisted three movers. One having no address must not cost them the
        other two — that is the AIQ-1520 lesson, applied to dispatch."""
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)):
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1",
                targets=[
                    {**_target(email="a@x.example", name="Asian Tigers"), "recipient_id": "rec-a"},
                    {**_target(email=None, name="Santa Fe"), "recipient_id": "rec-b"},
                    {**_target(email="c@x.example", name="Transworld"), "recipient_id": "rec-c"},
                ],
                send_email=True,
            )

        self.assertEqual([r["sent"] for r in results], [True, False, True])
        self.assertEqual(results[1]["error"], sld.NO_ADDRESS)

    def test_no_resend_key_sends_nothing_and_says_so(self):
        env = {k: v for k, v in os.environ.items() if k != "RESEND_API_KEY"}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")], send_email=True
            )

        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[0]["sent"])
        self.assertIn("RESEND_API_KEY", results[0]["error"])
        post.assert_not_called()


class EmailBodyTests(unittest.TestCase):
    def test_the_email_says_no_account_is_needed(self):
        """The single assumption this whole spike tests: a supplier will answer without signing
        up. If the email fails to say so, we are not testing the thing we think we are."""
        html = sld.rfq_email_html("Santa Fe", "https://relopass.com/supplier/quote?token=abc")
        self.assertIn("no account to create", html)
        self.assertIn("https://relopass.com/supplier/quote?token=abc", html)
        self.assertIn("Santa Fe", html)
        self.assertIn("#1f8e8b", html)  # DESIGN.md accent, not a stray colour

    def test_a_supplier_name_cannot_inject_markup_into_the_email(self):
        """suppliers.name is not trusted input — the catalog is part crowd-sourced (HR
        vendor-curation) and part LLM-scraped, so a name can carry markup."""
        html = sld.rfq_email_html(
            '<script>alert(1)</script>', "https://relopass.com/supplier/quote?token=abc"
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
