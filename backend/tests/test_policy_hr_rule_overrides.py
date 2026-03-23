"""HR override layer: effective entitlement traces, merge, resolution, comparison."""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, List

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_hr_rule_override_layer import (  # noqa: E402
    compute_entitlement_value_trace,
    merge_benefit_rule_for_effective_layer,
    merge_benefit_rules_for_comparison_engine,
)
from backend.services.policy_rule_comparison_readiness import (  # noqa: E402
    evaluate_policy_comparison_readiness,
    evaluate_rule_comparison_readiness,
)


def _rule(
    rid: str,
    bk: str,
    *,
    amount: float = 5000.0,
    unit: str = "per_month",
    cur: str = "USD",
) -> Dict[str, Any]:
    return {
        "id": rid,
        "policy_version_id": "v1",
        "benefit_key": bk,
        "benefit_category": "housing",
        "calc_type": "unit_cap",
        "amount_value": amount,
        "amount_unit": unit,
        "currency": cur,
        "frequency": "per_assignment",
        "metadata_json": {},
        "auto_generated": True,
        "review_status": "pending",
    }


class PolicyHRRuleOverrideLayerTests(unittest.TestCase):
    def test_no_override_trace_matches_baseline(self) -> None:
        r = _rule("r1", "temporary_housing", amount=4000.0)
        tr = compute_entitlement_value_trace(r, None)
        self.assertIsNone(tr["hr_override"])
        self.assertEqual(tr["baseline"]["amount_value"], 4000.0)
        self.assertEqual(tr["effective"]["amount_value"], 4000.0)

    def test_increased_temporary_housing_cap(self) -> None:
        r = _rule("r1", "temporary_housing", amount=3500.0)
        ov = {
            "id": "o1",
            "benefit_rule_id": "r1",
            "amount_value_override": 6000.0,
        }
        tr = compute_entitlement_value_trace(r, ov)
        self.assertEqual(tr["baseline"]["amount_value"], 3500.0)
        self.assertEqual(tr["hr_override"]["amount_value_override"], 6000.0)
        self.assertEqual(tr["effective"]["amount_value"], 6000.0)
        merged = merge_benefit_rule_for_effective_layer(r, ov)
        self.assertEqual(merged.get("amount_value"), 6000.0)

    def test_reduced_shipment_allowance(self) -> None:
        r = _rule("r2", "shipment", amount=10000.0, unit="lump_sum")
        ov = {"amount_value_override": 4000.0, "amount_unit_override": "lump_sum"}
        tr = compute_entitlement_value_trace(r, ov)
        self.assertEqual(tr["effective"]["amount_value"], 4000.0)

    def test_service_switched_to_excluded(self) -> None:
        r = _rule("r3", "schooling", amount=15000.0)
        ov = {"service_visibility": "force_excluded"}
        tr = compute_entitlement_value_trace(r, ov)
        self.assertFalse(tr["effective"]["included"])
        merged = merge_benefit_rule_for_effective_layer(r, ov)
        self.assertIsNone(merged.get("amount_value"))

    def test_note_only_override(self) -> None:
        r = _rule("r4", "immigration", amount=3000.0, unit="lump_sum")
        ov = {"hr_notes": "Confirm with legal before finalizing cap."}
        tr = compute_entitlement_value_trace(r, ov)
        self.assertEqual(tr["effective"]["amount_value"], 3000.0)
        self.assertEqual(tr["hr_override"]["hr_notes"], ov["hr_notes"])

    def test_comparison_engine_uses_merged_cap(self) -> None:
        r = _rule("r5", "shipment", amount=8000.0, unit="lump_sum")
        merged = merge_benefit_rule_for_effective_layer(r, {"amount_value_override": 12000.0})
        ev = evaluate_rule_comparison_readiness(merged, rule_kind="benefit_rule")
        self.assertIn(ev.get("level"), ("full", "partial"))


class _FakeComparisonDB:
    def __init__(self, rules: List[Dict[str, Any]], overrides: List[Dict[str, Any]]) -> None:
        self._rules = rules
        self._ov = overrides

    def list_policy_benefit_rules(self, vid: str) -> List[Dict[str, Any]]:
        return list(self._rules)

    def list_policy_exclusions(self, vid: str) -> List[Dict[str, Any]]:
        return []

    def list_hr_benefit_rule_overrides(self, vid: str) -> List[Dict[str, Any]]:
        return list(self._ov)


class PolicyHRRuleOverrideComparisonTests(unittest.TestCase):
    def test_merge_benefit_rules_for_comparison_engine(self) -> None:
        rules = [_rule("x1", "shipment", amount=5000.0, unit="lump_sum")]
        ovs = [
            {
                "benefit_rule_id": "x1",
                "policy_version_id": "v9",
                "amount_value_override": 9000.0,
            }
        ]
        db = _FakeComparisonDB(rules, ovs)
        merged = merge_benefit_rules_for_comparison_engine(db, "v9", rules)
        self.assertEqual(merged[0].get("amount_value"), 9000.0)
        pol = evaluate_policy_comparison_readiness(policy_version_id="v9", db=db)
        self.assertTrue(pol.get("rule_evaluations"))


if __name__ == "__main__":
    unittest.main()
