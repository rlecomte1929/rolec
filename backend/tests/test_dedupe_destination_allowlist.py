"""The destination-allowlist dedupe must collapse spellings, never merge two real places.

HR could not reach 29 already-approved Dublin vendors because the allowlist stored the
destination three ways — `dublin/ireland`, `Dublin/IE`, `Dublin/Ireland` — and the curation
page builds its country dropdown from a raw Set over the exact strings. Picking the
lower-cased one sends `destination_city="dublin"`, which `hr_catalog.get_curation_view`
compares with a raw `==` against `'Dublin'`, returning nothing.

The risk in fixing it by deletion is the opposite error: collapsing two genuinely different
places that share a city name. That is what `test_two_real_cambridges_both_survive` pins.
"""
from __future__ import annotations

import importlib.util
import os
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT = os.path.join(_REPO_ROOT, "backend", "scripts", "dedupe_destination_allowlist.py")

_spec = importlib.util.spec_from_file_location("dedupe_destination_allowlist", _SCRIPT)
dedupe = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(dedupe)


def _rows():
    """The production shape, measured 2026-08-23."""
    return [
        {"id": "1", "city": "Paris", "country": "FR"},
        {"id": "2", "city": "Paris", "country": "France"},
        {"id": "3", "city": "Dublin", "country": "IE"},
        {"id": "4", "city": "Dublin", "country": "Ireland"},
        {"id": "5", "city": "dublin", "country": "ireland"},
        {"id": "6", "city": "Oslo", "country": "NO"},
        {"id": "7", "city": "Oslo", "country": "Norway"},
        {"id": "8", "city": "Cork", "country": "Ireland"},
    ]


def _deleted(rows):
    return {d["id"] for _s, ds in dedupe.plan(rows) for d in ds}


def _survivors(rows):
    return {s["id"] for s, _ds in dedupe.plan(rows)}


class CollapsesSpellingsOfOneDestination(unittest.TestCase):
    def test_the_four_redundant_production_rows_are_removed(self) -> None:
        self.assertEqual({"1", "3", "5", "6"}, _deleted(_rows()))

    def test_the_survivor_is_the_full_name_title_cased_form(self) -> None:
        """71 of 74 countries already use the full name; the ISO rows are the outliers."""
        keep = {s["city"] + "/" + s["country"] for s, _ in dedupe.plan(_rows())}
        self.assertEqual({"Paris/France", "Dublin/Ireland", "Oslo/Norway"}, keep)

    def test_a_city_with_only_one_row_is_untouched(self) -> None:
        self.assertNotIn("8", _deleted(_rows()))

    def test_an_already_clean_allowlist_is_a_no_op(self) -> None:
        clean = [{"id": "a", "city": "Cork", "country": "Ireland"},
                 {"id": "b", "city": "Galway", "country": "Ireland"}]
        self.assertEqual([], dedupe.plan(clean))


class NeverMergesTwoDifferentPlaces(unittest.TestCase):
    def test_two_real_cambridges_both_survive(self) -> None:
        """The whole risk of a delete-based fix. Same city name, different countries."""
        rows = _rows() + [
            {"id": "9", "city": "Cambridge", "country": "United Kingdom"},
            {"id": "10", "city": "Cambridge", "country": "United States"},
        ]
        deleted = _deleted(rows)
        self.assertNotIn("9", deleted)
        self.assertNotIn("10", deleted)

    def test_iso_and_full_name_are_recognised_as_one_country(self) -> None:
        """Via requirements_country_key.resolve_catalog_country, NOT a string heuristic.

        A first draft matched an ISO code against the start of the full name. That is wrong:
        `'ireland'.startswith('ie')` is False — ISO codes are not prefixes (IE→Ireland,
        DE→Germany, ES→Spain). It passed for FR/France and NO/Norway and silently refused the
        one destination this exists to fix.
        """
        self.assertTrue(dedupe._same_country({"country": "Ireland"}, {"country": "IE"}))
        self.assertTrue(dedupe._same_country({"country": "France"}, {"country": "FR"}))
        self.assertTrue(dedupe._same_country({"country": "Norway"}, {"country": "NO"}))
        self.assertTrue(dedupe._same_country({"country": "Germany"}, {"country": "DE"}))
        self.assertTrue(dedupe._same_country({"country": "Spain"}, {"country": "ES"}))

    def test_two_different_countries_are_not_the_same(self) -> None:
        self.assertFalse(
            dedupe._same_country({"country": "United Kingdom"}, {"country": "United States"})
        )
        self.assertFalse(dedupe._same_country({"country": "Ireland"}, {"country": "Iceland"}))

    def test_a_blank_country_never_matches(self) -> None:
        self.assertFalse(dedupe._same_country({"country": ""}, {"country": "Ireland"}))
        self.assertFalse(dedupe._same_country({"country": None}, {"country": None}))


class CityCanonicalisation(unittest.TestCase):
    def test_it_matches_the_curation_reader(self) -> None:
        """Must agree with vendor_curation._canon_city or the two disagree about what a
        destination IS — which is the class of bug being fixed."""
        from backend.app.services.vendor_curation import _canon_city

        for value in ("Dublin", " dublin ", "Zürich", "ZURICH", "  São  Paulo "):
            self.assertEqual(_canon_city(value), dedupe.canon_city(value), value)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
