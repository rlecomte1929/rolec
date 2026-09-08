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

from backend.app.services import vendor_curation  # noqa: E402


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

-- [F-2] The guard in upsert_master_selection reads this table to compare the selection's
-- country against the catalog item's own. Without it every write would hit "no such table".
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY,
    name TEXT,
    category TEXT,
    city TEXT,
    country TEXT,
    active INTEGER NOT NULL DEFAULT 1
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

    def _catalog_item(self, item_id: str, name: str, country, city=None) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO service_catalog_items (id, name, category, city, country) "
                     "VALUES (:i, :n, 'movers', :c, :co)"),
                {"i": item_id, "n": name, "c": city, "co": country},
            )

    # ------------------------------------------------------------------
    # [F-2] country agreement at the WRITE path
    #
    # 177 Norwegian companies had approved a Sydney mover because nothing ever
    # compared the selection's country with the catalog item's. Cross-country rows
    # were still arriving daily when this guard was written, which is why it matters
    # more than any one-off cleanup.
    # ------------------------------------------------------------------
    def test_a_vendor_in_the_wrong_country_is_refused(self) -> None:
        master = str(uuid.uuid4())
        self._catalog_item(master, "Santa Fe Relocation", "AU", city="Sydney")
        with self.assertRaises(vendor_curation.CountryMismatch) as ctx:
            vendor_curation.upsert_master_selection(
                company_id=str(uuid.uuid4()), category="movers", master_item_id=master,
                selected=True, destination_city="Oslo", country="NO",
            )
        self.assertIn("AU", str(ctx.exception))
        self.assertIn("NO", str(ctx.exception))

    def test_a_refused_toggle_leaves_no_row_behind(self) -> None:
        """The check runs before the INSERT, inside the same transaction."""
        company, master = str(uuid.uuid4()), str(uuid.uuid4())
        self._catalog_item(master, "Santa Fe Relocation", "AU")
        with self.assertRaises(vendor_curation.CountryMismatch):
            vendor_curation.upsert_master_selection(
                company_id=company, category="movers", master_item_id=master,
                selected=True, country="NO",
            )
        with self.engine.begin() as conn:
            n = conn.execute(
                text("SELECT count(*) FROM company_vendor_selections WHERE company_id = :c"),
                {"c": company},
            ).scalar()
        self.assertEqual(n, 0)

    def test_a_matching_country_is_allowed(self) -> None:
        master = str(uuid.uuid4())
        self._catalog_item(master, "Alfa Mobility Norway", "NO", city="Oslo")
        row = vendor_curation.upsert_master_selection(
            company_id=str(uuid.uuid4()), category="movers", master_item_id=master,
            selected=True, destination_city="Oslo", country="NO",
        )
        self.assertTrue(row["selected"])

    def test_case_and_whitespace_do_not_make_a_false_mismatch(self) -> None:
        master = str(uuid.uuid4())
        self._catalog_item(master, "Alfa Mobility Norway", "no")
        row = vendor_curation.upsert_master_selection(
            company_id=str(uuid.uuid4()), category="movers", master_item_id=master,
            selected=True, country=" NO ",
        )
        self.assertTrue(row["selected"])

    def test_an_unknown_country_is_permitted_not_rejected(self) -> None:
        """service_catalog_items.country is 981 of 985 populated. "We do not know" is not
        evidence of a mismatch, and rejecting on absence would block legitimate saves."""
        master = str(uuid.uuid4())
        self._catalog_item(master, "Unlocated Vendor", None)
        row = vendor_curation.upsert_master_selection(
            company_id=str(uuid.uuid4()), category="movers", master_item_id=master,
            selected=True, country="NO",
        )
        self.assertTrue(row["selected"])

    def test_a_selection_with_no_country_is_permitted(self) -> None:
        master = str(uuid.uuid4())
        self._catalog_item(master, "Santa Fe Relocation", "AU")
        row = vendor_curation.upsert_master_selection(
            company_id=str(uuid.uuid4()), category="movers", master_item_id=master,
            selected=True, country=None,
        )
        self.assertTrue(row["selected"])

    def test_an_unknown_master_item_is_permitted(self) -> None:
        """A master id with no catalog row cannot be compared against anything."""
        row = vendor_curation.upsert_master_selection(
            company_id=str(uuid.uuid4()), category="movers",
            master_item_id=str(uuid.uuid4()), selected=True, country="NO",
        )
        self.assertTrue(row["selected"])

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

    # ------------------------------------------------------------------
    # AIQ-1457 — city matching must tolerate case/whitespace/diacritic drift
    # between HR's picker city and the employee's intake city, or HR-curated
    # vendors silently vanish and the employee sees "HR is finalizing providers".
    # ------------------------------------------------------------------
    def _seed_city(self, company: str, city: str) -> None:
        vendor_curation.add_custom_vendor(
            company_id=company, category="movers",
            name="Hannah's Trusted Movers", attributes={},
            destination_city=city,
        )

    def test_list_curation_matches_city_case_insensitively(self) -> None:
        company = str(uuid.uuid4())
        self._seed_city(company, "Zürich")
        rows = vendor_curation.list_curation(
            company_id=company, category="movers", destination_city="zürich",
        )
        self.assertEqual(len(rows), 1)

    def test_list_curation_matches_city_ignoring_diacritics(self) -> None:
        # The reported bug: HR picked "Zürich", the case city is "Zurich".
        company = str(uuid.uuid4())
        self._seed_city(company, "Zürich")
        rows = vendor_curation.list_curation(
            company_id=company, category="movers", destination_city="Zurich",
        )
        self.assertEqual(len(rows), 1)

    def test_list_curation_matches_city_ignoring_whitespace(self) -> None:
        company = str(uuid.uuid4())
        self._seed_city(company, "Munich")
        rows = vendor_curation.list_curation(
            company_id=company, category="movers", destination_city="  Munich  ",
        )
        self.assertEqual(len(rows), 1)

    def test_list_curation_still_excludes_a_different_city(self) -> None:
        company = str(uuid.uuid4())
        self._seed_city(company, "Munich")
        rows = vendor_curation.list_curation(
            company_id=company, category="movers", destination_city="Berlin",
        )
        self.assertEqual(rows, [])

    def test_list_curation_null_city_rows_always_returned(self) -> None:
        # Company-wide (city-agnostic) curation must show for any destination.
        company = str(uuid.uuid4())
        self._seed_city(company, None)
        rows = vendor_curation.list_curation(
            company_id=company, category="movers", destination_city="Anywhere",
        )
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
