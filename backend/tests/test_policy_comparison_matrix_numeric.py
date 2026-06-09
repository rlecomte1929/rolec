"""Config-matrix benefits must produce NUMERIC cap-vs-estimate comparisons.

Bridge 2/4 (#488) resolves config-matrix policies into the comparison, but matrix
benefits carried no ``rule_comparison_readiness`` (no policy_version to enrich
from), so every row degraded to ``information_only`` — a cap on file, no number.
``_synthesize_matrix_rule_readiness`` fixes that; this test pins the full path
(synthesize -> legacy alias -> engine) end to end.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_service_comparison import (
    MATRIX_TO_LEGACY_BENEFIT_KEY,
    _synthesize_matrix_rule_readiness,
    _with_legacy_benefit_key_aliases,
)
from backend.app.services.service_comparison_engine import (
    build_entitlements_by_benefit_key,
    compare_selected_services_effective_entitlements,
)


def _matrix_benefit(benefit_key, *, max_value, included=True, currency="EUR", frequency="one_time"):
    return {
        "benefit_key": benefit_key,
        "included": included,
        "min_value": None,
        "standard_value": max_value,
        "max_value": max_value,
        "currency": currency,
        "amount_unit": None,
        "frequency": frequency,
    }


def _compare(benefits, selections):
    enriched = _with_legacy_benefit_key_aliases(_synthesize_matrix_rule_readiness(benefits))
    ent = build_entitlements_by_benefit_key(enriched)
    return compare_selected_services_effective_entitlements(
        selected_services=selections, entitlements_by_benefit_key=ent, version_comparison_ready=True
    )


class SynthesizeReadinessTests(unittest.TestCase):
    def test_numeric_cap_marked_full_with_delta(self):
        out = _synthesize_matrix_rule_readiness([_matrix_benefit("shipment_of_goods", max_value=10000)])
        cr = out[0]["rule_comparison_readiness"]
        self.assertEqual(cr["level"], "full")
        self.assertTrue(cr["supports_budget_delta"])

    def test_no_numeric_cap_stays_partial(self):
        b = _matrix_benefit("settling_in_services", max_value=None)
        cr = _synthesize_matrix_rule_readiness([b])[0]["rule_comparison_readiness"]
        self.assertEqual(cr["level"], "partial")
        self.assertFalse(cr["supports_budget_delta"])

    def test_does_not_mutate_input(self):
        src = [_matrix_benefit("shipment_of_goods", max_value=10000)]
        _synthesize_matrix_rule_readiness(src)
        self.assertNotIn("rule_comparison_readiness", src[0])


class MatrixNumericComparisonTests(unittest.TestCase):
    def test_shipment_within_envelope(self):
        rows = _compare(
            [_matrix_benefit("shipment_of_goods", max_value=10000)],
            [{"service_key": "household_goods_shipment", "estimated_cost": 8000, "currency": "EUR"}],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["comparison_status"], "within_envelope")
        self.assertIsNotNone(rows[0]["delta"])

    def test_shipment_exceeds_envelope(self):
        rows = _compare(
            [_matrix_benefit("shipment_of_goods", max_value=10000)],
            [{"service_key": "household_goods_shipment", "estimated_cost": 12000, "currency": "EUR"}],
        )
        self.assertEqual(rows[0]["comparison_status"], "exceeds_envelope")

    def test_host_housing_cap_aliases_to_temporary_housing(self):
        # The map gap fix: host_housing_cap now resolves the temporary_housing service.
        self.assertEqual(MATRIX_TO_LEGACY_BENEFIT_KEY.get("host_housing_cap"), "temporary_housing")
        rows = _compare(
            [_matrix_benefit("host_housing_cap", max_value=3800, frequency="one_time")],
            [{"service_key": "temporary_housing", "estimated_cost": 3000, "currency": "EUR"}],
        )
        self.assertEqual(rows[0]["comparison_status"], "within_envelope")

    def test_no_numeric_cap_is_information_only_not_numeric(self):
        rows = _compare(
            [_matrix_benefit("settling_in_services", max_value=None)],
            [{"service_key": "home_search", "estimated_cost": 2000, "currency": "EUR"}],
        )
        self.assertEqual(rows[0]["comparison_status"], "information_only")
        self.assertIsNone(rows[0]["delta"])


if __name__ == "__main__":
    unittest.main()
