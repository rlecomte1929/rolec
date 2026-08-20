"""
[AIQ-1872] Mover service-area scoring was Asia-only and city-only.

The ticket's symptom was "Singapore movers surface for a Madrid->Dublin move".
Verified in prod 2026-08-20: a Dublin case now returns **0 movers**, because the
HR-curation gate (AIQ-1857) already stops uncurated vendors reaching the employee.
So the visible symptom is gone — but the RANKING defect underneath is real, and it
is what would resurface the moment a company curates movers.

Measured on origin/main, on the shipped dataset:

    Dublin   vs ["Europe"]   -> 20      Dublin   vs ["Asia"]      -> 75
    Dublin   vs ["Ireland"]  -> 20      New York vs ["Americas"]  -> 20

A mover covering Europe scored WORSE for a Dublin move than one covering Asia, and
a mover covering Ireland scored as though it had no coverage at all. The dimension
was not merely weak — outside Asia it was inverted.

Two root causes, both fixed:
  1. `asia_keywords` was the only region the scorer knew.
  2. `MoversCriteria` never declared `destination_country`, so pydantic dropped the
     field `criteria_builder` had always emitted and the scorer only saw a city.

Deliberately still a SCORE, not a gate: the ticket warns against over-filtering
corridors that legitimately share regional movers, and `service_areas` is
vendor-authored free text rather than a guarantee.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.recommendations.plugins.movers import (  # noqa: E402
    MoversCriteria,
    _service_area_score,
)


class RegionSymmetryTests(unittest.TestCase):
    """The core defect: Asia was the only region with a tier."""

    def test_europe_beats_asia_for_a_dublin_move(self) -> None:
        europe = _service_area_score("Dublin", ["Europe"], "IE")
        asia = _service_area_score("Dublin", ["Asia"], "IE")
        self.assertGreater(
            europe, asia,
            "a Europe-covering mover must outrank an Asia-covering one for Dublin",
        )

    def test_every_region_scores_its_own_destination_alike(self) -> None:
        """No region is privileged. Before the fix only the Asia row scored 75."""
        for city, country, region_word in [
            ("Dublin", "IE", "Europe"),
            ("Madrid", "ES", "Europe"),
            ("New York", "US", "Americas"),
            ("Tokyo", "JP", "Asia"),
            ("Sydney", "AU", "Oceania"),
            ("Dubai", "AE", "Middle East"),
        ]:
            self.assertEqual(
                _service_area_score(city, [region_word], country), 75.0,
                f"{city} / {region_word} did not get the region tier",
            )

    def test_out_of_region_is_penalised(self) -> None:
        self.assertEqual(_service_area_score("Dublin", ["Singapore"], "IE"), 20.0)
        self.assertEqual(_service_area_score("Tokyo", ["Europe"], "JP"), 20.0)


class CountryLevelCoverageTests(unittest.TestCase):
    def test_country_name_matches_a_city_in_it(self) -> None:
        """A mover covering "Ireland" plainly serves Dublin. It scored 20 before."""
        self.assertEqual(_service_area_score("Dublin", ["Ireland"], "IE"), 95.0)

    def test_iso_code_on_the_case_matches_a_written_out_country(self) -> None:
        """"IE" is not a substring of "Ireland" — which is exactly why country-level
        coverage read as no coverage. Both forms must resolve to each other."""
        self.assertEqual(_service_area_score("Dublin", ["Ireland"], "IE"), 95.0)
        self.assertEqual(_service_area_score("Dublin", ["ireland"], "ie"), 95.0)
        self.assertEqual(_service_area_score("Dublin", ["IE"], "Ireland"), 95.0)

    def test_city_still_outranks_country_which_outranks_region(self) -> None:
        city = _service_area_score("Dublin", ["Dublin"], "IE")
        country = _service_area_score("Dublin", ["Ireland"], "IE")
        glob = _service_area_score("Dublin", ["Global"], "IE")
        region = _service_area_score("Dublin", ["Europe"], "IE")
        none_ = _service_area_score("Dublin", ["Singapore"], "IE")
        self.assertEqual([city, country, glob, region, none_],
                         sorted([city, country, glob, region, none_], reverse=True))


class CriteriaCarriesCountryTests(unittest.TestCase):
    def test_movers_criteria_declares_destination_country(self) -> None:
        """criteria_builder has always emitted it; the model dropped it silently."""
        self.assertIn("destination_country", MoversCriteria.model_fields)

    def test_criteria_round_trips_the_country(self) -> None:
        c = MoversCriteria(destination_city="Dublin", destination_country="IE")
        self.assertEqual(c.destination_country, "IE")


class DegradationTests(unittest.TestCase):
    """It stays a score, not a gate — and never raises on thin input."""

    def test_unknown_destination_is_neutral_not_zero(self) -> None:
        self.assertEqual(_service_area_score("", [], ""), 50.0)

    def test_empty_service_areas_is_no_coverage(self) -> None:
        self.assertEqual(_service_area_score("Dublin", [], "IE"), 20.0)

    def test_unmapped_country_does_not_guess_a_region(self) -> None:
        """An unknown country must not silently inherit a continent."""
        self.assertEqual(_service_area_score("Ulaanbaatar", ["Europe"], "MN"), 20.0)

    def test_region_still_resolves_when_no_country_is_supplied(self) -> None:
        """The golden scoring baseline passes a bare `destination_city: "Tokyo"` with
        no country, and so can any hand-built criteria. An earlier cut of this fix
        required a country to resolve a region, which dropped Tokyo vs ["Asia"] from
        75 to 20 — trading the Asia-only bug for a country-required one. The frozen
        baseline (backend/tests/eval/test_weight_refactor.py) caught it."""
        self.assertEqual(_service_area_score("Tokyo", ["Asia"], ""), 75.0)
        self.assertEqual(_service_area_score("Dublin", ["Europe"], ""), 75.0)
        self.assertEqual(_service_area_score("New York", ["Americas"], ""), 75.0)

    def test_global_coverage_still_ranks_well_everywhere(self) -> None:
        for city, country in [("Dublin", "IE"), ("Tokyo", "JP"), ("New York", "US")]:
            self.assertEqual(_service_area_score(city, ["Global"], country), 85.0)

    def test_out_of_region_is_penalised_not_excluded(self) -> None:
        """The ticket warns against over-filtering. A wrong-region mover keeps a
        non-zero score so it can still appear when nothing better exists."""
        self.assertGreater(_service_area_score("Dublin", ["Singapore"], "IE"), 0.0)


if __name__ == "__main__":
    unittest.main()
