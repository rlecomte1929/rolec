"""
Tests for backend/services/catalog_coverage.py.

Locks the routine's read-only behavior (report_coverage) and the
ensure_destination_catalog hook's contract.
"""
from __future__ import annotations

import logging
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.catalog_coverage import (  # noqa: E402
    MAX_ITEMS_PER_DESTINATION,
    categories_with_gaps,
    ensure_destination_catalog,
    report_coverage,
)


class CatalogCoverageTests(unittest.TestCase):
    def test_report_returns_known_categories(self) -> None:
        coverage = report_coverage("Munich")
        # The plugin registry has 14 categories at the time of writing;
        # don't lock the count, but require the key ones we ship UI for.
        for k in ("schools", "living_areas", "movers", "banks"):
            self.assertIn(k, coverage)
            self.assertIn("items", coverage[k])
            self.assertIn("geo_bound", coverage[k])

    def test_geo_agnostic_category_counts_all_items(self) -> None:
        # Banks dataset has no `city` field; same count regardless of city.
        a = report_coverage("Munich")["banks"]["items"]
        b = report_coverage("Singapore")["banks"]["items"]
        self.assertEqual(a, b)
        self.assertGreater(a, 0)

    def test_geo_bound_category_filters_by_city(self) -> None:
        # Schools dataset has `city`; Munich and Singapore should differ.
        munich = report_coverage("Munich")["schools"]["items"]
        sg = report_coverage("Singapore")["schools"]["items"]
        self.assertGreater(sg, 0)
        self.assertGreater(munich, 0)
        # Demo seed adds 6 Munich schools; Singapore has more (10+).
        self.assertGreater(sg, munich)

    def test_munich_seed_present_for_demo(self) -> None:
        coverage = report_coverage("Munich")
        # Both geo-bound categories must be non-empty for Munich after the
        # seed; if someone removes the seed, this catches it.
        self.assertGreater(coverage["schools"]["items"], 0)
        self.assertGreater(coverage["living_areas"]["items"], 0)

    def test_alias_resolution(self) -> None:
        # "münchen" / "Germany" / "DE" must resolve to the Munich bucket.
        for alias in ("münchen", "Germany", "DE"):
            self.assertEqual(
                report_coverage(alias)["schools"]["items"],
                report_coverage("Munich")["schools"]["items"],
            )

    def test_categories_with_gaps_returns_below_threshold(self) -> None:
        gaps = categories_with_gaps("Munich")
        # At least one category should still be below 10 items for Munich
        # (we deliberately didn't seed every geo-bound dataset to depth).
        for key in gaps:
            cov = report_coverage("Munich")[key]
            self.assertLess(cov["items"], MAX_ITEMS_PER_DESTINATION)

    def test_ensure_destination_catalog_logs_on_gap(self) -> None:
        with self.assertLogs(
            "backend.services.catalog_coverage", level="INFO"
        ) as cm:
            result = ensure_destination_catalog("schools", "Tokyo", country="Japan")
        self.assertEqual(result["category"], "schools")
        self.assertEqual(result["destination_city"], "Tokyo")
        self.assertEqual(result["country"], "Japan")
        self.assertEqual(result["have"], 0)
        self.assertEqual(result["needed"], MAX_ITEMS_PER_DESTINATION)
        self.assertFalse(result["scraper_dispatched"])
        # Structured log emitted so we can rank gaps by demand.
        self.assertTrue(any("catalog_gap_detected" in line for line in cm.output))

    def test_ensure_destination_catalog_silent_when_full(self) -> None:
        # banks is geo-agnostic with 10 items, so any city is "full".
        logger = logging.getLogger("backend.services.catalog_coverage")
        before = logger.getEffectiveLevel()
        try:
            with self.assertLogs(
                "backend.services.catalog_coverage", level="INFO"
            ) as cm:
                # Trigger SOMETHING so assertLogs doesn't itself raise.
                logging.getLogger("backend.services.catalog_coverage").info("noop")
                result = ensure_destination_catalog("banks", "Tokyo")
            self.assertGreaterEqual(result["have"], MAX_ITEMS_PER_DESTINATION)
            self.assertEqual(result["needed"], 0)
            self.assertFalse(
                any("catalog_gap_detected" in line for line in cm.output),
                "should not emit gap event when catalog is at capacity",
            )
        finally:
            logger.setLevel(before)


if __name__ == "__main__":
    unittest.main()
