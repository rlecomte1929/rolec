"""
Tests for backend/services/employee_recommendations_filter.py — Phase 2c.

Locks the strict authority chain: an employee sees a master vendor only
when HR has explicitly approved it; HR custom vendors get appended;
no HR approvals → empty list with hr_pending status.
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

from backend.app.recommendations.types import (  # noqa: E402
    RecommendationExplanation,
    RecommendationItem,
    RecommendationTier,
)
from backend.app.services import employee_recommendations_filter as flt  # noqa: E402
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
    supplier_id TEXT,
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


def _rec(item_id: str, name: str, score: float = 90.0) -> RecommendationItem:
    return RecommendationItem(
        item_id=item_id,
        name=name,
        score=score,
        tier=RecommendationTier.BEST_MATCH,
        summary="ok",
        rationale="ok",
        breakdown={},
        pros=[],
        cons=[],
        metadata={},
        explanation=RecommendationExplanation(),
    )


class EmployeeRecommendationsFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        for mod in (service_catalog, vendor_curation):
            patcher = mock.patch.object(mod.db, "engine", self.engine)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _seed_three_movers(self) -> dict:
        masters = {}
        for ext_id, name in (("m-1", "Acme"), ("m-2", "Beta"), ("m-3", "Gamma")):
            row = service_catalog.upsert_item(
                category="movers", name=name, attributes={}, source="seed",
                external_id=ext_id,
            )
            masters[ext_id] = row
        return masters

    # ------------------------------------------------------------------
    # No tenant context → pass through (legacy behavior)
    # ------------------------------------------------------------------
    def test_no_company_id_passes_through(self) -> None:
        items = [_rec("m-1", "Acme"), _rec("m-2", "Beta")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=None, destination_city=None,
        )
        self.assertEqual([i.item_id for i in out], ["m-1", "m-2"])
        self.assertIsNone(status)

    # ------------------------------------------------------------------
    # Strict default: HR has made zero decisions → empty + hr_pending
    # ------------------------------------------------------------------
    def test_no_hr_decisions_returns_hr_pending(self) -> None:
        self._seed_three_movers()
        company = str(uuid.uuid4())
        items = [_rec("m-1", "Acme"), _rec("m-2", "Beta"), _rec("m-3", "Gamma")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city="Munich",
        )
        self.assertEqual(out, [])
        self.assertEqual(status, "hr_pending")

    # ------------------------------------------------------------------
    # HR has approved 2 of 3 → only those 2 visible
    # ------------------------------------------------------------------
    def test_hr_approved_subset_only(self) -> None:
        masters = self._seed_three_movers()
        company = str(uuid.uuid4())
        # Approve m-1 and m-3
        for ext_id, want in (("m-1", True), ("m-3", True)):
            vendor_curation.upsert_master_selection(
                company_id=company, category="movers",
                master_item_id=masters[ext_id]["id"], selected=want,
            )
        # m-2 has no HR row (default-off)
        items = [_rec("m-1", "Acme"), _rec("m-2", "Beta"), _rec("m-3", "Gamma")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city=None,
        )
        ids = sorted(i.item_id for i in out)
        self.assertEqual(ids, ["m-1", "m-3"])
        self.assertIsNone(status)

    # ------------------------------------------------------------------
    # Explicit HR rejection (selected=false) hides the item
    # ------------------------------------------------------------------
    def test_hr_explicit_off_hides(self) -> None:
        masters = self._seed_three_movers()
        company = str(uuid.uuid4())
        # Approve m-1, explicitly hide m-2, leave m-3 undecided
        vendor_curation.upsert_master_selection(
            company_id=company, category="movers",
            master_item_id=masters["m-1"]["id"], selected=True,
        )
        vendor_curation.upsert_master_selection(
            company_id=company, category="movers",
            master_item_id=masters["m-2"]["id"], selected=False,
        )
        items = [_rec("m-1", "Acme"), _rec("m-2", "Beta"), _rec("m-3", "Gamma")]
        out, _ = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city=None,
        )
        self.assertEqual([i.item_id for i in out], ["m-1"])

    # ------------------------------------------------------------------
    # HR custom vendors get appended even when zero master approvals
    # ------------------------------------------------------------------
    def test_custom_vendor_appended(self) -> None:
        self._seed_three_movers()
        company = str(uuid.uuid4())
        # No master approvals; one custom vendor.
        vendor_curation.add_custom_vendor(
            company_id=company, category="movers",
            name="Hannah's Trusted Movers",
            attributes={"notes": "Family-recommended."},
            destination_city="Munich",
        )
        items = [_rec("m-1", "Acme"), _rec("m-2", "Beta")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city="Munich",
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].name, "Hannah's Trusted Movers")
        self.assertTrue(out[0].metadata.get("hr_custom"))
        self.assertTrue(out[0].metadata.get("company_preferred"))
        self.assertIsNone(status)

    def test_custom_plus_master_combined(self) -> None:
        masters = self._seed_three_movers()
        company = str(uuid.uuid4())
        vendor_curation.upsert_master_selection(
            company_id=company, category="movers",
            master_item_id=masters["m-1"]["id"], selected=True,
        )
        vendor_curation.add_custom_vendor(
            company_id=company, category="movers", name="HR-pref", attributes={},
        )
        items = [_rec("m-1", "Acme"), _rec("m-2", "Beta")]
        out, _ = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city=None,
        )
        names = [i.name for i in out]
        self.assertIn("Acme", names)
        self.assertIn("HR-pref", names)
        self.assertEqual(len(out), 2)

    # ------------------------------------------------------------------
    # Items not in master are dropped (legacy data without backfill)
    # ------------------------------------------------------------------
    def test_drops_items_with_no_master_row(self) -> None:
        self._seed_three_movers()
        company = str(uuid.uuid4())
        # Approve m-1 only.
        master = service_catalog.find_master_by_external_id("movers", "m-1")
        vendor_curation.upsert_master_selection(
            company_id=company, category="movers",
            master_item_id=master["id"], selected=True,
        )
        # Plugin returned a 4th item that's not in the master at all.
        items = [
            _rec("m-1", "Acme"),
            _rec("m-99", "Ghost from JSON dataset"),
        ]
        out, _ = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city=None,
        )
        self.assertEqual([i.item_id for i in out], ["m-1"])

    # ------------------------------------------------------------------
    # [AIQ-1530] The employee sees HR's curated vendors in HR's display_order,
    # NOT the engine's score order. "A vendor HR ranked first sorts first."
    # ------------------------------------------------------------------
    def _set_display_order(self, company: str, master_id: str, order: int) -> None:
        # upsert_master_selection doesn't expose display_order; set it directly.
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE company_vendor_selections SET display_order = :o "
                    "WHERE company_id = :co AND master_item_id = :mid"
                ),
                {"o": order, "co": company, "mid": master_id},
            )

    def test_orders_by_hr_display_order_not_engine_score(self) -> None:
        masters = self._seed_three_movers()
        company = str(uuid.uuid4())
        for ext_id in ("m-1", "m-2", "m-3"):
            vendor_curation.upsert_master_selection(
                company_id=company, category="movers",
                master_item_id=masters[ext_id]["id"], selected=True,
            )
        # HR's ranking: Gamma(1st), Acme(2nd), Beta(3rd).
        self._set_display_order(company, masters["m-3"]["id"], 0)
        self._set_display_order(company, masters["m-1"]["id"], 1)
        self._set_display_order(company, masters["m-2"]["id"], 2)
        # Engine hands them back in a DIFFERENT order (by its own score).
        items = [_rec("m-1", "Acme", 95.0), _rec("m-2", "Beta", 90.0), _rec("m-3", "Gamma", 50.0)]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city=None,
        )
        # HR's display_order wins — Gamma first even though it scored lowest.
        self.assertEqual([i.item_id for i in out], ["m-3", "m-1", "m-2"])
        self.assertIsNone(status)

    # ------------------------------------------------------------------
    # [AIQ-1553] Postgres returns uuid columns as uuid.UUID objects, while
    # service_catalog._row_to_item stringifies the master id. The curation row
    # mapper must ALSO stringify, or `str(master_id) in {UUID(master_item_id)}`
    # is always False and every HR-approved master is dropped to hr_pending
    # (the AIQ-1550 layer-3 defect). SQLite returns uuids as text, so only an
    # explicit UUID-object row reproduces the prod mismatch.
    # ------------------------------------------------------------------
    def test_row_to_dict_stringifies_uuid_columns(self) -> None:
        rid, cid, mid, uid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        row = {
            "id": rid, "company_id": cid, "master_item_id": mid,
            "created_by_user_id": uid, "category": "movers",
            "destination_city": None, "custom_item_json": None,
            "selected": 1, "display_order": 0,
        }
        d = vendor_curation._row_to_dict(row)
        self.assertIsInstance(d["master_item_id"], str)
        self.assertEqual(d["master_item_id"], str(mid))
        self.assertEqual(d["company_id"], str(cid))
        self.assertEqual(d["id"], str(rid))
        self.assertEqual(d["created_by_user_id"], str(uid))
        # The str master_item_id now matches service_catalog's stringified master id,
        # so the set-membership test in apply_hr_curation keeps the approved master.
        self.assertIn(str(mid), {d["master_item_id"]})
        self.assertIs(d["selected"], True)

    def test_equal_display_order_preserves_engine_order(self) -> None:
        # The default (all display_order=0) must not reshuffle — engine order is the tie-break,
        # so behavior for un-ranked curation is unchanged.
        masters = self._seed_three_movers()
        company = str(uuid.uuid4())
        for ext_id in ("m-1", "m-2", "m-3"):
            vendor_curation.upsert_master_selection(
                company_id=company, category="movers",
                master_item_id=masters[ext_id]["id"], selected=True,
            )
        items = [_rec("m-2", "Beta"), _rec("m-1", "Acme"), _rec("m-3", "Gamma")]
        out, _ = flt.apply_hr_curation(
            category="movers", items=items, company_id=company, destination_city=None,
        )
        self.assertEqual([i.item_id for i in out], ["m-2", "m-1", "m-3"])

    # ------------------------------------------------------------------
    # AIQ-1688: registry items are keyed item_id=supplier UUID, but their masters
    # are keyed external_id='m-N' with supplier_id=<that UUID>. Curation must resolve
    # via supplier_id, else HR-approved movers render as an empty category.
    # ------------------------------------------------------------------
    def _insert_master_with_supplier(
        self, *, external_id: str, supplier_id: str, name: str = "Asian Tigers"
    ) -> str:
        master_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO service_catalog_items "
                    "(id, category, name, external_id, supplier_id, active) "
                    "VALUES (:id, 'movers', :name, :ext, :sup, 1)"
                ),
                {"id": master_id, "name": name, "ext": external_id, "sup": supplier_id},
            )
        return master_id

    def test_registry_item_resolves_to_master_via_supplier_id(self) -> None:
        supplier_uuid = str(uuid.uuid4())
        master_id = self._insert_master_with_supplier(
            external_id="m-1", supplier_id=supplier_uuid
        )
        company = str(uuid.uuid4())
        vendor_curation.upsert_master_selection(
            company_id=company, category="movers",
            master_item_id=master_id, selected=True,
        )
        # Engine serves the registry representation (item_id = supplier UUID).
        items = [_rec(supplier_uuid, "Asian Tigers")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company,
            destination_city="Singapore",
        )
        self.assertIsNone(status)  # NOT hr_pending — the approved item resolved
        self.assertEqual([i.item_id for i in out], [supplier_uuid])

    def test_registry_and_static_twin_dedup_to_one(self) -> None:
        # Both the registry item (item_id=UUID) and its legacy static twin (item_id='m-1')
        # resolve to the SAME approved master → only ONE renders (the first/highest-ranked).
        supplier_uuid = str(uuid.uuid4())
        master_id = self._insert_master_with_supplier(
            external_id="m-1", supplier_id=supplier_uuid
        )
        company = str(uuid.uuid4())
        vendor_curation.upsert_master_selection(
            company_id=company, category="movers",
            master_item_id=master_id, selected=True,
        )
        items = [_rec(supplier_uuid, "Asian Tigers (registry)"), _rec("m-1", "Asian Tigers (static)")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company,
            destination_city="Singapore",
        )
        self.assertIsNone(status)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].item_id, supplier_uuid)

    def test_unapproved_master_still_hidden_via_supplier_id(self) -> None:
        # Guard the allowlist: matching by supplier_id must NOT bypass HR approval.
        supplier_uuid = str(uuid.uuid4())
        self._insert_master_with_supplier(external_id="m-1", supplier_id=supplier_uuid)
        company = str(uuid.uuid4())  # HR approves NOTHING
        items = [_rec(supplier_uuid, "Asian Tigers")]
        out, status = flt.apply_hr_curation(
            category="movers", items=items, company_id=company,
            destination_city="Singapore",
        )
        self.assertEqual(out, [])
        self.assertEqual(status, "hr_pending")


if __name__ == "__main__":
    unittest.main()
