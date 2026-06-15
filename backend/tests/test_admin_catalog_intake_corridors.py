"""
Tests for CATALOG-4 admin intake-corridors endpoint (admin_catalog.py).

Direct-call pattern (mirrors test_admin_catalog_demand_gaps): the route function
is called directly. Intake aggregation runs against a real sqlite `wizard_cases`
table; coverage + allowlist are mocked at the service layer.

Note: the real catalog_coverage.report_coverage emits per-category dicts keyed by
"items" (the coverage count) — the intake-corridors endpoint reads "items", so the
mock here uses "items" too (unlike the demand-gaps test, which mocks "have").
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

from sqlalchemy import create_engine, text

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import admin_catalog as mod  # noqa: E402
import backend.database as database_mod  # noqa: E402

SCHEMA = """
CREATE TABLE wizard_cases (
  id TEXT PRIMARY KEY,
  dest_city TEXT,
  dest_country TEXT,
  origin_city TEXT,
  origin_country TEXT,
  status TEXT,
  created_at TEXT NOT NULL DEFAULT '2026-06-14T00:00:00Z'
);
"""

_ADMIN = {"id": "admin-1", "role": "ADMIN"}


class IntakeCorridorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            # Berlin: 2 intakes from UK (an emerging corridor, movers uncovered)
            conn.execute(text("INSERT INTO wizard_cases (id, dest_city, dest_country, origin_country) VALUES ('1','Berlin','Germany','United Kingdom')"))
            conn.execute(text("INSERT INTO wizard_cases (id, dest_city, dest_country, origin_country) VALUES ('2','Berlin','Germany','United Kingdom')"))
            # Munich: 1 intake, fully covered → should be excluded
            conn.execute(text("INSERT INTO wizard_cases (id, dest_city, dest_country, origin_country) VALUES ('3','Munich','Germany','France')"))
            # Blank dest is ignored by the aggregation.
            conn.execute(text("INSERT INTO wizard_cases (id, dest_city, dest_country, origin_country) VALUES ('4','','Germany','France')"))
        self.eng_patch = mock.patch.object(database_mod.db, "engine", self.engine)
        self.eng_patch.start()
        self.addCleanup(self.eng_patch.stop)

        # Coverage: Berlin/movers uncovered (items=0), banks covered; Munich all covered.
        def _report(city):
            c = (city or "").strip().lower()
            if c == "berlin":
                return {"movers": {"items": 0}, "banks": {"items": 3}}
            if c == "munich":
                return {"movers": {"items": 5}, "banks": {"items": 3}}
            return {}
        from backend.app.services import catalog_coverage
        self.cov_patch = mock.patch.object(catalog_coverage, "report_coverage", side_effect=_report)
        self.cov_patch.start()
        self.addCleanup(self.cov_patch.stop)

        from backend.app.services import scrape_safety
        self.allow_patch = mock.patch.object(scrape_safety, "is_destination_allowlisted", return_value=False)
        self.allow_patch.start()
        self.addCleanup(self.allow_patch.stop)

    def test_lists_emerging_corridors_with_uncovered_categories(self):
        rows = mod.list_intake_corridors(limit=50, user=_ADMIN)
        # Munich is fully covered → excluded; only Berlin remains.
        self.assertEqual(len(rows), 1)
        corridor = rows[0]
        self.assertEqual(corridor["city"], "Berlin")
        self.assertEqual(corridor["country"], "Germany")
        self.assertEqual(corridor["top_origin"], "United Kingdom")
        self.assertEqual(corridor["intake_count"], 2)  # both Berlin intakes counted
        self.assertEqual(corridor["uncovered_categories"], ["movers"])
        self.assertFalse(corridor["allowlisted"])

    def test_ranked_by_intake_volume(self):
        # Add a higher-volume uncovered corridor and confirm ordering.
        with self.engine.begin() as conn:
            for i in range(5):
                conn.execute(text(
                    "INSERT INTO wizard_cases (id, dest_city, dest_country, origin_country) "
                    f"VALUES ('sg{i}','Singapore','Singapore','United Kingdom')"
                ))
        from backend.app.services import catalog_coverage
        def _report(city):
            c = (city or "").strip().lower()
            if c == "berlin":
                return {"movers": {"items": 0}}
            if c == "singapore":
                return {"movers": {"items": 0}}
            return {}
        with mock.patch.object(catalog_coverage, "report_coverage", side_effect=_report):
            rows = mod.list_intake_corridors(limit=50, user=_ADMIN)
        cities = [r["city"] for r in rows]
        # Singapore (5 intakes) ranks above Berlin (2 intakes).
        self.assertEqual(cities, ["Singapore", "Berlin"])

    def test_fully_covered_corridor_excluded(self):
        from backend.app.services import catalog_coverage
        with mock.patch.object(catalog_coverage, "report_coverage", return_value={"movers": {"items": 9}}):
            rows = mod.list_intake_corridors(limit=50, user=_ADMIN)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
