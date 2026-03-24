from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_config_cap_compare import (
    compare_provider_estimate_to_normalized_cap,
    evaluate_estimates_against_caps,
    normalized_cap_record_from_benefit_row,
    NORMALIZED_CURRENCY_AMOUNT,
)


class PolicyConfigCapCompareTests(unittest.TestCase):
    def test_normalize_currency_row(self) -> None:
        row = {
            "benefit_key": "host_housing_cap",
            "benefit_label": "Housing",
            "category": "compensation_allowances",
            "covered": True,
            "value_type": "currency",
            "amount_value": 5000.0,
            "currency_code": "USD",
            "unit_frequency": "monthly",
            "notes": "Cap note",
            "conditions_json": {},
            "cap_rule_json": {"cap_amount": 3000, "currency": "USD"},
        }
        n = normalized_cap_record_from_benefit_row(row)
        self.assertEqual(n["normalized_cap_type"], NORMALIZED_CURRENCY_AMOUNT)
        self.assertEqual(n["normalized_amount"], 3000.0)
        self.assertEqual(n["currency_code"], "USD")

    def test_compare_under_cap(self) -> None:
        cap = {
            "normalized_cap_type": NORMALIZED_CURRENCY_AMOUNT,
            "normalized_amount": 5000.0,
            "currency_code": "EUR",
        }
        r = compare_provider_estimate_to_normalized_cap(
            estimate_amount=4000, estimate_currency="EUR", normalized_cap=cap
        )
        self.assertTrue(r["supported_comparison"])
        self.assertTrue(r["within_cap"])
        self.assertEqual(r["difference_direction"], "under")

    def test_compare_over_cap(self) -> None:
        cap = {
            "normalized_cap_type": NORMALIZED_CURRENCY_AMOUNT,
            "normalized_amount": 5000.0,
            "currency_code": "EUR",
        }
        r = compare_provider_estimate_to_normalized_cap(
            estimate_amount=5200, estimate_currency="EUR", normalized_cap=cap
        )
        self.assertTrue(r["supported_comparison"])
        self.assertFalse(r["within_cap"])
        self.assertEqual(r["difference_direction"], "over")

    def test_compare_invalid_estimate_amount(self) -> None:
        cap = {
            "normalized_cap_type": NORMALIZED_CURRENCY_AMOUNT,
            "normalized_amount": 5000.0,
            "currency_code": "USD",
        }
        r = compare_provider_estimate_to_normalized_cap(
            estimate_amount=float("nan"), estimate_currency="USD", normalized_cap=cap
        )
        self.assertFalse(r["supported_comparison"])
        self.assertEqual(r.get("reason_unsupported"), "invalid_estimate_amount")

    def test_batch_missing_benefit(self) -> None:
        caps = [
            normalized_cap_record_from_benefit_row(
                {
                    "benefit_key": "a",
                    "benefit_label": "A",
                    "category": "x",
                    "covered": True,
                    "value_type": "currency",
                    "amount_value": 100,
                    "currency_code": "USD",
                    "unit_frequency": "one_time",
                    "notes": None,
                    "conditions_json": {},
                    "cap_rule_json": {},
                }
            )
        ]
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "missing", "amount": 50, "currency": "USD"}], caps
        )
        self.assertFalse(out[0]["matched_cap"])


if __name__ == "__main__":
    unittest.main()
