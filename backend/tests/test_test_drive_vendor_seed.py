"""[AIQ-1651] Test-drive provisioning seeds HR vendor curation for the corridor destination.

Provisioning seeds a published policy but never seeded company_vendor_selections, so ~98% of
test-drive companies had none and the employee's Services → Recommendations showed every
category as "Your HR is finalizing providers …" (no shortlist → Request quotes never enables).

These pin `db.seed_company_vendor_selections_for_country` — the seeding that provision() calls:
it writes selected CVS rows pointing at EXISTING admin catalog items (service_catalog_items with
a supplier_id) for the destination country — the exact shape the recommendation filter reads
(list_company_curated_supplier_ids). It must NOT invent suppliers or select items without a
supplier, and it must be idempotent.

SQLite under a `public` schema (ATTACH) so the router's public.-qualified SQL runs unmodified,
mirroring test_case_vendors.py.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.db.companies import CompaniesMixin  # noqa: E402

SCHEMA = """
CREATE TABLE public.service_catalog_items (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  country TEXT,
  city TEXT,
  name TEXT NOT NULL,
  supplier_id TEXT,
  active BOOLEAN NOT NULL DEFAULT 1
);
CREATE TABLE public.company_vendor_selections (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  category TEXT NOT NULL,
  destination_city TEXT,
  country TEXT,
  master_item_id TEXT,
  selected BOOLEAN NOT NULL DEFAULT 1,
  display_order INTEGER NOT NULL DEFAULT 0,
  created_by_user_id TEXT,
  created_at TEXT,
  UNIQUE (company_id, category, destination_city, master_item_id)
);
"""


class _DB(CompaniesMixin):
    """Minimal carrier: the seed method only touches ``self.engine``."""

    def __init__(self, engine) -> None:
        self.engine = engine


def _make_public_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _attach_public(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS public")

    return engine


class SeedVendorSelectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _make_public_engine()
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.db = _DB(self.engine)

    def _catalog(self, category, country, name, supplier_id="sup", active=1):
        cid = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public.service_catalog_items "
                    "(id, category, country, name, supplier_id, active) "
                    "VALUES (:id, :cat, :country, :name, :sup, :active)"
                ),
                {"id": cid, "cat": category, "country": country, "name": name,
                 "sup": supplier_id, "active": active},
            )
        return cid

    def _cvs_rows(self, company_id):
        with self.engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT category, destination_city, country, master_item_id, selected, "
                    "display_order, created_by_user_id "
                    "FROM public.company_vendor_selections WHERE company_id = :cid "
                    "ORDER BY category, display_order"
                ),
                {"cid": company_id},
            ).mappings().all()

    def test_seeds_cvs_for_destination_from_catalog_items_with_a_supplier(self) -> None:
        # NO destination: 2 living_areas + 1 schools that have a supplier → seedable.
        la1 = self._catalog("living_areas", "NO", "Oslo Homes A")
        la2 = self._catalog("living_areas", "NO", "Oslo Homes B")
        sc1 = self._catalog("schools", "NO", "Oslo Intl School")
        # Excluded: no supplier / wrong country / inactive.
        self._catalog("movers", "NO", "Oslo Movers", supplier_id=None)
        self._catalog("living_areas", "DE", "Munich Homes")
        self._catalog("living_areas", "NO", "Oslo Inactive", active=0)

        n = self.db.seed_company_vendor_selections_for_country("co-1", "NO", "Oslo", "hr-1")

        self.assertEqual(n, 3, "only the 3 NO items WITH a supplier seed a CVS row")
        rows = self._cvs_rows("co-1")
        self.assertEqual(len(rows), 3)
        # Every seeded row is a hard-selected curation for the destination, authored by HR.
        for r in rows:
            self.assertTrue(r["selected"])
            self.assertEqual(r["country"], "NO")
            self.assertEqual(r["destination_city"], "Oslo")
            self.assertEqual(r["created_by_user_id"], "hr-1")
        seeded_master_ids = {r["master_item_id"] for r in rows}
        self.assertEqual(seeded_master_ids, {la1, la2, sc1})
        # The no-supplier / other-country / inactive items were NOT selected.
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r["category"], 0)
            by_cat[r["category"]] += 1
        self.assertEqual(by_cat, {"living_areas": 2, "schools": 1})

    def test_seed_is_idempotent(self) -> None:
        self._catalog("living_areas", "NO", "Oslo Homes A")
        first = self.db.seed_company_vendor_selections_for_country("co-1", "NO", "Oslo", "hr-1")
        second = self.db.seed_company_vendor_selections_for_country("co-1", "NO", "Oslo", "hr-1")
        self.assertEqual(first, 1)
        self.assertEqual(second, 0, "re-seeding inserts nothing (ON CONFLICT DO NOTHING)")
        self.assertEqual(len(self._cvs_rows("co-1")), 1)

    def test_zero_when_destination_has_no_catalog_supplier(self) -> None:
        # AE-style: catalog rows exist but none has a supplier → nothing seeds (caller logs it).
        self._catalog("living_areas", "AE", "Dubai Homes", supplier_id=None)
        n = self.db.seed_company_vendor_selections_for_country("co-2", "AE", "Dubai", "hr-2")
        self.assertEqual(n, 0)
        self.assertEqual(self._cvs_rows("co-2"), [])

    def test_per_category_cap(self) -> None:
        for i in range(8):
            self._catalog("living_areas", "NO", f"Home {i:02d}")
        n = self.db.seed_company_vendor_selections_for_country(
            "co-3", "NO", "Oslo", "hr-3", per_category=5
        )
        self.assertEqual(n, 5, "capped at per_category per category")


if __name__ == "__main__":
    unittest.main()
