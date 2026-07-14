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


if __name__ == "__main__":
    unittest.main()
