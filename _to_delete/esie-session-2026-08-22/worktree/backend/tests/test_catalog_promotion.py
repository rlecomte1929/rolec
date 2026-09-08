"""
[CATALOG-2] Unit tests for catalog_promotion_service.promote_hr_vendors.

In-memory SQLite with the two real table shapes (service_catalog_items,
company_vendor_selections); the shared `db.engine` singleton is patched so both
the promotion service and service_catalog.upsert_item hit the test engine.
"""
from __future__ import annotations

import json
import os
import unittest
import uuid
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text  # noqa: E402

from backend.database import db as db_singleton  # noqa: E402
from backend.app.services import catalog_promotion_service  # noqa: E402

SCHEMA = """
CREATE TABLE service_catalog_items (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  city TEXT,
  country TEXT,
  name TEXT NOT NULL,
  attributes_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'manual',
  active INTEGER NOT NULL DEFAULT 1,
  external_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  created_by_user_id TEXT
);
CREATE TABLE company_vendor_selections (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  category TEXT NOT NULL,
  destination_city TEXT,
  country TEXT,
  master_item_id TEXT,
  custom_item_json TEXT,
  selected INTEGER DEFAULT 1,
  display_order INTEGER DEFAULT 0,
  created_by_user_id TEXT
);
"""


class TestCatalogPromotion(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.strip().split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
        self._patch = mock.patch.object(db_singleton, "engine", self.engine)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()

    # ---- helpers ----------------------------------------------------------
    def _add_custom(self, company_id, category, city, name, country="DE", attributes=None):
        payload = {"name": name, **(attributes or {})}
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO company_vendor_selections "
                    "(id, company_id, category, destination_city, country, custom_item_json) "
                    "VALUES (:id, :co, :cat, :city, :country, :json)"
                ),
                {
                    "id": str(uuid.uuid4()), "co": company_id, "cat": category,
                    "city": city, "country": country, "json": json.dumps(payload),
                },
            )

    def _seed_master(self, category, city, name, source="seed"):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO service_catalog_items "
                    "(id, category, city, country, name, attributes_json, source, active, created_at, updated_at) "
                    "VALUES (:id, :cat, :city, 'DE', :name, '{}', :source, 1, 't', 't')"
                ),
                {"id": str(uuid.uuid4()), "cat": category, "city": city, "name": name, "source": source},
            )

    def _catalog_rows(self):
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT * FROM service_catalog_items")).mappings().all()

    # ---- tests ------------------------------------------------------------
    def test_promotes_at_threshold(self):
        self._add_custom("co1", "cleaning", "Berlin", "CleanCo", attributes={"phone": "123"})
        self._add_custom("co2", "cleaning", "Berlin", "CleanCo")
        res = catalog_promotion_service.promote_hr_vendors(threshold=2)
        self.assertEqual(len(res["promoted"]), 1)
        rows = self._catalog_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "hr_promoted")
        self.assertEqual(rows[0]["name"], "CleanCo")
        # attributes carried over, minus the name key
        self.assertEqual(json.loads(rows[0]["attributes_json"]).get("phone"), "123")
        self.assertNotIn("name", json.loads(rows[0]["attributes_json"]))

    def test_one_off_not_promoted(self):
        self._add_custom("co1", "cleaning", "Berlin", "Solo")
        res = catalog_promotion_service.promote_hr_vendors(threshold=2)
        self.assertEqual(len(res["promoted"]), 0)
        self.assertEqual(res["below_threshold"], 1)
        self.assertEqual(len(self._catalog_rows()), 0)

    def test_dedup_single_row(self):
        for co in ("co1", "co2", "co3"):
            self._add_custom(co, "cleaning", "Berlin", "CleanCo")
        res = catalog_promotion_service.promote_hr_vendors(threshold=2)
        self.assertEqual(len(res["promoted"]), 1)
        self.assertEqual(len(self._catalog_rows()), 1)

    def test_idempotent_rerun(self):
        self._add_custom("co1", "cleaning", "Berlin", "CleanCo")
        self._add_custom("co2", "cleaning", "Berlin", "CleanCo")
        catalog_promotion_service.promote_hr_vendors(threshold=2)
        res2 = catalog_promotion_service.promote_hr_vendors(threshold=2)
        self.assertEqual(len(self._catalog_rows()), 1)
        self.assertEqual(len(res2["promoted"]), 0)
        self.assertEqual(len(res2["skipped_existing"]), 1)

    def test_skips_existing_master(self):
        self._seed_master("cleaning", "Berlin", "CleanCo", source="seed")
        self._add_custom("co1", "cleaning", "Berlin", "CleanCo")
        self._add_custom("co2", "cleaning", "Berlin", "CleanCo")
        res = catalog_promotion_service.promote_hr_vendors(threshold=2)
        self.assertEqual(len(res["promoted"]), 0)
        self.assertEqual(len(res["skipped_existing"]), 1)
        self.assertEqual(len(self._catalog_rows()), 1)  # only the pre-seeded row

    def test_case_insensitive_grouping(self):
        # 'CleanCo'/'cleanco' and 'Berlin'/' berlin ' normalise to one group
        self._add_custom("co1", "cleaning", "Berlin", "CleanCo")
        self._add_custom("co2", "cleaning", " berlin ", "cleanco")
        res = catalog_promotion_service.promote_hr_vendors(threshold=2)
        self.assertEqual(len(res["promoted"]), 1)
        self.assertEqual(len(self._catalog_rows()), 1)

    def test_dry_run_writes_nothing(self):
        self._add_custom("co1", "cleaning", "Berlin", "CleanCo")
        self._add_custom("co2", "cleaning", "Berlin", "CleanCo")
        res = catalog_promotion_service.promote_hr_vendors(threshold=2, dry_run=True)
        self.assertEqual(len(res["promoted"]), 1)
        self.assertTrue(res["promoted"][0].get("dry_run"))
        self.assertEqual(len(self._catalog_rows()), 0)


if __name__ == "__main__":
    unittest.main()
