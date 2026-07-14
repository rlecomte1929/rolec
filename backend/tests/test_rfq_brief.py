"""AIQ-1521 follow-up — the brief a vendor actually receives.

Before this, a vendor got the word "movers" plus whatever free text the employee happened to
type — and `{}` if they typed nothing. The platform already knew the route and the date and sent
neither.

That is not just a lost quote. The whole point of the spike is to learn whether a real supplier
answers. Send them "someone is moving, click here", get silence, and we would conclude
"suppliers don't respond" when the truth is "we asked badly" — a FALSE VERDICT on the model.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.rfq_brief import (  # noqa: E402
    NOT_SPECIFIED,
    RESPONSE_EXPECTATIONS,
    build_movers_requirements,
    render_brief_lines,
    respond_by,
)

CASE = {
    "home_city": "Paris",
    "home_country": "FR",
    "host_city": "Oslo",
    "host_country": "NO",
    "target_start_date": date(2026, 9, 15),
}


class BuildTests(unittest.TestCase):
    def test_the_route_and_date_come_from_the_CASE_not_the_employee(self):
        # The employee is never asked to retype what we already hold — and the client is never
        # trusted for it either.
        req = build_movers_requirements(CASE, {})
        self.assertEqual(req["route"]["from_city"], "Paris")
        self.assertEqual(req["route"]["to_city"], "Oslo")
        self.assertEqual(req["route"]["to_country"], "NO")
        self.assertEqual(req["target_date"], "2026-09-15")

    def test_the_employee_supplies_only_what_we_cannot_know(self):
        req = build_movers_requirements(CASE, {
            "property_size": "2-bedroom flat",
            "floor": "3rd",
            "lift": False,
            "storage_needed": True,
            "special_items": "piano",
            "notes": "flexible on the exact day",
        })
        self.assertEqual(req["property"]["size"], "2-bedroom flat")
        self.assertIs(req["property"]["lift"], False)
        self.assertIs(req["storage_needed"], True)
        self.assertEqual(req["special_items"], "piano")

    def test_a_missing_case_does_not_explode_it_degrades(self):
        req = build_movers_requirements(None, None)
        self.assertIsNone(req["target_date"])
        self.assertIsNone(req["route"]["from_city"])


class RenderTests(unittest.TestCase):
    def _rows(self, req):
        return {r["label"]: r["value"] for r in render_brief_lines(req)}

    def test_a_full_brief_reads_like_something_a_mover_can_price(self):
        rows = self._rows(build_movers_requirements(CASE, {
            "property_size": "2-bedroom flat", "floor": "3rd", "lift": False,
            "storage_needed": False, "special_items": "piano",
        }))
        self.assertEqual(rows["Move from"], "Paris, FR")
        self.assertEqual(rows["Move to"], "Oslo, NO")
        self.assertEqual(rows["Target move date"], "2026-09-15")
        self.assertEqual(rows["Property"], "2-bedroom flat, floor 3rd, no lift")
        self.assertEqual(rows["Storage needed"], "No")
        self.assertEqual(rows["Special items"], "piano")

    def test_UNKNOWNS_ARE_SHOWN_not_dropped_and_never_guessed(self):
        # A vendor must see what we did NOT tell them, so they can ask. Silently omitting the
        # floor invites them to guess — and a wrong guess is a wrong price.
        rows = self._rows(build_movers_requirements({"home_city": "Paris", "home_country": "FR"}, {}))
        self.assertEqual(rows["Target move date"], NOT_SPECIFIED)
        self.assertEqual(rows["Property"], NOT_SPECIFIED)
        self.assertEqual(rows["Storage needed"], NOT_SPECIFIED)
        self.assertEqual(rows["Move to"], NOT_SPECIFIED)

    def test_storage_false_is_NOT_treated_as_unknown(self):
        # "No storage" is an answer. Only None is unknown.
        rows = self._rows(build_movers_requirements(CASE, {"storage_needed": False}))
        self.assertEqual(rows["Storage needed"], "No")

    def test_a_legacy_free_text_requirements_blob_still_renders(self):
        # Old RFQs stored {"notes": "..."} with no schema. They must not blow up the page.
        rows = self._rows({"notes": "2-bed flat, Paris to Oslo"})
        self.assertEqual(rows["Details"], "2-bed flat, Paris to Oslo")

    def test_an_empty_legacy_blob_says_so_rather_than_rendering_nothing(self):
        self.assertEqual(self._rows({})["Details"], NOT_SPECIFIED)


class ExpectationTests(unittest.TestCase):
    def test_the_vendor_is_told_what_a_good_answer_looks_like(self):
        joined = " ".join(RESPONSE_EXPECTATIONS).lower()
        self.assertIn("confirm", joined)     # scope / route
        self.assertIn("itemised", joined)    # a breakdown, not a lump sum
        self.assertIn("valid", joined)       # how long the price holds

    def test_the_deadline_is_a_real_date_not_soon(self):
        self.assertRegex(respond_by(), r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
