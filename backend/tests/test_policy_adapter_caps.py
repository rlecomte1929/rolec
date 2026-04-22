"""
Regression: compensation-matrix benefit_keys must populate service-category
caps so the employee Services page budget bar (PackageSummary.tsx) has
something to compare selected service costs against. Prior to the fix,
BENEFIT_KEY_TO_CAP_KEY only carried legacy document-normalized keys; a
company publishing via the Admin → Policy Workspace matrix would land
benefit rows whose keys never matched the table, producing an empty caps
dict and a hidden budget bar.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_adapter import caps_from_resolved_benefits


class PolicyAdapterMatrixCapsTests(unittest.TestCase):
    def test_matrix_relocation_allowance_maps_to_movers_cap(self) -> None:
        """Repro of the exact production scenario: Test March company."""
        benefits = [
            {
                "benefit_key": "relocation_allowance_assignee_partner",
                "included": True,
                "max_value": 5000,
                "currency": "EUR",
            },
            {
                "benefit_key": "relocation_allowance_dependent",
                "included": True,
                "max_value": 1000,
                "currency": "EUR",
            },
        ]
        out = caps_from_resolved_benefits(benefits)
        self.assertEqual(out["currency"], "EUR")
        # Both matrix keys route to the "movers" bucket so the frontend bar
        # has a numeric cap to render against selected mover/shipment costs.
        # Max-across-matching-keys is the existing behavior for all cap_keys.
        self.assertEqual(out["caps"].get("movers"), 5000)

    def test_matrix_repatriation_allowance_also_movers(self) -> None:
        benefits = [
            {
                "benefit_key": "repatriation_allowance_assignee_partner",
                "included": True,
                "max_value": 3000,
                "currency": "USD",
            }
        ]
        out = caps_from_resolved_benefits(benefits)
        self.assertEqual(out["caps"].get("movers"), 3000)

    def test_excluded_matrix_benefits_produce_no_cap(self) -> None:
        benefits = [
            {
                "benefit_key": "relocation_allowance_assignee_partner",
                "included": False,
                "max_value": 5000,
                "currency": "EUR",
            }
        ]
        out = caps_from_resolved_benefits(benefits)
        self.assertEqual(out["caps"], {})

    def test_legacy_keys_still_work(self) -> None:
        """The legacy (document-normalized) path must keep working."""
        benefits = [
            {"benefit_key": "temporary_housing", "included": True, "max_value": 4000, "currency": "USD"},
            {"benefit_key": "shipment", "included": True, "max_value": 8000, "currency": "USD"},
            {"benefit_key": "schooling", "included": True, "max_value": 20000, "currency": "USD"},
        ]
        out = caps_from_resolved_benefits(benefits)
        self.assertEqual(out["caps"]["housing"], 4000)
        self.assertEqual(out["caps"]["movers"], 8000)
        self.assertEqual(out["caps"]["schools"], 20000)


if __name__ == "__main__":
    unittest.main()
