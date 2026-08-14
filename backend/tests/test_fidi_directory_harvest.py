"""[Stage 9 · Phase 0] The FIDI affiliate harvest — tier-1 origin supply for movers.

Phase 0 found zero FR-based movers able to evidence Norway reach. These tests pin the parts
that make the replacement supply trustworthy: a real per-entity evidence URL, an audited FAIM
expiry, and an accreditation that stays `claimed` until something actually confirms it.
"""
from __future__ import annotations

import unittest

from backend.app.services.registry_sources import Acquisition, sources_for
from backend.app.services.vendor_harvester import validate
from backend.imports.suppliers.fidi_directory import (
    COUNTRY_IDS,
    SOURCE_NAME,
    body_for,
    harvest,
    list_slugs,
    parse_affiliate,
    to_candidate,
)

_INDEX = """
<a href="/find-fidi-affiliate/ags-france">AGS</a>
<a href="/find-fidi-affiliate/gosselin-5">Gosselin</a>
<a href="/find-fidi-affiliate/ags-france">AGS again</a>
<a href="/find-fidi-affiliate/companies-fraudulently-claiming-fidi-affiliation">notice</a>
<a href="/find-fidi-affiliate/faim-34-top-performers">editorial</a>
"""

_DETAIL = """
<title>SANTA FE RELOCATION - PARIS | FIDI</title>
<div>address 6, RUE RENE RAZEL SACLAY France</div>
<div>Certificate validity FAIM Expiry date: 2029</div>
"""


class ListingTests(unittest.TestCase):
    def test_editorial_entries_are_not_affiliates(self) -> None:
        slugs = list_slugs("FR", fetcher=lambda url: _INDEX)
        self.assertNotIn("companies-fraudulently-claiming-fidi-affiliation", slugs)
        self.assertNotIn("faim-34-top-performers", slugs)

    def test_repeated_links_yield_one_slug(self) -> None:
        self.assertEqual(list_slugs("FR", fetcher=lambda url: _INDEX),
                         ["ags-france", "gosselin-5"])

    def test_an_unverified_country_is_refused_rather_than_guessed(self) -> None:
        """A wrong country id silently harvests the wrong country's movers."""
        with self.assertRaises(LookupError):
            list_slugs("ZZ", fetcher=lambda url: _INDEX)

    def test_a_failed_listing_yields_no_slugs_rather_than_raising(self) -> None:
        def boom(url: str):
            raise TimeoutError("boom")

        self.assertEqual(list_slugs("FR", fetcher=boom), [])

    def test_france_id_is_the_one_that_was_verified(self) -> None:
        self.assertEqual(COUNTRY_IDS["FR"], 101)


class ParseTests(unittest.TestCase):
    def test_the_name_comes_from_the_title(self) -> None:
        aff = parse_affiliate("santa-fe-relocation-paris", _DETAIL)
        self.assertEqual(aff.name, "SANTA FE RELOCATION - PARIS")

    def test_the_expiry_year_becomes_31_dec_not_1_jan(self) -> None:
        """"Expiry 2026" means valid THROUGH 2026. The older 1-Jan convention is the wrong
        direction for an end date: on 2026-08-13 it marked 4 of 11 live FIDI affiliates as
        already expired, including one of only two suppliers able to evidence Norway reach."""
        self.assertEqual(parse_affiliate("x", _DETAIL).faim_expiry, "2029-12-31")

    def test_a_current_year_certificate_is_not_treated_as_expired(self) -> None:
        aff = parse_affiliate("x", _DETAIL.replace("2029", "2026"))
        self.assertEqual(aff.faim_expiry, "2026-12-31")

    def test_a_missing_expiry_is_none_not_invented(self) -> None:
        aff = parse_affiliate("x", "<title>SOME MOVER | FIDI</title>")
        self.assertIsNone(aff.faim_expiry)

    def test_faim_plus_is_only_claimed_when_the_page_says_so(self) -> None:
        """FAIM Plus is a higher audited certification. Inventing it overstates a credential."""
        plain = parse_affiliate("x", _DETAIL)
        self.assertFalse(plain.faim_plus)
        self.assertEqual(body_for(plain), "FIDI Global Alliance / FAIM (auditor: EY)")

        plus = parse_affiliate("y", _DETAIL.replace("FAIM Expiry", "FAIM Plus Expiry"))
        self.assertTrue(plus.faim_plus)
        self.assertEqual(body_for(plus), "FIDI Global Alliance / FAIM Plus (auditor: EY)")

    def test_the_country_is_only_set_when_the_page_states_it(self) -> None:
        self.assertEqual(parse_affiliate("x", _DETAIL, country_hint="France").address_country,
                         "France")
        self.assertIsNone(parse_affiliate("x", _DETAIL, country_hint="Germany").address_country)

    def test_a_titleless_page_is_dropped(self) -> None:
        self.assertIsNone(parse_affiliate("x", "<div>no title here</div>"))


class CandidateTests(unittest.TestCase):
    def _cand(self):
        return to_candidate(parse_affiliate("santa-fe-relocation-paris", _DETAIL), country="FR")

    def test_the_candidate_validates(self) -> None:
        validate(self._cand())  # must not raise

    def test_the_source_is_tier_1_and_now_enumerable(self) -> None:
        src = [s for s in sources_for("FR-NO", "movers") if s.name == SOURCE_NAME][0]
        self.assertEqual(src.tier, 1)
        self.assertIs(src.acquisition, Acquisition.HTTP_LISTING,
                      "the /find-mover 404 made this look manual; the country index is live")

    def test_the_evidence_url_is_per_entity_and_matches_the_pattern(self) -> None:
        import re

        cand = self._cand()
        src = [s for s in sources_for("FR-NO", "movers") if s.name == SOURCE_NAME][0]
        self.assertEqual(
            cand.source_url,
            "https://www.fidi.org/find-fidi-affiliate/santa-fe-relocation-paris",
        )
        self.assertTrue(re.search(src.entry_url_pattern, cand.source_url))

    def test_no_membership_number_is_invented(self) -> None:
        """FIDI publishes none. A fabricated one would look like stronger evidence."""
        self.assertIsNone(self._cand().accreditation_number)

    def test_no_city_is_claimed(self) -> None:
        self.assertIsNone(self._cand().city)

    def test_the_note_says_the_accreditation_is_not_yet_confirmed(self) -> None:
        self.assertIn("CLAIMED until", self._cand().notes)

    def test_the_body_matches_the_strings_already_in_the_table(self) -> None:
        """Dedupe is on (supplier_id, body); a novel spelling creates a second row for a
        supplier we already hold."""
        self.assertIn(self._cand().accreditation_body, {
            "FIDI Global Alliance / FAIM (auditor: EY)",
            "FIDI Global Alliance / FAIM Plus (auditor: EY)",
        })


class HarvestTests(unittest.TestCase):
    def test_a_dead_detail_page_is_reported_not_skipped_silently(self) -> None:
        def fetcher(url: str):
            if url.endswith("gosselin-5"):
                raise TimeoutError("boom")
            return _INDEX if "?country=" in url else _DETAIL

        cands, problems = harvest("FR", fetcher=fetcher)
        self.assertEqual(len(cands), 1)
        self.assertTrue(any("gosselin-5" in p for p in problems))

    def test_an_empty_listing_is_a_reported_finding(self) -> None:
        cands, problems = harvest("FR", fetcher=lambda url: "<html></html>")
        self.assertEqual(cands, [])
        self.assertTrue(any("listed no affiliates" in p for p in problems))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
