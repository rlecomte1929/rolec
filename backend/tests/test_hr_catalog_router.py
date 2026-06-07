"""
Router-level tests for backend/app/routers/hr_catalog.py — Phase 2d.

Covers the geo-agnostic-vs-geo-bound branch in get_curation_view that
makes movers/banks/etc visible in the HR curation view even when HR
queries with destination_city set.
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

from backend.app.routers import hr_catalog as hr_catalog_router  # noqa: E402
from backend.app.services import service_catalog, vendor_curation  # noqa: E402


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


def _user(role: str, company_id: str):
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "company": company_id,
        "is_admin": False,
    }


class HrCatalogRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        for mod in (service_catalog, vendor_curation, hr_catalog_router):
            patcher = mock.patch.object(mod.db, "engine", self.engine)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Company comes from the user dict's `company` claim. get_profile_record
        # returns a NULL company_id and there is no hr_users row for the synthetic
        # user, so the hr_users-first resolver must fall through to user["company"].
        profile_patcher = mock.patch.object(
            hr_catalog_router.db,
            "get_profile_record",
            side_effect=lambda uid: {"id": uid, "company_id": None},
        )
        profile_patcher.start()
        self.addCleanup(profile_patcher.stop)
        hr_company_patcher = mock.patch.object(
            hr_catalog_router.db, "get_hr_company_id", return_value=None
        )
        hr_company_patcher.start()
        self.addCleanup(hr_company_patcher.stop)

    def _seed_geo_bound(self) -> None:
        # 3 schools — 2 in Munich, 1 in Singapore (geo-bound)
        for ext_id, name, city in (
            ("s-mu1", "BIS Munich", "Munich"),
            ("s-mu2", "MIS Munich", "Munich"),
            ("s-sg1", "UWCSEA", "Singapore"),
        ):
            service_catalog.upsert_item(
                category="schools", name=name, attributes={}, source="seed",
                city=city, external_id=ext_id,
            )

    def _seed_geo_agnostic(self) -> None:
        # 3 movers — no city set (geo-agnostic)
        for ext_id, name in (("m-1", "Santa Fe"), ("m-2", "Pacific"), ("m-3", "Crown")):
            service_catalog.upsert_item(
                category="movers", name=name, attributes={}, source="seed",
                external_id=ext_id,
            )

    # ------------------------------------------------------------------
    # geo-bound: city filter narrows to that city
    # ------------------------------------------------------------------
    def test_geo_bound_category_filters_by_city(self) -> None:
        self._seed_geo_bound()
        view = hr_catalog_router.get_curation_view(
            category="schools",
            destination_city="Munich",
            user=_user("HR", str(uuid.uuid4())),
        )
        names = sorted(r["name"] for r in view["rows"] if r["kind"] == "master")
        self.assertEqual(names, ["BIS Munich", "MIS Munich"])

    # ------------------------------------------------------------------
    # geo-agnostic: city filter MUST NOT hide rows that apply everywhere
    # ------------------------------------------------------------------
    def test_geo_agnostic_category_visible_when_city_supplied(self) -> None:
        # This is the bug the user reported: HR sees "0 items" for movers
        # in Munich even though the master has 3 movers (geo-agnostic).
        self._seed_geo_agnostic()
        view = hr_catalog_router.get_curation_view(
            category="movers",
            destination_city="Munich",
            user=_user("HR", str(uuid.uuid4())),
        )
        names = sorted(r["name"] for r in view["rows"] if r["kind"] == "master")
        self.assertEqual(names, ["Crown", "Pacific", "Santa Fe"])

    def test_mixed_dataset_prefers_geo_match_when_present(self) -> None:
        # If a category has even one geo-bound row, treat it as geo-bound;
        # filtering by city should narrow to that city. Geo-agnostic rows
        # in the same category (would be unusual) get excluded — this is
        # the conservative read of "city was specified, so respect it".
        self._seed_geo_bound()
        # Add a geo-agnostic schools row (atypical, but exercises the branch)
        service_catalog.upsert_item(
            category="schools", name="Generic", attributes={}, source="seed",
            external_id="s-gen",
        )
        view = hr_catalog_router.get_curation_view(
            category="schools",
            destination_city="Munich",
            user=_user("HR", str(uuid.uuid4())),
        )
        names = sorted(r["name"] for r in view["rows"] if r["kind"] == "master")
        self.assertEqual(names, ["BIS Munich", "MIS Munich"])

    def test_geo_bound_no_city_filter_returns_all(self) -> None:
        self._seed_geo_bound()
        view = hr_catalog_router.get_curation_view(
            category="schools",
            destination_city=None,
            user=_user("HR", str(uuid.uuid4())),
        )
        self.assertEqual(len(view["rows"]), 3)


if __name__ == "__main__":
    unittest.main()
