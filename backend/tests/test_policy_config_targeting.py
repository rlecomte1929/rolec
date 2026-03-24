from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.schemas_compensation_allowance import (
    PolicyConfigAssignmentType,
    PolicyConfigBenefitWrite,
    PolicyConfigCategory,
    PolicyConfigFamilyStatus,
    PolicyConfigUnitFrequency,
    PolicyConfigValueType,
)
from backend.services.policy_config_targeting import (
    normalize_assignment_type,
    row_matches_targeting,
    validate_optional_query_assignment_type,
)


class PolicyConfigTargetingTests(unittest.TestCase):
    def test_normalize_assignment_legacy(self) -> None:
        self.assertEqual(normalize_assignment_type("LTA"), "long_term")
        self.assertEqual(normalize_assignment_type("long-term"), "long_term")

    def test_row_matches_strict_vs_relaxed(self) -> None:
        row = {"assignment_types": ["long_term"], "family_statuses": []}
        self.assertTrue(row_matches_targeting(row, "long_term", None, strict_context=True))
        self.assertFalse(row_matches_targeting(row, None, None, strict_context=True))
        self.assertTrue(row_matches_targeting(row, None, None, strict_context=False))

    def test_family_both_axes(self) -> None:
        row = {"assignment_types": ["long_term"], "family_statuses": ["dependents"]}
        self.assertTrue(row_matches_targeting(row, "long_term", "dependents", strict_context=True))
        self.assertFalse(row_matches_targeting(row, "long_term", "single", strict_context=True))

    def test_validate_query_assignment(self) -> None:
        self.assertIsNone(validate_optional_query_assignment_type(None))
        self.assertEqual(validate_optional_query_assignment_type("long_term"), "long_term")
        with self.assertRaises(ValueError):
            validate_optional_query_assignment_type("not_a_real_type")

    def test_benefit_write_accepts_enums(self) -> None:
        m = PolicyConfigBenefitWrite.model_validate(
            {
                "benefit_key": "mobility_premium",
                "benefit_label": "Mobility premium",
                "category": PolicyConfigCategory.compensation_allowances.value,
                "covered": True,
                "value_type": PolicyConfigValueType.currency.value,
                "assignment_types": [PolicyConfigAssignmentType.long_term.value],
                "family_statuses": [PolicyConfigFamilyStatus.dependents.value],
                "unit_frequency": PolicyConfigUnitFrequency.monthly.value,
            }
        )
        self.assertEqual(m.assignment_types[0], PolicyConfigAssignmentType.long_term)

    def test_benefit_write_rejects_bad_assignment_token(self) -> None:
        with self.assertRaises(Exception):
            PolicyConfigBenefitWrite.model_validate(
                {
                    "benefit_key": "mobility_premium",
                    "benefit_label": "Mobility premium",
                    "category": PolicyConfigCategory.compensation_allowances.value,
                    "assignment_types": ["typo_assignment"],
                    "unit_frequency": PolicyConfigUnitFrequency.monthly.value,
                }
            )


if __name__ == "__main__":
    unittest.main()
