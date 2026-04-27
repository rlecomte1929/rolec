"""
Tests for backend/services/vendor_curation.py — Phase 2d.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services import vendor_curation  # noqa: E402


SCHEMA = """
CREATE TABLE company_vendor_selections (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    category TEXT NOT NULL,
    destination_city TEXT,
    country TEXT,
    master_item_id TEXT,
    custom_item_json TEXT,
    selected INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id TEXT,
    UNIQUE (company_id, category, destination_city, master_item_id),
    CHECK (
        (master_item_id IS NOT NULL AND custom_item_json IS NULL)
        OR (master_item_id IS NULL AND custom_item_json IS NOT NULL)
    )
);
"""


class VendorCurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(vendor_curation.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

    # ------------------------------------------------------------------
    # upsert_master_selection
    # ------------------------------------------------------------------
    def test_master_toggle_inserts_then_updates_in_place(self) -> None:
        company = str(uuid.uuid4())
        master = str(uuid.uuid4())
        a = vendor_curation.upsert_master_selection(
            company_id=company, category="schools", master_item_id=master,
            selected=True, destination_city="Munich",
        )
        self.assertTrue(a["selected"])
        b = vendor_curation.upsert_master_selection(
            company_id=company, category="schools", master_item_id=master,
            selected=False, destination_city="Munich",
        )
        self.assertEqual(a["id"], b["id"])
        self.assertFalse(b["selected"])

        with self.engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM company_vendor_selections "
                    "WHERE company_id = :co AND master_item_id = :m"
                ),
                {"co": company, "m": master},
            ).scalar()
        self.assertEqual(count, 1)

    def test_master_toggle_scoped_per_city(self) -> None:
        company = str(uuid.uuid4())
        master = str(uuid.uuid4())
        # Same master id but different cities → independent selections.
        vendor_curation.upsert_master_selection(
            company_id=company, category="schools", master_item_id=master,
            selected=True, destination_city="Munich",
        )
        vendor_curation.upsert_master_selection(
            company_id=company, category="schools", master_item_id=master,
            selected=False, destination_city="Berlin",
        )
        rows = vendor_curation.list_curation(
            company_id=company, category="schools", destination_city="Munich"
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["selected"])

    def test_master_toggle_tenant_isolated(self) -> None:
        co_a, co_b = str(uuid.uuid4()), str(uuid.uuid4())
        master = str(uuid.uuid4())
        vendor_curation.upsert_master_selection(
            company_id=co_a, category="schools", master_item_id=master, selected=True,
        )
        vendor_curation.upsert_master_selection(
            company_id=co_b, category="schools", master_item_id=master, selected=False,
        )
        a_view = vendor_curation.list_curation(company_id=co_a, category="schools")
        b_view = vendor_curation.list_curation(company_id=co_b, category="schools")
        self.assertTrue(a_view[0]["selected"])
        self.assertFalse(b_view[0]["selected"])

    # ------------------------------------------------------------------
    # add_custom_vendor / delete_custom_vendor
    # ------------------------------------------------------------------
    def test_add_custom_vendor_round_trip(self) -> None:
        company = str(uuid.uuid4())
        row = vendor_curation.add_custom_vendor(
            company_id=company, category="movers",
            name="Hannah's Trusted Movers",
            attributes={"phone": "+49 89 555 0102", "rating": 4.6},
            destination_city="Munich", country="Germany",
        )
        self.assertIsNone(row["master_item_id"])
        self.assertEqual(row["custom_item_json"]["name"], "Hannah's Trusted Movers")
        self.assertEqual(row["custom_item_json"]["rating"], 4.6)

        rows = vendor_curation.list_curation(company_id=company, category="movers")
        self.assertEqual(len(rows), 1)

    def test_add_custom_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            vendor_curation.add_custom_vendor(
                company_id=str(uuid.uuid4()), category="movers",
                name="   ", attributes={},
            )

    def test_delete_custom_vendor(self) -> None:
        company = str(uuid.uuid4())
        row = vendor_curation.add_custom_vendor(
            company_id=company, category="movers",
            name="X", attributes={},
        )
        self.assertTrue(vendor_curation.delete_custom_vendor(
            company_id=company, row_id=row["id"]
        ))
        self.assertEqual(
            vendor_curation.list_curation(company_id=company, category="movers"),
            [],
        )

    def test_delete_custom_returns_false_for_unknown(self) -> None:
        self.assertFalse(vendor_curation.delete_custom_vendor(
            company_id=str(uuid.uuid4()), row_id=str(uuid.uuid4()),
        ))

    def test_cannot_delete_master_selection(self) -> None:
        company = str(uuid.uuid4())
        row = vendor_curation.upsert_master_selection(
            company_id=company, category="schools",
            master_item_id=str(uuid.uuid4()), selected=True,
        )
        with self.assertRaises(ValueError):
            vendor_curation.delete_custom_vendor(
                company_id=company, row_id=row["id"],
            )

    def test_delete_other_tenant_returns_false(self) -> None:
        co_a, co_b = str(uuid.uuid4()), str(uuid.uuid4())
        row = vendor_curation.add_custom_vendor(
            company_id=co_a, category="movers", name="X", attributes={},
        )
        self.assertFalse(vendor_curation.delete_custom_vendor(
            company_id=co_b, row_id=row["id"],
        ))


if __name__ == "__main__":
    unittest.main()
