"""AIQ-1778 — public.cases country columns are ISO 3166-1 alpha-2, always.

The gap this closes: `case_outcomes` has a DB CHECK (`~ '^[A-Z]{2}$'`), a normaliser
(`outcome_extractor._norm_country`) AND a regex test. `public.cases` had none of the three,
and accumulated 22 rows of 'France' plus 'Germany', 'India' and one empty string.

A name is not a harmless variant. `trigger_engine._build_context` upper-cases without
shortening, so 'France' becomes 'FRANCE', misses the pure-ISO-2 `_EEA_COUNTRIES` frozenset,
and `visa_type` falls through to 'skilled_worker' instead of 'eea_registration' — handing an
EU citizen Blue Card paperwork while the corridor data sheet never attaches.

`test_the_eea_gate_is_why_this_matters` pins that causal chain rather than just the string
format, so the reason the normalisation exists cannot be refactored away without a failure.
"""
from __future__ import annotations

import re
import unittest

from backend.app.services.requirements_country_key import (
    to_iso,
    to_iso_alpha2,
)

_ISO2_RE = re.compile(r"^[A-Z]{2}$")


class TestToIsoAlpha2(unittest.TestCase):
    def test_resolves_the_names_actually_found_in_prod(self):
        """These four are the exact bad values in public.cases as of 2026-08-10."""
        self.assertEqual(to_iso_alpha2("France"), "FR")
        self.assertEqual(to_iso_alpha2("Germany"), "DE")
        self.assertEqual(to_iso_alpha2("India"), "IN")
        self.assertIsNone(to_iso_alpha2(""))

    def test_passes_through_a_wellformed_code_in_any_case(self):
        for raw, want in (("FR", "FR"), ("fr", "FR"), (" de ", "DE"), ("No", "NO")):
            self.assertEqual(to_iso_alpha2(raw), want, raw)

    def test_accepts_a_valid_code_we_have_no_name_for(self):
        """Shape-valid must not be rejected for being absent from our name map.

        The DB CHECK this feeds is `^[A-Z]{2}$` — a shape check, not a membership check.
        Rejecting Monaco because the map is incomplete would block real cases.
        """
        self.assertEqual(to_iso_alpha2("MC"), "MC")
        self.assertEqual(to_iso_alpha2("zz"), "ZZ")

    def test_resolves_localised_spellings(self):
        """An HR user typing in their own language is how 'France' got in."""
        for raw, want in (
            ("Frankreich", "FR"), ("Allemagne", "DE"), ("Deutschland", "DE"),
            ("Norge", "NO"), ("Royaume-Uni", "GB"), ("Inde", "IN"),
        ):
            self.assertEqual(to_iso_alpha2(raw), want, raw)

    def test_resolves_alpha3_and_aliases(self):
        for raw, want in (("DEU", "DE"), ("fra", "FR"), ("USA", "US"), ("UK", "GB")):
            self.assertEqual(to_iso_alpha2(raw), want, raw)

    def test_returns_none_for_genuine_garbage(self):
        """None is reserved for 'not a country at all' — the case worth failing closed on."""
        for raw in (None, "", "   ", "Atlantis", "n/a", "TBD", "1234"):
            self.assertIsNone(to_iso_alpha2(raw), repr(raw))

    def test_output_always_satisfies_the_db_check(self):
        samples = ["France", "fr", "DEU", "Norge", "United Arab Emirates", "MC", "usa"]
        for raw in samples:
            got = to_iso_alpha2(raw)
            self.assertIsNotNone(got, raw)
            self.assertRegex(got, _ISO2_RE, f"{raw!r} -> {got!r}")


class TestToIsoIsStillNarrow(unittest.TestCase):
    """`to_iso` answers a DIFFERENT question and must not have been widened.

    It means "do we hold requirement CATALOG data for this country?" —
    requirements_builder.py:152 uses `to_iso(dest) is None` as a coverage gate. Widening it
    would make an uncovered destination silently claim coverage, which is the fail-open the
    module's own docstring was written to prevent.
    """

    def test_still_none_for_countries_without_catalog_data(self):
        self.assertIsNone(to_iso("IT"))
        self.assertIsNone(to_iso("Japan"))

    def test_the_two_functions_disagree_on_purpose(self):
        # Same input, different questions: Italy has an ISO code but no catalog rows.
        self.assertEqual(to_iso_alpha2("Italy"), "IT")
        self.assertIsNone(to_iso("Italy"))


class TestWriterNormalisesBeforeStoring(unittest.TestCase):
    """The bridge must normalise, and must skip rather than store an unusable country.

    Asserted against the source of `_ensure_canonical_case_from_wizard` rather than by
    running it: the method needs a live DB, a resolvable profile and a company, and the
    behaviour worth locking is that the country values pass through the normaliser at all.
    This is the same style as test_case_engine_bridge.py, which also reads the source.
    """

    def _source(self) -> str:
        import inspect
        from backend.db.cases import CasesMixin
        return inspect.getsource(CasesMixin._ensure_canonical_case_from_wizard)

    def test_both_countries_go_through_to_iso_alpha2(self):
        src = self._source()
        self.assertIn('to_iso_alpha2(derived.get("dest_country"))', src)
        self.assertIn('to_iso_alpha2(derived.get("origin_country"))', src)

    def test_a_bare_strip_is_no_longer_used_for_either_country(self):
        """The exact pre-fix expressions. Their return would reintroduce the bug."""
        src = self._source()
        self.assertNotIn('(derived.get("origin_country") or "").strip()', src)
        self.assertNotIn('(derived.get("dest_country") or "").strip()', src)

    def test_an_unresolvable_origin_fails_closed(self):
        src = self._source()
        self.assertRegex(
            src,
            r"if not origin:(?:.|\n)*?return",
            "an unresolvable origin must skip the upsert, not store a bad value",
        )


class TestTheEeaGateIsWhyThisMatters(unittest.TestCase):
    """Pin the causal chain, not just the string format.

    If someone later decides names are acceptable, this is the test that explains the cost.
    """

    def test_a_country_name_misses_the_eea_frozenset(self):
        from backend.app.services.trigger_engine import _EEA_COUNTRIES
        # What trigger_engine does to the stored value: .upper(), no shortening.
        self.assertNotIn("FRANCE".upper(), _EEA_COUNTRIES)
        self.assertNotIn("GERMANY".upper(), _EEA_COUNTRIES)
        # What it should have been.
        self.assertIn("FR", _EEA_COUNTRIES)
        self.assertIn("DE", _EEA_COUNTRIES)

    def test_normalising_restores_eea_membership(self):
        from backend.app.services.trigger_engine import _EEA_COUNTRIES
        for name in ("France", "Germany", "Norge", "Deutschland"):
            iso = to_iso_alpha2(name)
            self.assertIn(iso, _EEA_COUNTRIES, f"{name} -> {iso}")

    def test_a_non_eea_origin_still_resolves_outside_the_set(self):
        """The fix must not accidentally make everything EEA."""
        self.assertNotIn(to_iso_alpha2("India"), _eea())
        self.assertNotIn(to_iso_alpha2("United States"), _eea())


def _eea():
    from backend.app.services.trigger_engine import _EEA_COUNTRIES
    return _EEA_COUNTRIES


if __name__ == "__main__":
    unittest.main()
