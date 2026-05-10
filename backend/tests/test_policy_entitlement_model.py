"""Sanity checks for canonical entitlement constants and legacy bridges."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_entitlement_model import (  # noqa: E402
    CANONICAL_ENTITLEMENT_RULE_JSON_SCHEMA,
    CANONICAL_SERVICE_KEYS,
    CanonicalServiceKey,
    canonical_service_for_legacy_benefit_key,
    infer_rule_strength,
    legacy_benefit_key_for_canonical_service,
)


class PolicyEntitlementModelTests(unittest.TestCase):
    def test_minimum_service_keys_present(self) -> None:
        required = {
            "visa_support",
            "temporary_housing",
            "home_search",
            "school_search",
            "household_goods_shipment",
            "tax_briefing",
            "tax_filing_support",
            "destination_orientation",
            "spouse_support",
            "language_training",
        }
        self.assertTrue(required.issubset(CANONICAL_SERVICE_KEYS))

    def test_legacy_bridge_round_trip_for_housing(self) -> None:
        sk = canonical_service_for_legacy_benefit_key("temporary_housing")
        self.assertEqual(sk, CanonicalServiceKey.TEMPORARY_HOUSING.value)
        self.assertEqual(legacy_benefit_key_for_canonical_service(sk), "temporary_housing")

    def test_tax_services_share_legacy_key(self) -> None:
        self.assertEqual(
            legacy_benefit_key_for_canonical_service(CanonicalServiceKey.TAX_BRIEFING.value),
            "tax",
        )
        self.assertEqual(
            legacy_benefit_key_for_canonical_service(CanonicalServiceKey.TAX_FILING_SUPPORT.value),
            "tax",
        )

    def test_json_schema_includes_enums(self) -> None:
        props = CANONICAL_ENTITLEMENT_RULE_JSON_SCHEMA["properties"]
        self.assertIn("enum", props["service_key"])
        self.assertGreaterEqual(len(props["service_key"]["enum"]), 10)

    def test_infer_rule_strength_ordering(self) -> None:
        self.assertEqual(
            infer_rule_strength(
                is_draft_candidate_only=True,
                has_numeric_or_structured_limit=False,
                passes_publish_gate_signals=False,
                passes_comparison_signals=False,
            ),
            "draft_only",
        )


if __name__ == "__main__":
    unittest.main()
