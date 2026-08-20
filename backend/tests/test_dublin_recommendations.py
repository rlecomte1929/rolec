"""
[AIQ-1882 / T18-08] Dublin living areas and schools.

Before this, neither dataset had a single Dublin row (Singapore, Oslo, San Francisco,
New York, Munich and Dubai only) and neither plugin had a Dublin city alias — so a
Madrid->Dublin case resolved "Dublin" to a literal string that matched nothing and
both endpoints returned []. That is the T18 finding, verified in prod 2026-08-13.

SOURCING DISCIPLINE is the hard constraint of this ticket, so it is tested, not just
intended. Daft.ie publishes SUB-REGION bands for Dublin (South City, City Centre,
South County, North City, North County, West Dublin), never per-neighbourhood
figures. Every Dublin rent number here is therefore a sub-region band carried with
its basis, and `test_every_dublin_rent_figure_carries_its_basis` fails if a bare
number ever appears.

Geocoding (criterion 3) is deliberately NOT covered here: it is gated on an unsigned
Geoapify DPA, not on code. See the PR.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.recommendations.plugins.living_areas import (  # noqa: E402
    LivingAreasCriteria,
    LivingAreasPlugin,
    _resolve_city as _resolve_city_areas,
)
from backend.app.recommendations.plugins.schools import (  # noqa: E402
    _resolve_city as _resolve_city_schools,
)

DATASETS = Path(_REPO_ROOT) / "backend" / "app" / "recommendations" / "datasets"

# The sub-region figures actually published in the sourced Daft Q1 2026 extract.
SOURCED_BANDS = {2850, 2444, 2609}


def _rows(name, city="Dublin"):
    """Rows for a city, asserting there ARE some.

    Without the guard every per-row loop below passes vacuously against a tree with
    no Dublin data — which is precisely the tree this ticket exists to fix. A test
    that iterates an empty list and reports green is worse than no test."""
    data = json.loads((DATASETS / f"{name}.json").read_text(encoding="utf-8"))
    rows = [i for i in data if i.get("city") == city]
    assert rows, f"no {city} rows in {name}.json — nothing was checked"
    return rows


class DublinDatasetTests(unittest.TestCase):
    def test_at_least_six_dublin_living_areas(self) -> None:
        """Criterion 1 — at least 6 named areas."""
        areas = _rows("living_areas")
        self.assertGreaterEqual(len(areas), 6, f"only {len(areas)} Dublin areas")
        names = {a["name"] for a in areas}
        for expected in ("Grand Canal Dock", "Ranelagh", "Rathmines"):
            self.assertIn(expected, names)

    def test_dublin_schools_are_non_empty(self) -> None:
        """Criterion 2."""
        self.assertGreaterEqual(len(_rows("schools")), 1)

    def test_every_dublin_rent_figure_carries_its_basis(self) -> None:
        """Criterion 5 — no rent figure without a cited basis and date.

        This is the ticket's central discipline: Daft publishes sub-region bands, so
        a per-neighbourhood number would have to be invented. Every row must name
        which band it used and where it came from."""
        for a in _rows("living_areas"):
            basis = a.get("rent_basis") or ""
            self.assertTrue(basis, f"{a['name']} has a rent figure with no basis")
            self.assertIn("Daft", basis, f"{a['name']} basis names no source")
            self.assertIn("Q1 2026", basis, f"{a['name']} basis carries no date")
            self.assertTrue(a.get("daft_sub_region"), f"{a['name']} names no sub-region")

    def test_no_invented_per_neighbourhood_rent(self) -> None:
        """Every Dublin rent value must be one of the sourced sub-region bands —
        never an interpolated or made-up per-area number."""
        for a in _rows("living_areas"):
            self.assertIn(
                a["avg_rent_2br"], SOURCED_BANDS,
                f"{a['name']} carries {a['avg_rent_2br']}, which is not a sourced Daft band",
            )

    def test_no_invented_three_bed_figures(self) -> None:
        """The sourced extract has no Dublin 3-bed figure, so the field is omitted
        rather than guessed. The plugin falls back to the 2-bed value."""
        for a in _rows("living_areas"):
            self.assertNotIn("avg_rent_3br", a, f"{a['name']} asserts an unsourced 3-bed rent")

    def test_no_invented_review_counts(self) -> None:
        """There is no Dublin review corpus. Ratings are left to the plugin's neutral
        default rather than fabricated with a plausible-looking count."""
        for a in _rows("living_areas") + _rows("schools"):
            self.assertNotIn("rating", a, f"{a['name']} asserts a rating we do not have")
            self.assertEqual(a.get("rating_count"), 0, f"{a['name']} claims reviews")

    def test_dublin_areas_are_geocoded(self) -> None:
        """Criterion 4 needs real coords so commute is computed from the case work
        location instead of read from a static estimate."""
        for a in _rows("living_areas"):
            self.assertIsInstance(a.get("lat"), float, f"{a['name']} has no lat")
            self.assertIsInstance(a.get("lng"), float, f"{a['name']} has no lng")
            # Sanity-box Dublin so a transposed or wrong-hemisphere coord is caught.
            self.assertTrue(53.2 < a["lat"] < 53.5, f"{a['name']} lat {a['lat']} is not in Dublin")
            self.assertTrue(-6.5 < a["lng"] < -6.0, f"{a['name']} lng {a['lng']} is not in Dublin")


class DublinCityResolutionTests(unittest.TestCase):
    def test_both_plugins_resolve_dublin_aliases(self) -> None:
        for resolve in (_resolve_city_areas, _resolve_city_schools):
            for given in ("Dublin", "dublin", "Dublin, Ireland", "Ireland", "IE"):
                self.assertEqual(resolve(given), "Dublin", f"{resolve.__module__}: {given!r}")


class DublinRankingTests(unittest.TestCase):
    """The dataset existing is not the same as the endpoint returning it."""

    def setUp(self) -> None:
        self.plugin = LivingAreasPlugin()
        self.items = self.plugin.load_dataset()

    def _scored(self, city="Dublin", budget=(2000, 3200)):
        c = LivingAreasCriteria(
            destination_city=city,
            budget_monthly={"min": budget[0], "max": budget[1]},
            bedrooms=2,
        )
        return [
            (i, self.plugin.score(c, i))
            for i in self.items
            if self.plugin.score(c, i)["score_raw"] > 0
        ]

    def test_a_dublin_case_ranks_dublin_areas(self) -> None:
        scored = self._scored()
        self.assertGreaterEqual(len(scored), 6, "Dublin case returned fewer than 6 areas")
        for item, _ in scored:
            self.assertEqual(item["city"], "Dublin")

    def test_rent_basis_reaches_the_response_metadata(self) -> None:
        """A number on screen without its basis is the failure this ticket names."""
        for item, result in self._scored():
            self.assertTrue(
                result["metadata"].get("rent_basis"),
                f"{item['name']} loses its basis before the response",
            )

    def test_rent_is_priced_in_euro_not_the_singapore_default(self) -> None:
        for _, result in self._scored():
            self.assertEqual(result["metadata"]["currency"], "EUR")


if __name__ == "__main__":
    unittest.main()
