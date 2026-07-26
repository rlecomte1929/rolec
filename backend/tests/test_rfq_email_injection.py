"""AIQ-1521 — the RFQ email must not be an injection vector.

This HTML is sent FROM our own domain TO an external company we are trying to win over, and it
now carries EMPLOYEE free text (special_items, property_size, notes) as well as a supplier name
from a partly crowd-sourced, partly LLM-scraped catalog.

Unescaped, a user could inject markup — including an <a href> — into mail that appears to come
from us. That is a phishing vector, not a rendering bug.
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.supplier_link_dispatch import (  # noqa: E402
    NO_ADDRESS,
    _PERSONAL_DOMAINS,
    dispatch_supplier_links,
    rfq_email_html,
    rfq_email_subject,
)

LINK = "https://relopass.com/supplier/quote?token=abc"


class EmailInjectionTests(unittest.TestCase):
    def test_employee_free_text_cannot_inject_markup_into_the_outbound_email(self):
        html = rfq_email_html(
            "Evil<script>alert(1)</script>Movers",
            LINK,
            [
                {"label": "Special items", "value": '<a href="https://phish.example">Verify your account</a>'},
                {"label": "Anything else", "value": '"><img src=x onerror=alert(1)>'},
            ],
            "2026-07-21",
        )
        # The payloads must arrive as TEXT, never as live markup. Note "onerror=" DOES survive as
        # characters inside "&lt;img … &gt;" — that is correct, it is inert. What must never
        # survive is an unescaped tag opener.
        self.assertNotIn("<script>", html)
        self.assertNotIn('<a href="https://phish.example"', html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertIn("phish.example", html)  # shown to the vendor, but not clickable

        # The ONLY live link in the mail must be ours.
        self.assertEqual(html.count("<a href="), 1)
        self.assertIn(f'href="{LINK}"', html)

    def test_the_brief_and_the_deadline_actually_reach_the_vendor(self):
        html = rfq_email_html(
            "Allied",
            LINK,
            [{"label": "Move from", "value": "Paris, FR"}, {"label": "Move to", "value": "Oslo, NO"}],
            "2026-07-21",
        )
        self.assertIn("Paris, FR", html)
        self.assertIn("Oslo, NO", html)
        self.assertIn("2026-07-21", html)
        self.assertIn("itemised", html.lower())  # we say what a good answer looks like

    def test_the_subject_carries_the_route_so_a_vendor_can_triage_it(self):
        subject = rfq_email_subject([
            {"label": "Move from", "value": "Paris, FR"},
            {"label": "Move to", "value": "Oslo, NO"},
        ])
        self.assertEqual(subject, "Quote request: household move, Paris, FR → Oslo, NO")
        self.assertNotIn("\n", subject)  # no header injection

    def test_the_subject_degrades_honestly_when_the_route_is_unknown(self):
        subject = rfq_email_subject([{"label": "Move from", "value": "Not specified"}])
        self.assertEqual(subject, "A relocation company would like a quote from you")

    def test_an_email_with_no_brief_still_renders(self):
        # Legacy / non-movers RFQs have no structured brief. The mail must not break.
        html = rfq_email_html("Allied", LINK)
        self.assertIn("<a href=", html)
        self.assertNotIn("None", html)


class PersonalDomainGuardTests(unittest.TestCase):
    """AIQ-1533 — personal/webmail domains in the catalog must never receive RFQ emails."""

    def setUp(self):
        # These assert EMAIL-mode address guards; opt into email egress so the go-live gate
        # (RELOPASS_SUPPLIER_EMAIL_LIVE) doesn't force inbox and skip the guards under test.
        from unittest.mock import patch as _patch
        p = _patch.dict(os.environ, {"RELOPASS_SUPPLIER_EMAIL_LIVE": "true"})
        p.start()
        self.addCleanup(p.stop)

    def _targets(self, email):
        return [{"recipient_id": "r-1", "vendor_id": "v-1", "supplier_name": "Test Mover", "email": email}]

    def test_personal_domain_blocked_not_sent(self):
        # dispatch_supplier_links must not email a personal inbox even with send_email=True.
        # (No real email actually goes out here — RESEND_API_KEY is unset in tests.)
        results = dispatch_supplier_links(
            rfq_id="rfq-test-1",
            targets=self._targets("someone@hotmail.com"),
            dispatch_mode="email",
            send_email=True,
        )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["ok"])
        self.assertFalse(results[0]["sent"])
        self.assertIn("hotmail.com", results[0]["error"])

    def test_no_address_still_blocked(self):
        results = dispatch_supplier_links(
            rfq_id="rfq-test-2",
            targets=self._targets(None),
            dispatch_mode="email",
            send_email=False,
        )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["error"], NO_ADDRESS)

    def test_business_domain_passes_the_guard(self):
        # A real business address should NOT be blocked by the personal-domain guard.
        # It will mint a token (which needs a DB), so we only check it's NOT rejected
        # for the domain reason — the token-mint may fail in the test environment.
        results = dispatch_supplier_links(
            rfq_id="rfq-test-3",
            targets=self._targets("rfq@asiantigers-worldwide.com"),
            dispatch_mode="email",
            send_email=False,
        )
        self.assertEqual(len(results), 1)
        # Must not be rejected due to domain; any failure should be from token-mint, not domain
        if not results[0]["ok"]:
            self.assertNotIn("placeholder email", results[0].get("error", ""))

    def test_personal_domains_blocklist_includes_hotmail(self):
        self.assertIn("hotmail.com", _PERSONAL_DOMAINS)
        self.assertIn("gmail.com", _PERSONAL_DOMAINS)

    def test_gmail_domain_blocked(self):
        results = dispatch_supplier_links(
            rfq_id="rfq-test-4",
            targets=self._targets("contact@gmail.com"),
            dispatch_mode="email",
            send_email=True,
        )
        self.assertFalse(results[0]["ok"])
        self.assertIn("gmail.com", results[0]["error"])


if __name__ == "__main__":
    unittest.main()
