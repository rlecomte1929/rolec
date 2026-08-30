"""AIQ-2095 follow-up — the approve_capability hook must LINK an existing same-name
catalog row instead of INSERTing a duplicate the UNIQUE (category, lower(trim(name)))
index would reject (which, being best-effort, was silently swallowed — a no-op).

Covers the two new service_catalog helpers on a real SQLite engine, and the
link-or-insert decision in _ensure_catalog_master_for_capability via mocks.
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import supplier_registry, service_catalog  # noqa: E402

_SCHEMA = """
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY, category TEXT, city TEXT, country TEXT, name TEXT,
    attributes_json TEXT, source TEXT, active BOOLEAN, external_id TEXT,
    created_at TEXT, updated_at TEXT, created_by_user_id TEXT, supplier_id TEXT
);
CREATE UNIQUE INDEX uq_scat_cat_name_ci ON service_catalog_items (category, lower(trim(name)));
"""


class ServiceCatalogLinkHelpersTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        with self.engine.begin() as conn:
            for stmt in _SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            conn.execute(text(
                "INSERT INTO service_catalog_items (id, category, name, source, active, supplier_id, country) "
                "VALUES ('row-1', 'movers', 'Santa Fe Relocation', 'scraper', 1, NULL, NULL)"
            ))
        p = mock.patch.object(service_catalog.db, "engine", self.engine)
        p.start()
        self.addCleanup(p.stop)

    def test_find_by_category_name_is_case_and_trim_insensitive(self):
        self.assertEqual(service_catalog.find_master_by_category_name("movers", "santa fe relocation")["id"], "row-1")
        self.assertEqual(service_catalog.find_master_by_category_name("movers", "  Santa Fe Relocation ")["id"], "row-1")
        self.assertIsNone(service_catalog.find_master_by_category_name("movers", "Nope"))
        self.assertIsNone(service_catalog.find_master_by_category_name("schools", "Santa Fe Relocation"))

    def test_link_sets_supplier_and_fills_country_without_overwriting(self):
        service_catalog.link_supplier_to_master("row-1", "sup-1", country="NO")
        with self.engine.connect() as conn:
            r = conn.execute(text("SELECT supplier_id, active, country FROM service_catalog_items WHERE id='row-1'")).mappings().first()
        self.assertEqual(r["supplier_id"], "sup-1")
        self.assertTrue(r["active"])
        self.assertEqual(r["country"], "NO")
        # COALESCE: a second link with a different country must NOT overwrite the set one.
        service_catalog.link_supplier_to_master("row-1", "sup-1", country="FR")
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT country FROM service_catalog_items WHERE id='row-1'")).scalar(), "NO")


def _cap(country="NO", category="movers", supplier_id="sup-1"):
    return SimpleNamespace(service_category=category, country_code=country, city_name="Oslo", supplier_id=supplier_id)


class ApprovalLinkOrInsertDecisionTests(unittest.TestCase):
    def _run(self, existing):
        with mock.patch.object(service_catalog, "find_master_by_category_name", return_value=existing) as find, \
             mock.patch.object(service_catalog, "link_supplier_to_master") as link, \
             mock.patch.object(service_catalog, "upsert_item") as upsert:
            supplier_registry._ensure_catalog_master_for_capability(_cap(), "Santa Fe Relocation")
        return find, link, upsert

    def test_no_existing_name_row_inserts(self):
        _, link, upsert = self._run(None)
        upsert.assert_called_once()
        link.assert_not_called()

    def test_existing_unlinked_row_is_linked_not_inserted(self):
        _, link, upsert = self._run({"id": "row-1", "supplier_id": None})
        link.assert_called_once()
        self.assertEqual(link.call_args.args[0], "row-1")
        self.assertEqual(link.call_args.args[1], "sup-1")
        upsert.assert_not_called()

    def test_row_linked_to_different_supplier_is_left_alone(self):
        _, link, upsert = self._run({"id": "row-1", "supplier_id": "someone-else"})
        link.assert_not_called()
        upsert.assert_not_called()

    def test_row_already_linked_to_same_supplier_is_noop(self):
        _, link, upsert = self._run({"id": "row-1", "supplier_id": "sup-1"})
        link.assert_not_called()
        upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
