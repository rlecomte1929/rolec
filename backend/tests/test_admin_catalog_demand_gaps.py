"""
Tests for CATALOG-1 admin demand-gaps endpoints (admin_catalog.py).

Direct-call pattern: the route functions are called directly (the
require_admin dependency only runs under FastAPI routing). The demand
aggregation runs against a real sqlite `catalog_employee_demand` table;
coverage + scraper + allowlist are mocked at the service layer.
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
CREATE TABLE catalog_employee_demand (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  category TEXT NOT NULL,
  destination_city TEXT,
  destination_country TEXT,
  last_seen_by_user_id TEXT,
  last_seen_at TEXT NOT NULL DEFAULT '2026-06-14T00:00:00Z',
  demand_count INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT '2026-06-14T00:00:00Z'
);
"""

_ADMIN = {"id": "admin-1", "role": "ADMIN"}


class DemandGapsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            # Munich movers: 2 companies, demand 5 + 3 = 8 (UNcovered)
            conn.execute(text("INSERT INTO catalog_employee_demand (id, company_id, category, destination_city, destination_country, demand_count) VALUES ('1','c1','movers','Munich','Germany',5)"))
            conn.execute(text("INSERT INTO catalog_employee_demand (id, company_id, category, destination_city, destination_country, demand_count) VALUES ('2','c2','movers','Munich','Germany',3)"))
            # Berlin banks: demand 4 (COVERED — should be filtered out)
            conn.execute(text("INSERT INTO catalog_employee_demand (id, company_id, category, destination_city, destination_country, demand_count) VALUES ('3','c1','banks','Berlin','Germany',4)"))
        self.eng_patch = mock.patch.object(database_mod.db, "engine", self.engine)
        self.eng_patch.start()
        self.addCleanup(self.eng_patch.stop)

        # Coverage: Berlin/banks covered (have=2), Munich/movers uncovered (have=0).
        def _report(city):
            if (city or "").strip().lower() == "berlin":
                return {"banks": {"have": 2, "needed": 3}}
            return {}  # nothing covered for Munich
        from backend.app.services import catalog_coverage
        self.cov_patch = mock.patch.object(catalog_coverage, "report_coverage", side_effect=_report)
        self.cov_patch.start()
        self.addCleanup(self.cov_patch.stop)

        from backend.app.services import scrape_safety
        self.allow_patch = mock.patch.object(scrape_safety, "is_destination_allowlisted", return_value=False)
        self.allow_patch.start()
        self.addCleanup(self.allow_patch.stop)

    def test_demand_gaps_lists_uncovered_ranked_excludes_covered(self):
        rows = mod.list_demand_gaps(limit=50, user=_ADMIN)
        # Berlin/banks is covered → excluded; only Munich/movers remains.
        self.assertEqual(len(rows), 1)
        g = rows[0]
        self.assertEqual(g["category"], "movers")
        self.assertEqual(g["city"], "Munich")
        self.assertEqual(g["country"], "Germany")
        self.assertEqual(g["demand"], 8)       # 5 + 3 aggregated cross-company
        self.assertEqual(g["companies"], 2)
        self.assertFalse(g["allowlisted"])

    def test_fill_allowlists_then_scrapes(self):
        from backend.app.services import scrape_safety, catalog_scraper
        with mock.patch.object(scrape_safety, "add_allowlist_entry", return_value={}) as add, \
             mock.patch.object(catalog_scraper, "populate_destination_catalog", return_value=[{"id": "x"}, {"id": "y"}]) as scrape:
            out = mod.fill_demand_gap(mod.FillGapBody(category="movers", city="Munich", country="Germany"), user=_ADMIN)
        add.assert_called_once()
        scrape.assert_called_once()
        _, kw = scrape.call_args
        self.assertEqual(kw["category"], "movers")
        self.assertEqual(kw["destination_city"], "Munich")
        self.assertEqual(out["scraped_count"], 2)
        self.assertTrue(out["allowlisted"])

    def test_fill_tolerates_already_allowlisted(self):
        from backend.app.services import scrape_safety, catalog_scraper
        with mock.patch.object(scrape_safety, "add_allowlist_entry", side_effect=ValueError("already")) as _add, \
             mock.patch.object(catalog_scraper, "populate_destination_catalog", return_value=[]) as scrape:
            out = mod.fill_demand_gap(mod.FillGapBody(category="movers", city="Munich", country="Germany"), user=_ADMIN)
        # Still scrapes even when the allowlist entry already exists; empty
        # scraper result (disabled / no key) is a valid 0, not an error.
        scrape.assert_called_once()
        self.assertEqual(out["scraped_count"], 0)


if __name__ == "__main__":
    unittest.main()
