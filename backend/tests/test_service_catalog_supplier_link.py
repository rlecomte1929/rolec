"""AIQ-2095 — service_catalog.upsert_item can LINK a master to a suppliers-registry
row via supplier_id (the join the employee curation/recommendation paths use to reach
a promoted supplier).

Also pins the compatibility property: when supplier_id is None the emitted SQL is
byte-identical to before, so it still works against a service_catalog_items table that
has no supplier_id column (existing SQLite fixtures).
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

from backend.app.services import service_catalog  # noqa: E402

_WITH_SUPPLIER_ID = """
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY, category TEXT, city TEXT, country TEXT, name TEXT,
    attributes_json TEXT, source TEXT, active BOOLEAN, external_id TEXT,
    created_at TEXT, updated_at TEXT, created_by_user_id TEXT, supplier_id TEXT,
    UNIQUE (category, external_id)
)
"""

_WITHOUT_SUPPLIER_ID = """
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY, category TEXT, city TEXT, country TEXT, name TEXT,
    attributes_json TEXT, source TEXT, active BOOLEAN, external_id TEXT,
    created_at TEXT, updated_at TEXT, created_by_user_id TEXT,
    UNIQUE (category, external_id)
)
"""


class UpsertItemSupplierLinkTests(unittest.TestCase):
    def _engine(self, schema: str):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with engine.begin() as conn:
            conn.execute(text(schema))
        return engine

    def _patch_engine(self, engine):
        p = mock.patch.object(service_catalog.db, "engine", engine)
        p.start()
        self.addCleanup(p.stop)

    def test_upsert_links_supplier_and_is_idempotent(self):
        engine = self._engine(_WITH_SUPPLIER_ID)
        self._patch_engine(engine)
        eid = "registry:vc-1:movers:NO"
        service_catalog.upsert_item(
            category="movers", name="Expat Relocation Norway", attributes={},
            source="registry_promoted", city="Oslo", country="NO",
            external_id=eid, supplier_id="vc-1",
        )
        # Re-run: idempotent on (category, external_id) — still ONE row, linked.
        service_catalog.upsert_item(
            category="movers", name="Expat Relocation Norway (AS)", attributes={},
            source="registry_promoted", city="Oslo", country="NO",
            external_id=eid, supplier_id="vc-1",
        )
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT supplier_id, country, source, name FROM service_catalog_items"
            )).mappings().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["supplier_id"], "vc-1")
        self.assertEqual(rows[0]["country"], "NO")
        self.assertEqual(rows[0]["source"], "registry_promoted")

    def test_upsert_without_supplier_id_works_on_legacy_table(self):
        # No supplier_id column at all → the None path must not reference it.
        engine = self._engine(_WITHOUT_SUPPLIER_ID)
        self._patch_engine(engine)
        service_catalog.upsert_item(
            category="banks", name="A Bank", attributes={}, source="manual",
            city="Paris", country="FR", external_id="x-1",
        )
        with engine.connect() as conn:
            n = conn.execute(text("SELECT count(*) FROM service_catalog_items")).scalar()
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
