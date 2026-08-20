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


class _CurationFixture(unittest.TestCase):
    """Shared in-memory schema + db patching. No tests of its own: subclasses that only
    need the fixture must not also inherit (and re-run) another suite's assertions."""

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


class HrCatalogRouterTests(_CurationFixture):
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
    # batch resilience: one failing category must not 500 the whole batch
    # ------------------------------------------------------------------
    def test_populate_destination_isolates_failing_category(self) -> None:
        from backend.app.services import catalog_scraper, scrape_safety, service_catalog
        from backend.app.recommendations import registry

        def _pop(category, destination_city, country):
            if category == "movers":
                raise RuntimeError("simulated DB/scraper failure")
            return [{"id": "x"}]

        with mock.patch.object(registry, "list_categories",
                               return_value=[{"key": "movers"}, {"key": "banks"}]), \
             mock.patch.object(scrape_safety, "is_destination_allowlisted", return_value=True), \
             mock.patch.object(scrape_safety, "check_and_increment_quota",
                               return_value={"allowed": True, "limit": 10}), \
             mock.patch.object(catalog_scraper, "_enabled", return_value=True), \
             mock.patch.object(service_catalog, "count_by_category_city", return_value=0), \
             mock.patch.object(catalog_scraper, "populate_destination_catalog", side_effect=_pop), \
             mock.patch.object(catalog_scraper, "backfill_service_types", return_value={"tagged": 0}), \
             mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
            body = hr_catalog_router.PopulateDestinationBody(
                destination_city="Melbourne", country="Australia"
            )
            res = hr_catalog_router.populate_destination_with_ai(
                body=body, user=_user("HR", str(uuid.uuid4()))
            )

        # The request completes (no 500) with a per-category breakdown:
        self.assertEqual(res["status"], "completed")
        per = {r["category"]: r["status"] for r in res["per_category"]}
        self.assertEqual(per.get("movers"), "error", "failing category is isolated, not fatal")
        self.assertEqual(per.get("banks"), "populated", "other categories still succeed")

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

    def test_curation_view_dedupes_duplicate_vendor_names(self) -> None:
        # Two seed batches inserted the same vendors with different external_ids
        # (prod showed each mover twice). The view must collapse by name.
        for ext_id in ("m-1", "uuid-1-for-santa-fe"):
            service_catalog.upsert_item(
                category="movers", name="Santa Fe", attributes={}, source="seed",
                external_id=ext_id,
            )
        service_catalog.upsert_item(
            category="movers", name="Crown", attributes={}, source="seed",
            external_id="m-2",
        )
        view = hr_catalog_router.get_curation_view(
            category="movers", destination_city="Oslo",
            user=_user("HR", str(uuid.uuid4())),
        )
        names = sorted(r["name"] for r in view["rows"] if r["kind"] == "master")
        self.assertEqual(names, ["Crown", "Santa Fe"])  # Santa Fe once, not twice


class CurationRowIdCoercionTests(unittest.TestCase):
    """Regression for the prod-only 500: Postgres returns uuid columns as
    `uuid.UUID` objects, which a bare `str` field rejected. SQLite returns
    them as strings, so this must be asserted at the model level (DB-agnostic)
    rather than via the seeded sqlite fixtures above."""

    def test_uuid_ids_coerced_to_str(self) -> None:
        mid = uuid.uuid4()
        sid = uuid.uuid4()
        row = hr_catalog_router.CurationRow(
            kind="master",
            selection_id=sid,
            master_item_id=mid,
            name="ABC Movers",
            selected=True,
        )
        self.assertEqual(row.master_item_id, str(mid))
        self.assertEqual(row.selection_id, str(sid))
        self.assertIsInstance(row.master_item_id, str)
        self.assertIsInstance(row.selection_id, str)

    def test_none_ids_stay_none(self) -> None:
        row = hr_catalog_router.CurationRow(
            kind="custom", selection_id=None, master_item_id=None,
            name="x", selected=False,
        )
        self.assertIsNone(row.master_item_id)
        self.assertIsNone(row.selection_id)


class CurationCountryScopeTests(_CurationFixture):
    """The catalog proposal must be scopeable to the case's destination country.

    Without this the proposal spans every country in the catalog, so a case bound for Ireland
    could not be shown Ireland's vendors as a destination list. `service_catalog.list_items`
    always accepted `country`; the route did not pass it.
    """

    def _seed_two_countries(self) -> None:
        for ext_id, name, country in (
            ("ie-law-1", "Dublin Immigration Solicitors", "IE"),
            ("ie-law-2", "Liffey Legal", "IE"),
            ("no-law-1", "Oslo Advokat", "NO"),
        ):
            service_catalog.upsert_item(
                category="legal_admin", name=name, attributes={}, source="seed",
                country=country, external_id=ext_id,
            )

    def test_country_scopes_the_proposal(self) -> None:
        self._seed_two_countries()
        view = hr_catalog_router.get_curation_view(
            category="legal_admin",
            country="IE",
            user=_user("HR", str(uuid.uuid4())),
        )
        names = sorted(r["name"] for r in view["rows"] if r["kind"] == "master")
        self.assertEqual(names, ["Dublin Immigration Solicitors", "Liffey Legal"])

    def test_omitting_country_keeps_the_old_unscoped_behaviour(self) -> None:
        self._seed_two_countries()
        view = hr_catalog_router.get_curation_view(
            category="legal_admin",
            user=_user("HR", str(uuid.uuid4())),
        )
        self.assertEqual(len([r for r in view["rows"] if r["kind"] == "master"]), 3)


class CurationVerifiedFlagTests(_CurationFixture):
    """`verified` is lifted out of the attributes blob so the UI can flag unverified vendors."""

    def test_verified_flag_is_surfaced_per_row(self) -> None:
        service_catalog.upsert_item(
            category="legal_admin", name="Accredited Firm", attributes={"verified": True},
            source="seed", country="IE", external_id="ie-v1",
        )
        service_catalog.upsert_item(
            category="legal_admin", name="Unchecked Firm", attributes={"verified": False},
            source="seed", country="IE", external_id="ie-v2",
        )
        service_catalog.upsert_item(
            category="legal_admin", name="No Flag At All", attributes={},
            source="seed", country="IE", external_id="ie-v3",
        )
        view = hr_catalog_router.get_curation_view(
            category="legal_admin", country="IE", user=_user("HR", str(uuid.uuid4())),
        )
        by_name = {r["name"]: r for r in view["rows"]}
        self.assertTrue(by_name["Accredited Firm"]["verified"])
        self.assertFalse(by_name["Unchecked Firm"]["verified"])
        # Absence is not verification.
        self.assertFalse(by_name["No Flag At All"]["verified"])

    def test_unverified_vendors_are_still_offered(self) -> None:
        """Flagged, not hidden — the brief is explicit that they stay selectable."""
        service_catalog.upsert_item(
            category="legal_admin", name="Unchecked Firm", attributes={"verified": False},
            source="seed", country="IE", external_id="ie-v2",
        )
        view = hr_catalog_router.get_curation_view(
            category="legal_admin", country="IE", user=_user("HR", str(uuid.uuid4())),
        )
        self.assertEqual([r["name"] for r in view["rows"]], ["Unchecked Firm"])

    def test_is_verified_helper_rejects_non_bool_truthiness(self) -> None:
        self.assertTrue(hr_catalog_router._is_verified({"verified": True}))
        self.assertTrue(hr_catalog_router._is_verified({"verified": "true"}))
        self.assertFalse(hr_catalog_router._is_verified({"verified": "yes"}))
        self.assertFalse(hr_catalog_router._is_verified({"verified": 1}))
        self.assertFalse(hr_catalog_router._is_verified({}))
        self.assertFalse(hr_catalog_router._is_verified(None))

    def test_hr_custom_vendor_is_never_verified(self) -> None:
        company = str(uuid.uuid4())
        vendor_curation.add_custom_vendor(
            company_id=company,
            category="legal_admin",
            name="HR's Own Solicitor",
            attributes={"verified": True},  # even if the payload claims it
            country="IE",
        )
        view = hr_catalog_router.get_curation_view(
            category="legal_admin", country="IE", user=_user("HR", company),
        )
        custom = [r for r in view["rows"] if r["kind"] == "custom"]
        self.assertEqual(len(custom), 1)
        self.assertFalse(custom[0]["verified"])


class CurationTenantIsolationTests(_CurationFixture):
    """Company A must never see company B's selections or custom vendors."""

    def test_selections_and_customs_do_not_leak_across_companies(self) -> None:
        company_a = str(uuid.uuid4())
        company_b = str(uuid.uuid4())
        item = service_catalog.upsert_item(
            category="legal_admin", name="Shared Catalog Firm", attributes={},
            source="seed", country="IE", external_id="ie-shared",
        )
        # B approves the shared master row and adds a private vendor of its own.
        vendor_curation.upsert_master_selection(
            company_id=company_b, category="legal_admin",
            master_item_id=item["id"], selected=True, country="IE",
        )
        vendor_curation.add_custom_vendor(
            company_id=company_b, category="legal_admin",
            name="B Private Counsel", attributes={}, country="IE",
        )

        view_a = hr_catalog_router.get_curation_view(
            category="legal_admin", country="IE", user=_user("HR", company_a),
        )
        names_a = [r["name"] for r in view_a["rows"]]
        # A sees the shared CATALOG row (that is the point of a catalog) ...
        self.assertIn("Shared Catalog Firm", names_a)
        # ... but never B's private vendor, and never B's decision on the shared row.
        self.assertNotIn("B Private Counsel", names_a)
        shared_for_a = next(r for r in view_a["rows"] if r["name"] == "Shared Catalog Firm")
        self.assertFalse(shared_for_a["selected"])
        self.assertIsNone(shared_for_a["selection_id"])

        # B still sees its own state, proving the isolation is not just an empty read.
        view_b = hr_catalog_router.get_curation_view(
            category="legal_admin", country="IE", user=_user("HR", company_b),
        )
        names_b = [r["name"] for r in view_b["rows"]]
        self.assertIn("B Private Counsel", names_b)
        shared_for_b = next(r for r in view_b["rows"] if r["name"] == "Shared Catalog Firm")
        self.assertTrue(shared_for_b["selected"])


if __name__ == "__main__":
    unittest.main()
