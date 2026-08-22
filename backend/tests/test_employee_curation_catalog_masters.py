"""AIQ-1857 — an HR-approved catalog vendor must reach the employee.

The curation surface and the recommendation engine rank different vendor populations:

  HR curates  service_catalog_items  (crowdsourced/scraped; measured 2026-08-17:
                                      905 of 967 active rows carry NO supplier_id,
                                      and 46 of 46 for Paris)
  engine emits registry suppliers    (item_id = supplier uuid) or static-dataset rows

``find_masters_by_supplier_or_external_ids`` matches on
``external_id IN ids OR supplier_id::text IN ids``, so a catalog row in neither id space
can never be matched — HR's approvals silently became ``([], "hr_pending")`` and the
employee was told HR was still deciding. Production case 944a3820 (Oslo→Paris) hit this
on all three of housing_agencies, schools and movers at once.

Product decision (2026-08-17): the catalog is authoritative for curation, so an approved
master is surfaced on HR's say-so even when the engine cannot score it.

These tests pin BOTH halves of that: the vendor now appears, and the gates that make it
safe to appear — HR must have selected it, and it must serve this destination.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, List
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["RELOPASS_DISABLE_RATE_LIMITS"] = "1"
os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"

from backend.app.services import employee_recommendations_filter as filt  # noqa: E402
from backend.app.recommendations.types import (  # noqa: E402
    RecommendationItem,
    RecommendationTier,
)

_COMPANY = "c4b5214d-4704-4955-8563-fd7d5784e006"

# Four Paris housing agencies HR approved, exactly as production holds them:
# no supplier_id, slug external_id.
_MASTERS: List[Dict[str, Any]] = [
    {
        "id": "dc939cbb-cd86-4d5c-9528-564781c858db",
        "external_id": "housing_agencies-blueground-paris-1bvyt5n",
        "supplier_id": None,
        "name": "Blueground Paris",
        "category": "housing_agencies",
        "city": "Paris",
        "country": "FR",
        "active": True,
        "attributes_json": {"verified": True},
    },
    {
        "id": "084987a1-3153-402d-9425-82c1fb615683",
        "external_id": "housing_agencies-paris-attitude-ssvy3s",
        "supplier_id": None,
        "name": "Paris Attitude",
        "category": "housing_agencies",
        "city": "Paris",
        "country": "FR",
        "active": True,
        "attributes_json": {},
    },
]

# A vendor in the same company's catalog, approved city-agnostically, but in Madrid.
_MADRID_MASTER: Dict[str, Any] = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "external_id": "housing_agencies-madrid-only-xyz",
    "supplier_id": None,
    "name": "Madrid Only Agency",
    "category": "housing_agencies",
    "city": "Madrid",
    "country": "ES",
    "active": True,
    "attributes_json": {},
}

# A master HR did NOT select — must never surface.
_UNAPPROVED_MASTER: Dict[str, Any] = {
    "id": "bbbbbbbb-0000-0000-0000-000000000002",
    "external_id": "housing_agencies-not-approved-abc",
    "supplier_id": None,
    "name": "Not Approved Agency",
    "category": "housing_agencies",
    "city": "Paris",
    "country": "FR",
    "active": True,
    "attributes_json": {},
}

_ALL_MASTERS = _MASTERS + [_MADRID_MASTER, _UNAPPROVED_MASTER]


def _selection(master: Dict[str, Any], *, order: int = 0, selected: bool = True,
               city: Any = None) -> Dict[str, Any]:
    return {
        "id": f"sel-{master['id'][:8]}",
        "master_item_id": master["id"],
        "custom_item_json": None,
        "selected": selected,
        "display_order": order,
        "destination_city": city,
    }


class HrApprovedCatalogMastersReachEmployeeTests(unittest.TestCase):
    def setUp(self):
        self.selections: List[Dict[str, Any]] = [
            _selection(_MASTERS[0], order=0),
            _selection(_MASTERS[1], order=1),
        ]

        def _fake_find_by_ids(ids):
            wanted = {str(i) for i in ids}
            return [m for m in _ALL_MASTERS if m["id"] in wanted]

        patches = [
            mock.patch.object(filt.vendor_curation, "list_curation",
                              side_effect=lambda **kw: list(self.selections)),
            # The engine produced candidates, but none of them is one of HR's picks —
            # the production shape. (For housing_agencies in Paris it produced none at
            # all; test_no_engine_candidates_at_all covers that.)
            mock.patch.object(filt.service_catalog,
                              "find_masters_by_supplier_or_external_ids",
                              return_value={}),
            mock.patch.object(filt.service_catalog, "find_masters_by_ids",
                              side_effect=_fake_find_by_ids),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _engine_item(self, item_id: str = "vc-some-registry-supplier") -> RecommendationItem:
        return RecommendationItem(
            item_id=item_id,
            name="Some Registry Supplier",
            score=91.0,
            tier=RecommendationTier.BEST_MATCH,
            summary="",
            rationale="",
        )

    def _apply(self, items, city="Paris", country="FR"):
        return filt.apply_hr_curation(
            category="housing_agencies",
            items=items,
            company_id=_COMPANY,
            destination_city=city,
            destination_country=country,
        )

    def test_approved_master_reaches_employee_when_no_engine_candidate_matches(self):
        """The reported failure. Pre-fix this returns ([], 'hr_pending')."""
        items, status = self._apply([self._engine_item()])

        self.assertIsNone(status, "employee was still shown the 'HR is finalizing' state")
        self.assertEqual([i.name for i in items], ["Blueground Paris", "Paris Attitude"])

    def test_no_engine_candidates_at_all_still_surfaces_hr_picks(self):
        """housing_agencies is registry-only, and its FR registry rows are all
        'pending', so search_by_service_destination returned nothing — the engine had
        literally zero candidates. HR's picks must still render."""
        items, status = self._apply([])

        self.assertIsNone(status)
        self.assertEqual(len(items), 2)

    def test_synthesized_item_carries_the_id_shape_the_rfq_path_expects(self):
        items, _ = self._apply([])

        self.assertEqual(items[0].item_id, "housing_agencies-blueground-paris-1bvyt5n")
        self.assertTrue(items[0].metadata["hr_approved_catalog"])
        self.assertTrue(items[0].metadata["unscored"], "a baseline score must not read as an engine result")
        # Provenance is surfaced, never used as a filter — HR's selection is the gate.
        self.assertTrue(items[0].metadata["verified"])
        self.assertFalse(items[1].metadata["verified"])

    def test_hr_display_order_is_respected(self):
        self.selections = [
            _selection(_MASTERS[0], order=9),
            _selection(_MASTERS[1], order=1),
        ]
        items, _ = self._apply([])
        self.assertEqual([i.name for i in items], ["Paris Attitude", "Blueground Paris"])

    # ---- the gates that make surfacing safe -------------------------------

    def test_unapproved_master_never_surfaces(self):
        """The strict default holds: only an explicit selected=true row is shown."""
        self.selections = [
            _selection(_MASTERS[0], order=0),
            _selection(_UNAPPROVED_MASTER, order=1, selected=False),
        ]
        items, _ = self._apply([])
        names = [i.name for i in items]
        self.assertIn("Blueground Paris", names)
        self.assertNotIn("Not Approved Agency", names)

    def test_city_agnostic_selection_does_not_leak_another_citys_vendor(self):
        """A selection row with destination_city=NULL reaches every case. Engine
        candidates were destination-scoped; synthesized ones must be too."""
        self.selections = [
            _selection(_MASTERS[0], order=0, city=None),
            _selection(_MADRID_MASTER, order=1, city=None),
        ]
        items, _ = self._apply([], city="Paris", country="FR")
        names = [i.name for i in items]
        self.assertEqual(names, ["Blueground Paris"])
        self.assertNotIn("Madrid Only Agency", names)

    def test_country_name_vs_code_does_not_hide_an_approved_vendor(self):
        """Destination country arrives as 'France' from some intake paths. Comparing it
        against the catalog's 'FR' must not silently drop the vendor (the 'Germany'[:2]
        == 'GE' != 'DE' trap)."""
        items, _ = self._apply([], city=None, country="France")
        self.assertEqual(len(items), 2)

    def test_destination_gap_is_not_reported_as_hr_still_deciding(self):
        """HR approved only a Madrid vendor; this employee is going to Paris. HR HAS
        decided, so the employee must not be told they are still finalizing."""
        self.selections = [_selection(_MADRID_MASTER, order=0, city=None)]
        items, status = self._apply([], city="Paris", country="FR")

        self.assertEqual(items, [])
        self.assertEqual(status, "hr_destination_gap")

    def test_no_hr_decisions_still_reports_hr_pending(self):
        """The pre-existing contract is untouched when HR has approved nothing."""
        self.selections = []
        items, status = self._apply([])

        self.assertEqual(items, [])
        self.assertEqual(status, "hr_pending")

    def test_catalog_read_failure_degrades_to_pre_fix_behaviour(self):
        """A failed catalog read must not be reported as a destination gap — we did
        not check, so claiming one would be exactly the confident-and-wrong message
        this task removes."""
        with mock.patch.object(filt.service_catalog, "find_masters_by_ids",
                               side_effect=RuntimeError("catalog unreachable")):
            items, status = self._apply([])
        self.assertEqual(items, [])
        self.assertEqual(status, "hr_pending")

    def test_engine_matched_master_is_not_duplicated_by_the_fallback(self):
        """When the engine DID resolve a candidate to an approved master, that master
        must render once, not twice."""
        engine_item = self._engine_item(item_id="housing_agencies-blueground-paris-1bvyt5n")
        with mock.patch.object(
            filt.service_catalog, "find_masters_by_supplier_or_external_ids",
            return_value={"housing_agencies-blueground-paris-1bvyt5n": _MASTERS[0]},
        ):
            items, _ = self._apply([engine_item])

        # Two approved masters, two cards: Blueground came through the engine (so it
        # keeps its scored engine identity, NOT a synthesized twin), Paris Attitude was
        # synthesized. Blueground must not appear a second time as a synthesized card.
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].item_id, "housing_agencies-blueground-paris-1bvyt5n")
        self.assertEqual(items[0].score, 91.0, "the scored engine item must survive")
        self.assertNotIn("hr_approved_catalog", items[0].metadata)
        self.assertEqual(items[1].name, "Paris Attitude")
        self.assertTrue(items[1].metadata["hr_approved_catalog"])


if __name__ == "__main__":
    unittest.main()
