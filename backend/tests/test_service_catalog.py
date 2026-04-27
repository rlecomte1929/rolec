"""
Tests for backend/services/service_catalog.py — Phase 2a.

Same in-memory SQLite + db.engine swap pattern used by the other Phase 1
tests. Locks the upsert idempotency and the filtered list contract.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services import service_catalog  # noqa: E402


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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id TEXT,
    UNIQUE (category, external_id)
);
"""


class ServiceCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(service_catalog.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

    # ------------------------------------------------------------------
    # upsert
    # ------------------------------------------------------------------
    def test_upsert_inserts_then_updates_in_place(self) -> None:
        first = service_catalog.upsert_item(
            category="schools",
            name="Bavarian International School",
            attributes={"curriculum": "international", "rating": 4.7},
            source="seed",
            city="Munich",
            country="Germany",
            external_id="s-mu1",
        )
        self.assertEqual(first["name"], "Bavarian International School")
        self.assertEqual(first["source"], "seed")
        self.assertTrue(first["active"])

        # Re-upsert with same external_id should update the existing row,
        # not create a second one.
        second = service_catalog.upsert_item(
            category="schools",
            name="Bavarian International School (Munich)",
            attributes={"curriculum": "international", "rating": 4.8},
            source="manual",
            city="Munich",
            country="Germany",
            external_id="s-mu1",
        )
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["source"], "manual")
        self.assertEqual(second["attributes_json"]["rating"], 4.8)

        with self.engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM service_catalog_items "
                    "WHERE category = 'schools' AND external_id = 's-mu1'"
                )
            ).scalar()
        self.assertEqual(count, 1)

    def test_upsert_rejects_invalid_source(self) -> None:
        with self.assertRaises(ValueError):
            service_catalog.upsert_item(
                category="schools",
                name="X",
                attributes={},
                source="bogus",
            )

    def test_upsert_without_external_id_inserts_new_row(self) -> None:
        a = service_catalog.upsert_item(
            category="movers",
            name="Acme Movers",
            attributes={},
            source="manual",
        )
        b = service_catalog.upsert_item(
            category="movers",
            name="Acme Movers",
            attributes={},
            source="manual",
        )
        self.assertNotEqual(a["id"], b["id"])

    # ------------------------------------------------------------------
    # list_items
    # ------------------------------------------------------------------
    def _seed(self) -> None:
        service_catalog.upsert_item(
            category="schools", name="Munich BIS", attributes={}, source="seed",
            city="Munich", country="Germany", external_id="s-mu1",
        )
        service_catalog.upsert_item(
            category="schools", name="UWCSEA", attributes={}, source="seed",
            city="Singapore", country="Singapore", external_id="s-2",
        )
        service_catalog.upsert_item(
            category="movers", name="Santa Fe", attributes={}, source="scraper",
            external_id="m-1",
        )

    def test_list_filter_by_category(self) -> None:
        self._seed()
        rows = service_catalog.list_items(category="schools")
        self.assertEqual(len(rows), 2)
        names = sorted(r["name"] for r in rows)
        self.assertEqual(names, ["Munich BIS", "UWCSEA"])

    def test_list_filter_by_city(self) -> None:
        self._seed()
        rows = service_catalog.list_items(category="schools", city="Munich")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Munich BIS")

    def test_list_filter_by_source(self) -> None:
        self._seed()
        rows = service_catalog.list_items(source="scraper")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "movers")

    def test_list_invalid_source_raises(self) -> None:
        with self.assertRaises(ValueError):
            service_catalog.list_items(source="bogus")

    def test_list_active_only_default_true_skips_inactive(self) -> None:
        self._seed()
        # Mark one inactive
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE service_catalog_items SET active = 0 "
                     "WHERE category = 'schools' AND external_id = 's-2'")
            )
        rows = service_catalog.list_items(category="schools")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["external_id"], "s-mu1")

        rows_all = service_catalog.list_items(category="schools", active_only=False)
        self.assertEqual(len(rows_all), 2)

    # ------------------------------------------------------------------
    # count_by_category_city
    # ------------------------------------------------------------------
    def test_count_by_category_city(self) -> None:
        self._seed()
        self.assertEqual(service_catalog.count_by_category_city("schools", "Munich"), 1)
        self.assertEqual(service_catalog.count_by_category_city("schools", "Singapore"), 1)
        self.assertEqual(service_catalog.count_by_category_city("schools", "Tokyo"), 0)
        # Without a city filter, returns total active rows for the category.
        self.assertEqual(service_catalog.count_by_category_city("schools"), 2)


if __name__ == "__main__":
    unittest.main()
