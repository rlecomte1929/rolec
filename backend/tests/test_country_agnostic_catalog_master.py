"""AIQ-2195 / ADR-002 Option B — country-agnostic catalog master.

Pins the serving-path gate, the vendor_proposal NULL-country predicate for the
three known multi-country movers, and the idempotent data backfill (no DDL).
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.services import employee_recommendations_filter as flt  # noqa: E402
from backend.app.services import service_catalog  # noqa: E402
from backend.app.services.vendor_proposal import _SEED_SQL  # noqa: E402

BACKFILL_SQL = (
    Path(_REPO_ROOT) / "backend/scripts/backfill_country_agnostic_catalog_masters.py"
).read_text(encoding="utf-8")

_SCHEMA = """
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY, category TEXT, city TEXT, country TEXT, name TEXT,
    attributes_json TEXT DEFAULT '{}', source TEXT, active INTEGER DEFAULT 1,
    external_id TEXT, supplier_id TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE suppliers (
    id TEXT PRIMARY KEY, name TEXT, status TEXT
);
CREATE TABLE supplier_service_capabilities (
    id TEXT PRIMARY KEY, supplier_id TEXT, service_category TEXT,
    coverage_scope_type TEXT, country_code TEXT, platform_vetting_status TEXT
);
"""

# SQLite stand-in for the ADR UPDATE (btrim → trim, no public. schema, CURRENT_TIMESTAMP).
_SQLITE_BACKFILL = """
UPDATE service_catalog_items
   SET country = NULL, updated_at = 'now'
 WHERE source = 'registry_promoted'
   AND country IS NOT NULL
   AND id IN (
     SELECT sci.id
     FROM service_catalog_items sci
     WHERE sci.source = 'registry_promoted'
       AND sci.country IS NOT NULL
       AND sci.supplier_id IN (
         SELECT ssc.supplier_id
         FROM supplier_service_capabilities ssc
         WHERE ssc.platform_vetting_status = 'approved'
           AND ssc.country_code IS NOT NULL AND trim(ssc.country_code) <> ''
           AND lower(trim(ssc.service_category)) = lower(trim(sci.category))
         GROUP BY ssc.supplier_id
         HAVING count(DISTINCT ssc.country_code) > 1
       )
   )
"""

# vendor_proposal destination predicate without window/jsonb (sqlite-runnable).
_PROPOSAL_PREDICATE = """
SELECT DISTINCT sci.name
FROM service_catalog_items sci
LEFT JOIN suppliers s
       ON s.id = sci.supplier_id AND s.status = 'active'
LEFT JOIN supplier_service_capabilities ssc
       ON ssc.supplier_id = sci.supplier_id
      AND ssc.service_category = sci.category
      AND ssc.platform_vetting_status = 'approved'
      AND (ssc.coverage_scope_type = 'global' OR ssc.country_code = :dest)
WHERE sci.active = 1
  AND (sci.country = :dest OR sci.country IS NULL)
  AND (
        sci.country = :dest
     OR (s.id IS NOT NULL AND ssc.supplier_id IS NOT NULL)
      )
"""


class CountryAgnosticCatalogMasterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in _SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        for mod in (service_catalog, flt):
            patcher = mock.patch.object(mod.db, "engine", self.engine)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _seed_mover(self, *, sid, name, master_country, countries, source="registry_promoted"):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO suppliers (id, name, status) VALUES (:i, :n, 'active')"),
                {"i": sid, "n": name},
            )
            conn.execute(
                text(
                    "INSERT INTO service_catalog_items "
                    "(id, category, country, city, name, source, active, supplier_id) "
                    "VALUES (:id, 'movers', :co, 'Berlin', :n, :src, 1, :sid)"
                ),
                {"id": f"m-{sid}", "co": master_country, "n": name, "src": source, "sid": sid},
            )
            for i, cc in enumerate(countries):
                conn.execute(
                    text(
                        "INSERT INTO supplier_service_capabilities "
                        "(id, supplier_id, service_category, coverage_scope_type, "
                        " country_code, platform_vetting_status) "
                        "VALUES (:id, :sid, 'movers', 'country', :cc, 'approved')"
                    ),
                    {"id": f"cap-{sid}-{i}", "sid": sid, "cc": cc},
                )

    def test_null_country_master_serves_capability_countries_only(self):
        self._seed_mover(
            sid="ags", name="AGS France (SOFDI)", master_country=None, countries=("DE", "NO"),
        )
        master = {
            "id": "m-ags", "category": "movers", "country": None, "city": "Berlin",
            "supplier_id": "ags", "name": "AGS France (SOFDI)",
        }
        self.assertTrue(flt._serves_destination(master, "Oslo", "NO"))
        self.assertTrue(flt._serves_destination(master, "Berlin", "DE"))
        self.assertFalse(flt._serves_destination(master, "Paris", "FR"))

    def test_single_country_master_unchanged(self):
        master = {
            "id": "m-local", "category": "movers", "country": "FR", "city": None,
            "supplier_id": "local", "name": "Paris Only Movers",
        }
        self.assertTrue(flt._serves_destination(master, "Paris", "FR"))
        self.assertFalse(flt._serves_destination(master, "Oslo", "NO"))

    def test_null_country_global_capability_serves_destination(self):
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO suppliers (id, name, status) VALUES ('sirva', 'SIRVA', 'active')"
            ))
            conn.execute(text(
                "INSERT INTO supplier_service_capabilities "
                "(id, supplier_id, service_category, coverage_scope_type, "
                " country_code, platform_vetting_status) "
                "VALUES ('g1', 'sirva', 'movers', 'global', NULL, 'approved')"
            ))
        master = {
            "id": "m-s", "category": "movers", "country": None,
            "supplier_id": "sirva", "name": "SIRVA",
        }
        self.assertTrue(flt._serves_destination(master, "Dublin", "IE"))

    def test_null_country_without_supplier_does_not_pass_through(self):
        master = {"id": "m-x", "category": "movers", "country": None, "name": "orphan"}
        self.assertFalse(flt._serves_destination(master, "Oslo", "NO"))

    def test_vendor_proposal_sql_still_gates_null_country_on_capabilities(self):
        self.assertIn("sci.country IS NULL", _SEED_SQL)
        self.assertIn("coverage_scope_type = 'global'", _SEED_SQL)
        self.assertIn("ssc.country_code = :dest_country", _SEED_SQL)

    def test_vendor_proposal_predicate_three_movers_per_approved_country(self):
        """The ADR's three rows: each NULL master surfaces for its countries, not FR."""
        self._seed_mover(sid="ags", name="AGS France (SOFDI)", master_country=None, countries=("DE", "NO"))
        self._seed_mover(sid="awt", name="All World Transport", master_country=None, countries=("DE", "FR"))
        self._seed_mover(
            sid="gro", name="Grospiron International", master_country=None, countries=("DE", "NO"),
        )
        # Tagged-country control: must not appear for NO.
        self._seed_mover(sid="paris", name="Paris Only", master_country="FR", countries=("FR",))

        def names(dest: str) -> set[str]:
            with self.engine.connect() as conn:
                return {
                    r[0]
                    for r in conn.execute(text(_PROPOSAL_PREDICATE), {"dest": dest}).fetchall()
                }

        self.assertEqual(
            names("NO"),
            {"AGS France (SOFDI)", "Grospiron International"},
        )
        self.assertEqual(
            names("DE"),
            {"AGS France (SOFDI)", "All World Transport", "Grospiron International"},
        )
        self.assertEqual(names("FR"), {"All World Transport", "Paris Only"})
        self.assertEqual(names("IE"), set())

    def test_backfill_sql_matches_adr_scope(self):
        self.assertIn("source = 'registry_promoted'", BACKFILL_SQL)
        self.assertIn("sci.country IS NOT NULL", BACKFILL_SQL)
        self.assertIn("HAVING count(DISTINCT ssc.country_code) > 1", BACKFILL_SQL)
        self.assertNotIn("DROP ", BACKFILL_SQL)
        self.assertNotIn("ALTER ", BACKFILL_SQL)

    def test_backfill_nulls_multi_country_registry_masters_only_and_is_idempotent(self):
        self._seed_mover(
            sid="ags", name="AGS France (SOFDI)", master_country="DE", countries=("DE", "NO"),
        )
        self._seed_mover(
            sid="one", name="Single Country Movers", master_country="FR", countries=("FR",),
        )
        # Human-set source must not be overwritten even if the supplier is multi-country.
        self._seed_mover(
            sid="hand", name="Hand Curated", master_country="DE", countries=("DE", "NO"),
            source="manual",
        )
        with self.engine.begin() as conn:
            conn.execute(text(_SQLITE_BACKFILL))
            rows = {
                r.name: r.country
                for r in conn.execute(
                    text("SELECT name, country FROM service_catalog_items")
                )
            }
        self.assertIsNone(rows["AGS France (SOFDI)"])
        self.assertEqual(rows["Single Country Movers"], "FR")
        self.assertEqual(rows["Hand Curated"], "DE")

        with self.engine.begin() as conn:
            result = conn.execute(text(_SQLITE_BACKFILL))
            self.assertEqual(result.rowcount, 0)

    def test_clear_master_country_leaves_other_fields(self):
        self._seed_mover(sid="ags", name="AGS France (SOFDI)", master_country="DE", countries=("DE",))
        service_catalog.clear_master_country("m-ags")
        with self.engine.connect() as conn:
            r = conn.execute(
                text("SELECT country, name, source, supplier_id FROM service_catalog_items WHERE id='m-ags'")
            ).mappings().first()
        self.assertIsNone(r["country"])
        self.assertEqual(r["name"], "AGS France (SOFDI)")
        self.assertEqual(r["source"], "registry_promoted")
        self.assertEqual(r["supplier_id"], "ags")


if __name__ == "__main__":
    unittest.main()
