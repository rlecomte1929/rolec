"""Tests: per-rule and policy-level comparison readiness."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_rule_comparison_readiness import (  # noqa: E402
    RULE_COMPARISON_FULL,
    RULE_COMPARISON_NOT_READY,
    RULE_COMPARISON_PARTIAL,
    evaluate_policy_comparison_readiness,
    evaluate_rule_comparison_readiness,
)


class PolicyRuleComparisonReadinessTests(unittest.TestCase):
    def test_full_amount_cap(self) -> None:
        rule = {
            "benefit_key": "temporary_housing",
            "calc_type": "flat_amount",
            "amount_value": 4500,
            "currency": "EUR",
            "raw_text": "Temporary housing up to EUR 4,500",
        }
        r = evaluate_rule_comparison_readiness(rule)
        self.assertEqual(r["level"], RULE_COMPARISON_FULL)
        self.assertTrue(r["supports_budget_delta"])
        self.assertIn("NUMERIC_OR_PERCENT_CAP", r["reasons"])

    def test_full_duration_cap(self) -> None:
        rule = {
            "benefit_key": "temporary_housing",
            "calc_type": "unit_cap",
            "amount_value": 30,
            "amount_unit": "days",
            "currency": "USD",
            "raw_text": "Up to 30 days temporary housing",
        }
        r = evaluate_rule_comparison_readiness(rule)
        self.assertEqual(r["level"], RULE_COMPARISON_FULL)
        self.assertTrue(r["supports_budget_delta"])
        self.assertIn("DURATION_UNIT_CAP", r["reasons"])

    def test_exclusion_only_rule_full(self) -> None:
        excl = {
            "domain": "benefit",
            "benefit_key": "schooling",
            "description": "School search not covered",
        }
        r = evaluate_rule_comparison_readiness(excl, rule_kind="exclusion")
        self.assertEqual(r["level"], RULE_COMPARISON_FULL)
        self.assertFalse(r["supports_budget_delta"])

    def test_coverage_only_partial(self) -> None:
        rule = {
            "benefit_key": "temporary_housing",
            "calc_type": "other",
            "amount_value": None,
            "raw_text": "Temporary housing included for eligible assignees",
            "confidence": 0.8,
        }
        r = evaluate_rule_comparison_readiness(rule)
        self.assertEqual(r["level"], RULE_COMPARISON_PARTIAL)
        self.assertFalse(r["supports_budget_delta"])
        self.assertIn("COVERAGE_LANGUAGE_ONLY", r["reasons"])

    def test_weak_narrative_not_ready_low_confidence(self) -> None:
        rule = {
            "benefit_key": "mobility_premium",
            "calc_type": "other",
            "amount_value": None,
            "raw_text": "Additional support may be available for senior staff",
            "confidence": 0.4,
        }
        r = evaluate_rule_comparison_readiness(rule)
        self.assertEqual(r["level"], RULE_COMPARISON_NOT_READY)
        self.assertIn("VAGUE_LOW_CONFIDENCE", r["reasons"])

    def test_weak_narrative_partial_high_confidence(self) -> None:
        rule = {
            "benefit_key": "mobility_premium",
            "calc_type": "other",
            "amount_value": None,
            "raw_text": "Housing support may be provided depending on case",
            "confidence": 0.9,
        }
        r = evaluate_rule_comparison_readiness(rule)
        self.assertEqual(r["level"], RULE_COMPARISON_PARTIAL)
        self.assertIn("VAGUE_FRAMING", r["reasons"])

    def test_evaluate_policy_three_pillars_full(self) -> None:
        normalized = {
            "benefit_rules": [
                {
                    "benefit_key": "temporary_housing",
                    "calc_type": "flat_amount",
                    "amount_value": 5000,
                    "currency": "USD",
                },
                {
                    "benefit_key": "schooling",
                    "calc_type": "flat_amount",
                    "amount_value": 20000,
                    "currency": "USD",
                },
                {
                    "benefit_key": "shipment",
                    "calc_type": "flat_amount",
                    "amount_value": 10000,
                    "currency": "USD",
                },
            ],
            "exclusions": [],
        }
        p = evaluate_policy_comparison_readiness(normalized=normalized)
        self.assertEqual(p["policy_level"], RULE_COMPARISON_FULL)
        self.assertTrue(p["comparison_ready_strict"])


if __name__ == "__main__":
    unittest.main()
