"""
[AIQ-1883 / T18-09] Advisor matching returned confidently-wrong referrals for Ireland,
with unactionable contact URLs.

Verified in prod 2026-08-13: POST /api/advisors/match {origin ES, destination IE}
returned Lars Vantine, "EU Free Movement Specialist", specialisms
["EU Blue Card", "schengen long-stay", "digital nomad visas"] — three instruments
Ireland does not operate. It is outside the Blue Card Directive (European
Commission: it "does not apply in Denmark and Ireland") and outside Schengen.

He matched for two independent reasons, both working as coded:
  * `_advisor_matches_corridor` ORed in `origin_upper in corridors`, and his list
    contains ES though not IE — covering the ORIGIN is not a qualification to
    advise on the DESTINATION, which the function's own docstring already said;
  * IE maps to the "EU" region and his list contains "EU".

The second is legitimate corridor logic, so the fix cannot be corridor-only: the
destination's actual instrument set has to matter. Ireland is in the EU region and
is still a genuine exception.

Separately every seeded contact_url was on example.com — RFC 2606 documentation
space, which resolves to nothing — so even a correct match was unactionable.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import advisors as mod  # noqa: E402


def _seed():
    for value in vars(mod).values():
        if (isinstance(value, list) and value and isinstance(value[0], dict)
                and "specialisms" in value[0]):
            return value
    raise AssertionError("advisor seed not found")


def _by_name(name):
    for a in _seed():
        if a["name"] == name:
            return a
    raise AssertionError(f"{name} not in seed")


class IrelandCapabilityTests(unittest.TestCase):
    def test_blue_card_and_schengen_specialist_is_not_matched_to_ireland(self) -> None:
        """THE reported bug. All three of his specialisms are unavailable in Ireland."""
        self.assertFalse(
            mod._advisor_matches_corridor(_by_name("Lars Vantine"), "IE", "ES")
        )

    def test_the_same_advisor_is_still_matched_to_germany(self) -> None:
        """The control that proves this is destination-specific rather than a blanket
        exclusion: Germany DOES operate the Blue Card and IS in Schengen."""
        self.assertTrue(
            mod._advisor_matches_corridor(_by_name("Lars Vantine"), "DE", "ES")
        )

    def test_a_generalist_still_matches_ireland(self) -> None:
        """Ireland issues employment permits and has family reunification, so an
        advisor offering those is a real match. Fixing this must not empty the list
        of everyone."""
        self.assertTrue(
            mod._advisor_matches_corridor(_by_name("Helena Morrow"), "IE", "ES")
        )

    def test_exactly_one_advisor_matches_es_to_ie(self) -> None:
        matched = [a["name"] for a in _seed()
                   if mod._advisor_matches_corridor(a, "IE", "ES")]
        self.assertEqual(matched, ["Helena Morrow"])


class OriginIsNotAQualificationTests(unittest.TestCase):
    def test_covering_the_origin_alone_does_not_match(self) -> None:
        """An advisor whose corridors contain the origin but not the destination,
        and whose region does not cover it either, must not match."""
        advisor = {"name": "Origin Only", "corridors": ["ES"], "specialisms": ["x"]}
        self.assertFalse(mod._advisor_matches_corridor(advisor, "JP", "ES"))

    def test_destination_coverage_still_matches(self) -> None:
        advisor = {"name": "Dest", "corridors": ["JP"], "specialisms": ["x"]}
        self.assertTrue(mod._advisor_matches_corridor(advisor, "JP", "ES"))

    def test_global_coverage_still_matches(self) -> None:
        advisor = {"name": "Global", "corridors": [], "specialisms": ["x"]}
        self.assertTrue(mod._advisor_matches_corridor(advisor, "JP", "ES"))


class UsableSpecialismTests(unittest.TestCase):
    """Conservative by design — one applicable specialism keeps an advisor in."""

    def test_one_applicable_specialism_is_enough(self) -> None:
        advisor = {"specialisms": ["EU Blue Card", "Irish employment permits"]}
        self.assertTrue(mod._advisor_offers_something_usable(advisor, "IE"))

    def test_all_inapplicable_disqualifies(self) -> None:
        advisor = {"specialisms": ["EU Blue Card", "schengen long-stay"]}
        self.assertFalse(mod._advisor_offers_something_usable(advisor, "IE"))

    def test_no_specialisms_is_not_disqualifying(self) -> None:
        self.assertTrue(mod._advisor_offers_something_usable({"specialisms": []}, "IE"))

    def test_destinations_without_exceptions_are_unaffected(self) -> None:
        advisor = {"specialisms": ["EU Blue Card", "schengen long-stay"]}
        for dest in ("DE", "FR", "NL", "ES"):
            self.assertTrue(mod._advisor_offers_something_usable(advisor, dest), dest)


class PlaceholderUrlGuardTests(unittest.TestCase):
    """Criterion 3. The T18 campaign found placeholder data reaching a live response
    in two separate places; this pins one of them shut."""

    def test_no_seeded_advisor_can_serve_an_example_domain(self) -> None:
        for a in _seed():
            served = mod._public_contact_url(a.get("contact_url"))
            if served is not None:
                self.assertNotIn("example.", served.lower(), a["name"])

    def test_placeholder_domains_are_suppressed_to_none(self) -> None:
        for url in ("https://x.example.com", "http://y.example.net/path",
                    "https://z.EXAMPLE.ORG", "https://a.example.edu"):
            self.assertIsNone(mod._public_contact_url(url), url)

    def test_a_real_url_survives(self) -> None:
        self.assertEqual(
            mod._public_contact_url("https://fragomen.com/ireland"),
            "https://fragomen.com/ireland",
        )

    def test_missing_url_stays_none(self) -> None:
        self.assertIsNone(mod._public_contact_url(None))
        self.assertIsNone(mod._public_contact_url(""))


class NationalityNotModelledTests(unittest.TestCase):
    """Criterion 4 offers a choice: make an EEA and a third-country persona differ,
    or state plainly that the difference is not modelled. It is not modelled — advisor
    matching takes origin, destination and purpose, and never a nationality — so this
    records that rather than leaving it ambiguous.

    It matters for Ireland specifically: an EEA national needs no advisor at all,
    while a third-country national needs a Critical Skills permit specialist. Adding
    that dimension is a product decision, not a bug fix."""

    def test_match_request_carries_no_nationality_field(self) -> None:
        fields = set(mod.AdvisorMatchRequest.model_fields)
        self.assertNotIn("nationality", fields)
        self.assertNotIn("nationality_class", fields)
        self.assertTrue({"origin_country", "destination_country"} <= fields)


if __name__ == "__main__":
    unittest.main()
