"""Canonical LTA template: structure, uniqueness, required keys."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_canonical_lta_template import (
    CANONICAL_LTA_TEMPLATE_FIELDS,
    LTA_DOMAIN_IDS,
    LTA_POLICY_DOMAIN_ORDER,
    PolicyTemplateValueType,
    canonical_lta_template_as_jsonable,
    get_canonical_lta_field,
    list_taxonomy_keys_used_by_lta_template,
)


class CanonicalLtaTemplateTests(unittest.TestCase):
    REQUIRED_KEYS = frozenset(
        {
            "work_permits_and_visas",
            "medical_exam_support",
            "pre_assignment_visit",
            "policy_briefing",
            "cultural_training",
            "language_training",
            "travel_to_host",
            "relocation_allowance",
            "removal_expenses",
            "shipment_outbound",
            "storage",
            "temporary_living_outbound",
            "settling_in_support",
            "host_housing",
            "host_transportation",
            "mobility_premium",
            "location_premium",
            "remote_premium",
            "cola",
            "tax_equalization",
            "tax_briefing",
            "tax_return_support",
            "spouse_support",
            "child_education",
            "school_search",
            "home_leave",
            "return_shipment",
            "return_travel",
            "temporary_living_return",
            "repatriation_allowance",
        }
    )

    def test_unique_keys(self) -> None:
        keys = [f.key for f in CANONICAL_LTA_TEMPLATE_FIELDS]
        self.assertEqual(len(keys), len(set(keys)), "duplicate canonical keys")

    def test_domains_valid(self) -> None:
        for f in CANONICAL_LTA_TEMPLATE_FIELDS:
            self.assertIn(f.domain_id, LTA_DOMAIN_IDS, f.key)

    def test_domain_order_covers_all_domains(self) -> None:
        ordered = {d[0] for d in LTA_POLICY_DOMAIN_ORDER}
        self.assertEqual(ordered, LTA_DOMAIN_IDS)

    def test_required_keys_present(self) -> None:
        present = {f.key for f in CANONICAL_LTA_TEMPLATE_FIELDS}
        missing = self.REQUIRED_KEYS - present
        self.assertFalse(missing, f"missing keys: {missing}")

    def test_get_field_and_jsonable(self) -> None:
        f = get_canonical_lta_field("cola")
        self.assertIsNotNone(f)
        assert f is not None
        self.assertEqual(f.value_type, PolicyTemplateValueType.PERCENTAGE)
        blob = canonical_lta_template_as_jsonable()
        self.assertEqual(blob["schema"], "canonical_lta_template_v1")
        self.assertGreaterEqual(len(blob["fields"]), len(self.REQUIRED_KEYS))

    def test_taxonomy_bridge_subset(self) -> None:
        keys = list_taxonomy_keys_used_by_lta_template()
        self.assertIn("immigration", keys)
        self.assertIn("cola", keys)


if __name__ == "__main__":
    unittest.main()
