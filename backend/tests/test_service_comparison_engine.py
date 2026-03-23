"""Unit tests for effective-entitlement service comparison engine."""
from __future__ import annotations

import os
import sys
import unittest
from typing import List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_rule_comparison_readiness import (
    RULE_COMPARISON_FULL,
    RULE_COMPARISON_NOT_READY,
    RULE_COMPARISON_PARTIAL,
)
from backend.services.service_comparison_engine import (
    compare_selected_services_effective_entitlements,
    map_case_service_to_canonical_selection,
)


def _cr(level: str, *, supports_budget_delta: bool = False, reasons: Optional[List[str]] = None) -> dict:
    return {"level": level, "supports_budget_delta": supports_budget_delta, "reasons": reasons or []}


class ServiceComparisonEngineTests(unittest.TestCase):
    def test_within_envelope(self) -> None:
        sel = [{"service_key": "temporary_housing", "estimated_cost": 5000.0, "currency": "USD"}]
        ent = {
            "temporary_housing": {
                "benefit_key": "temporary_housing",
                "included": True,
                "max_value": 10000,
                "currency": "USD",
                "amount_unit": "flat",
                "approval_required": False,
                "rule_comparison_readiness": _cr(RULE_COMPARISON_FULL, supports_budget_delta=True, reasons=["NUMERIC_OR_PERCENT_CAP"]),
            }
        }
        out = compare_selected_services_effective_entitlements(
            selected_services=sel, entitlements_by_benefit_key=ent, version_comparison_ready=True
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["comparison_status"], "within_envelope")
        self.assertEqual(out[0]["delta"], -5000.0)
        self.assertEqual(out[0]["coverage_status"], "included")

    def test_exceeds_envelope(self) -> None:
        sel = [{"service_key": "school_search", "estimated_cost": 8000.0, "currency": "USD"}]
        ent = {
            "schooling": {
                "benefit_key": "schooling",
                "included": True,
                "standard_value": 5000,
                "currency": "USD",
                "amount_unit": "flat",
                "approval_required": True,
                "rule_comparison_readiness": _cr(RULE_COMPARISON_FULL, supports_budget_delta=True),
            }
        }
        out = compare_selected_services_effective_entitlements(
            selected_services=sel, entitlements_by_benefit_key=ent, version_comparison_ready=True
        )
        self.assertEqual(out[0]["comparison_status"], "exceeds_envelope")
        self.assertEqual(out[0]["delta"], 3000.0)
        self.assertTrue(out[0]["approval_required"])

    def test_excluded_deterministic(self) -> None:
        sel = [{"service_key": "household_goods_shipment", "estimated_cost": 999.0, "currency": "USD"}]
        ent = {
            "shipment": {
                "benefit_key": "shipment",
                "included": False,
                "rule_comparison_readiness": _cr(RULE_COMPARISON_FULL, supports_budget_delta=False, reasons=["RESOLVED_EXCLUDED"]),
            }
        }
        out = compare_selected_services_effective_entitlements(selected_services=sel, entitlements_by_benefit_key=ent)
        self.assertEqual(out[0]["comparison_status"], "excluded")
        self.assertIsNone(out[0]["delta"])
        self.assertEqual(out[0]["coverage_status"], "excluded")

    def test_conditional_no_numeric_cap(self) -> None:
        sel = [{"service_key": "visa_support", "estimated_cost": 2000.0, "currency": "USD"}]
        ent = {
            "immigration": {
                "benefit_key": "immigration",
                "included": True,
                "rule_comparison_readiness": _cr(RULE_COMPARISON_FULL, supports_budget_delta=True),
            }
        }
        out = compare_selected_services_effective_entitlements(selected_services=sel, entitlements_by_benefit_key=ent)
        self.assertEqual(out[0]["comparison_status"], "conditional")
        self.assertIsNone(out[0]["delta"])
        self.assertEqual(out[0]["coverage_status"], "conditional")

    def test_coverage_only_information_only(self) -> None:
        sel = [{"service_key": "home_search", "estimated_cost": 1000.0, "currency": "USD"}]
        ent = {
            "relocation_services": {
                "benefit_key": "relocation_services",
                "included": True,
                "rule_comparison_readiness": _cr(
                    RULE_COMPARISON_PARTIAL,
                    supports_budget_delta=False,
                    reasons=["RESOLVED_COVERAGE_ONLY"],
                ),
            }
        }
        out = compare_selected_services_effective_entitlements(selected_services=sel, entitlements_by_benefit_key=ent)
        self.assertEqual(out[0]["comparison_status"], "information_only")
        self.assertIsNone(out[0]["delta"])

    def test_weak_narrative_not_enough_policy_data(self) -> None:
        sel = [{"service_key": "temporary_housing", "estimated_cost": 1000.0, "currency": "USD"}]
        ent = {
            "temporary_housing": {
                "benefit_key": "temporary_housing",
                "included": True,
                "max_value": 5000,
                "currency": "USD",
                "rule_comparison_readiness": _cr(
                    RULE_COMPARISON_NOT_READY,
                    supports_budget_delta=False,
                    reasons=["VAGUE_LOW_CONFIDENCE"],
                ),
            }
        }
        out = compare_selected_services_effective_entitlements(selected_services=sel, entitlements_by_benefit_key=ent)
        self.assertEqual(out[0]["comparison_status"], "not_enough_policy_data")
        self.assertIsNone(out[0]["delta"])

    def test_no_delta_on_currency_mismatch(self) -> None:
        sel = [{"service_key": "temporary_housing", "estimated_cost": 1000.0, "currency": "EUR"}]
        ent = {
            "temporary_housing": {
                "benefit_key": "temporary_housing",
                "included": True,
                "max_value": 5000,
                "currency": "USD",
                "amount_unit": "flat",
                "rule_comparison_readiness": _cr(RULE_COMPARISON_FULL, supports_budget_delta=True),
            }
        }
        out = compare_selected_services_effective_entitlements(selected_services=sel, entitlements_by_benefit_key=ent)
        self.assertEqual(out[0]["comparison_status"], "conditional")
        self.assertIsNone(out[0]["delta"])
        self.assertIn("currency", out[0]["explanation"].lower())

    def test_version_not_ready_downgrades_envelope(self) -> None:
        sel = [{"service_key": "temporary_housing", "estimated_cost": 1000.0, "currency": "USD"}]
        ent = {
            "temporary_housing": {
                "benefit_key": "temporary_housing",
                "included": True,
                "max_value": 5000,
                "currency": "USD",
                "amount_unit": "flat",
                "rule_comparison_readiness": _cr(RULE_COMPARISON_FULL, supports_budget_delta=True),
            }
        }
        out = compare_selected_services_effective_entitlements(
            selected_services=sel,
            entitlements_by_benefit_key=ent,
            version_comparison_ready=False,
        )
        self.assertEqual(out[0]["comparison_status"], "not_enough_policy_data")
        self.assertIsNone(out[0]["delta"])

    def test_map_case_service_to_canonical_selection(self) -> None:
        m = map_case_service_to_canonical_selection(
            {"category": "movers", "selected": True, "estimated_cost": 1200, "currency": "USD"}
        )
        self.assertIsNotNone(m)
        assert m is not None
        self.assertEqual(m["service_key"], "household_goods_shipment")
        self.assertEqual(m["estimated_cost"], 1200.0)


if __name__ == "__main__":
    unittest.main()
