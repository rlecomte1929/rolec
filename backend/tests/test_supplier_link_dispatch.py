"""AIQ-1521 — dispatching a supplier magic link.

This is the code that decides whether an email leaves the building. The properties worth pinning
are the ones that stop us mailing a company we have no business mailing, and the ones that stop
us silently dropping a supplier the employee deliberately chose:

  * no address on record -> NOT contacted, NO token minted, and the employee is told (EMAIL mode)
  * send_email=False     -> the link is minted but nothing is sent
  * an address is never invented; it comes from suppliers.contact_email or an explicit override
  * a Resend failure never loses the minted link (the RFQ survives a mail outage)

The default dispatch_mode is now "inbox" (mints for everyone, no email, surfaces the link in-app);
the address/verified guards below are EMAIL-mode semantics, so these tests pass dispatch_mode="email"
explicitly. Inbox mode is pinned separately in InboxDispatchTests.

The end-to-end chain (create RFQ -> open link with no account -> submit a quote) is verified
against real Postgres in prod, not here: this suite runs on a mocked db, which would happily "pass"
against a schema that does not exist. See the AIQ-1523 uuid/text bug for what that class of false
green costs.
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


def _target(email=None, name="Santa Fe Relocation", verified=True):
    # verified defaults True: these tests exercise the happy path of a *verified* catalog address.
    # The verified-gate itself is pinned separately in test_an_unverified_address_is_not_dispatched.
    return {
        "recipient_id": "rec-1",
        "vendor_id": "sup-1",
        "supplier_name": name,
        "email": email,
        "verified": verified,
    }


class DispatchTests(unittest.TestCase):
    """EMAIL-mode dispatch. `dispatch_mode="email"` is passed explicitly: the default is now
    "inbox" (see InboxDispatchTests), and these address/provenance guards are email-mode semantics.
    Email egress is also gated behind RELOPASS_SUPPLIER_EMAIL_LIVE (see SupplierEmailGoLiveGateTests);
    these tests opt in so they exercise the email path.
    """

    def setUp(self):
        # Opt into email egress — the go-live gate forces inbox when this is unset.
        live = patch.dict(os.environ, {"RELOPASS_SUPPLIER_EMAIL_LIVE": "true"})
        live.start()
        self.addCleanup(live.stop)
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
                rfq_id="rfq-1", targets=[_target(email=None)],
                dispatch_mode="email", send_email=True,
            )

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["error"], sld.NO_ADDRESS)
        self.assertFalse(results[0]["sent"])
        post.assert_not_called()          # nothing left the building
        self.engine.begin.assert_not_called()  # and no token was minted for them

    def test_an_unverified_address_is_not_dispatched(self):
        """AIQ-1533: a catalog address with verified=False is an honest gap, not a send target.
        No token is minted and nothing goes out — the employee's move details never reach an
        address whose provenance we have not confirmed."""
        with patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1",
                targets=[_target(email="ops@santafe.example", verified=False)],
                dispatch_mode="email", send_email=True,
            )

        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["error"], sld.UNVERIFIED_ADDRESS)
        self.assertFalse(results[0]["sent"])
        post.assert_not_called()               # nothing left the building
        self.engine.begin.assert_not_called()  # and no token was minted

    def test_send_email_false_mints_a_link_but_sends_nothing(self):
        """Minting is harmless; emailing a real company is not. They are separate decisions."""
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=False,
            )

        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[0]["sent"])
        self.assertIn("/supplier/quote?token=", results[0]["link"])
        post.assert_not_called()

    def test_the_minted_token_is_scoped_to_this_rfq_and_this_supplier(self):
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)):
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True,
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
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True,
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
                dispatch_mode="email", send_email=True,
            )

        self.assertEqual([r["sent"] for r in results], [True, False, True])
        self.assertEqual(results[1]["error"], sld.NO_ADDRESS)

    def test_no_resend_key_sends_nothing_and_says_so(self):
        env = {k: v for k, v in os.environ.items() if k != "RESEND_API_KEY"}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True,
            )

        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[0]["sent"])
        self.assertIn("RESEND_API_KEY", results[0]["error"])
        post.assert_not_called()


class InboxDispatchTests(unittest.TestCase):
    """INBOX-mode dispatch (the default). The load-bearing property: it mints a working link for
    EVERY recipient — including the addressless, unverified catalog rows that make up most of the
    supplier list — and makes ZERO Resend calls. That is what makes token_hash reachable for all
    recipients while the email quota is never touched.
    """

    def setUp(self):
        self.engine = MagicMock()
        patcher = patch.object(sld, "db", MagicMock(engine=self.engine))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_inbox_mode_mints_for_an_addressless_unverified_supplier_and_sends_nothing(self):
        # The exact prod fixture: a school/mover with contact_email=NULL and verified=False. In
        # EMAIL mode this is NO_ADDRESS and no token; in INBOX mode it must mint and surface a link.
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1",
                targets=[_target(email=None, verified=False)],
                dispatch_mode="inbox",
            )

        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[0]["sent"])            # nothing emailed
        self.assertEqual(results[0]["mode"], "inbox")
        self.assertTrue(results[0]["queued_inbox"])
        self.assertIn("/supplier/quote?token=", results[0]["link"])
        post.assert_not_called()                        # ZERO Resend calls in inbox mode
        self.engine.begin.assert_called()               # a token WAS minted

    def test_inbox_mode_is_the_default(self):
        # No dispatch_mode passed -> inbox. An addressless supplier still mints (would be NO_ADDRESS
        # under email mode), proving the default is inbox.
        with patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email=None)],
            )
        self.assertEqual(results[0]["mode"], "inbox")
        self.assertTrue(results[0]["ok"])
        post.assert_not_called()

    def test_inbox_mode_never_emails_even_a_verified_business_address(self):
        # A real, verified, business address is exactly who we must NOT email in inbox mode.
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1",
                targets=[_target(email="ops@santafe.example", verified=True)],
                dispatch_mode="inbox", send_email=True,   # send_email ignored in inbox mode
            )
        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[0]["sent"])
        post.assert_not_called()

    def test_inbox_minted_token_is_valid_and_scoped(self):
        with patch.object(sld.requests, "post"):
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-9", targets=[_target(email=None)], dispatch_mode="inbox",
            )
        token = results[0]["link"].split("token=", 1)[1]
        claims = verify_supplier_token(token)
        self.assertEqual(claims["rfq_id"], "rfq-9")
        self.assertEqual(claims["app_role"], "supplier")

    def test_a_broken_inbox_message_never_loses_the_minted_link(self):
        # If posting the inbox message blows up, the token still stands (best-effort surfacing).
        with patch.object(sld, "_post_inbox_message", side_effect=RuntimeError("inbox down")), \
                patch.object(sld.requests, "post") as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email=None)], dispatch_mode="inbox",
            )
        self.assertTrue(results[0]["ok"])
        self.assertIn("/supplier/quote?token=", results[0]["link"])
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


class TestPersonaSenderGuardTests(unittest.TestCase):
    """Guard 3: a test persona (the SENDER) can never trigger a real email, even with the flag on
    and RESEND_API_KEY set. Email mode only — inbox mode emails no one. This is the hard safeguard
    that lets QA run RFQ flows against the real, now partly-contactable catalog with zero risk of a
    test user mailing a real mover."""

    def setUp(self):
        # Opt into email egress — the go-live gate forces inbox when this is unset.
        live = patch.dict(os.environ, {"RELOPASS_SUPPLIER_EMAIL_LIVE": "true"})
        live.start()
        self.addCleanup(live.stop)
        self.engine = MagicMock()
        patcher = patch.object(sld, "db", MagicMock(engine=self.engine))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_test_persona_sender_never_emails_even_with_key_and_send_email(self):
        # Exactly the scenario where a real send WOULD fire (verified business address, key set,
        # requests.post would return 200) — but the sender is a test persona.
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)) as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1",
                targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True,
                actor_email="e2e-employee@probe.test",
            )

        post.assert_not_called()                 # nothing left the building
        self.assertFalse(results[0]["sent"])
        self.assertIn("suppressed", results[0]["error"])
        self.assertTrue(results[0]["ok"])        # the token was still minted (virtual flow works)
        self.assertIn("/supplier/quote?token=", results[0]["link"])

    def test_testco_domain_sender_is_also_blocked(self):
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)) as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True, actor_email="hr@testco.com",
            )
        post.assert_not_called()
        self.assertFalse(results[0]["sent"])

    def test_a_real_sender_still_emails(self):
        # The guard must NOT break a legitimate send: a non-test actor still emails.
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)) as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True, actor_email="real.hr@acme-corp.com",
            )
        post.assert_called_once()
        self.assertTrue(results[0]["sent"])

    def test_unknown_actor_is_treated_as_non_test(self):
        # No actor_email passed → fail-open on identity (the flag + address guards still gate).
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)) as post:
            results = sld.dispatch_supplier_links(
                rfq_id="rfq-1", targets=[_target(email="ops@santafe.example")],
                dispatch_mode="email", send_email=True,
            )
        post.assert_called_once()
        self.assertTrue(results[0]["sent"])


class SupplierEmailGoLiveGateTests(unittest.TestCase):
    """Hard go-live gate: NO supplier is emailed until RELOPASS_SUPPLIER_EMAIL_LIVE=true, even on
    the fully-armed email path (dispatch_mode='email', send_email=True, RESEND_API_KEY set, a REAL
    (non-test) actor, a verified business address). Independent of SUPPLIER_RFQ_DISPATCH_ENABLED and
    the HR 'Email suppliers' action — this is the choke point they all pass through."""

    def setUp(self):
        self.engine = MagicMock()
        patcher = patch.object(sld, "db", MagicMock(engine=self.engine))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _armed(self):
        # The exact conditions under which an email WOULD fire if the gate were off.
        return dict(
            rfq_id="rfq-golive",
            targets=[_target(email="ops@acme-corp.com", verified=True)],
            dispatch_mode="email",
            send_email=True,
            actor_email="real.hr@acme-corp.com",  # a real (non-test) sender
        )

    def test_gate_off_forces_inbox_no_email_even_fully_armed(self):
        env = {k: v for k, v in os.environ.items() if k != "RELOPASS_SUPPLIER_EMAIL_LIVE"}
        with patch.dict(os.environ, {**env, "RESEND_API_KEY": "re_test"}, clear=True), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)) as post:
            results = sld.dispatch_supplier_links(**self._armed())

        post.assert_not_called()                 # NO supplier email left the building
        self.assertFalse(results[0]["sent"])
        self.assertEqual(results[0]["mode"], "inbox")   # forced to inbox
        self.assertTrue(results[0]["ok"])        # token still minted (loop still runs)
        self.assertIn("/supplier/quote?token=", results[0]["link"])

    def test_gate_on_allows_email(self):
        with patch.dict(os.environ, {"RESEND_API_KEY": "re_test", "RELOPASS_SUPPLIER_EMAIL_LIVE": "true"}), \
                patch.object(sld.requests, "post", return_value=MagicMock(status_code=200)) as post:
            results = sld.dispatch_supplier_links(**self._armed())

        post.assert_called_once()                # go-live on → the email path runs
        self.assertTrue(results[0]["sent"])
        self.assertEqual(results[0]["mode"], "email")


if __name__ == "__main__":
    unittest.main()
