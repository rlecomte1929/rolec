"""Unit tests: policy normalization readiness + payload validation (422 paths)."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY, SCOPE_LONG_TERM
from backend.services.policy_normalization_errors import PolicyNormalizationPayloadInvalid
from backend.services.policy_normalization_validate import (
    evaluate_normalization_readiness,
    readiness_for_auto_publish,
    validate_benefit_rules_payload,
    validate_policy_version_payload,
)


class PolicyNormalizationValidateTests(unittest.TestCase):
    def test_readiness_empty_layer2_known_scope_allows_draft_not_publish(self) -> None:
        doc = {
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": SCOPE_LONG_TERM,
            "extracted_metadata": {},
        }
        normalized = {
            "benefit_rules": [],
            "exclusions": [],
            "conditions": [],
        }
        r = evaluate_normalization_readiness(doc, normalized)
        self.assertFalse(r.draft_blocked)
        self.assertFalse(r.publishable)
        self.assertEqual(r.readiness_status, "draft_no_benefits_or_exclusions")
        self.assertTrue(any("layer2" in i.field for i in r.readiness_issues))

    def test_readiness_policy_summary_empty_layer2_draft_ok(self) -> None:
        doc = {
            "detected_document_type": DOC_TYPE_POLICY_SUMMARY,
            "detected_policy_scope": SCOPE_LONG_TERM,
            "extracted_metadata": {},
        }
        normalized = {
            "benefit_rules": [],
            "exclusions": [],
            "conditions": [],
        }
        r = evaluate_normalization_readiness(doc, normalized)
        self.assertFalse(r.draft_blocked)
        self.assertFalse(r.publishable)
        self.assertTrue(any("policy_summary" in (i.actual or "") for i in r.readiness_issues))

    def test_readiness_ok_with_exclusion_only(self) -> None:
        doc = {
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": SCOPE_LONG_TERM,
            "extracted_metadata": {},
        }
        normalized = {
            "benefit_rules": [],
            "exclusions": [{"domain": "scope", "description": "x"}],
            "conditions": [],
        }
        r = evaluate_normalization_readiness(doc, normalized)
        self.assertFalse(r.draft_blocked)
        self.assertTrue(r.publishable)
        self.assertEqual(r.readiness_issues, [])

    def test_readiness_unknown_scope_empty_layer2_draft_blocked(self) -> None:
        doc = {
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": "unknown",
            "extracted_metadata": {},
        }
        normalized = {
            "benefit_rules": [],
            "exclusions": [],
            "conditions": [],
        }
        r = evaluate_normalization_readiness(doc, normalized)
        self.assertTrue(r.draft_blocked)
        self.assertFalse(r.publishable)

    def test_readiness_processing_failed_draft_blocked(self) -> None:
        doc = {
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": SCOPE_LONG_TERM,
            "processing_status": "failed",
            "extracted_metadata": {},
        }
        normalized = {
            "benefit_rules": [{"benefit_key": "housing", "benefit_category": "housing"}],
            "exclusions": [],
            "conditions": [],
        }
        r = evaluate_normalization_readiness(doc, normalized)
        self.assertTrue(r.draft_blocked)

    def test_strict_require_conditions_blocks_publish_only(self) -> None:
        doc = {
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": SCOPE_LONG_TERM,
            "extracted_metadata": {},
        }
        normalized = {
            "benefit_rules": [{"benefit_key": "housing", "benefit_category": "housing"}],
            "exclusions": [],
            "conditions": [],
        }
        r = evaluate_normalization_readiness(doc, normalized, strict_require_conditions=True)
        self.assertFalse(r.draft_blocked)
        self.assertFalse(r.publishable)
        self.assertEqual(r.readiness_status, "conditions_required_for_publish")
        ok, issues = readiness_for_auto_publish(doc, normalized, strict_require_conditions=True)
        self.assertFalse(ok)
        self.assertTrue(any(b.field.endswith("conditions") for b in issues))

    def test_validate_version_bad_status(self) -> None:
        with self.assertRaises(PolicyNormalizationPayloadInvalid) as ctx:
            validate_policy_version_payload(
                {
                    "id": "v1",
                    "policy_id": "p1",
                    "version_number": 1,
                    "status": "not_a_real_status",
                    "auto_generated": True,
                    "review_status": "pending",
                },
                document_id="d1",
                request_id="r1",
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_POLICY_VERSION_SCHEMA")
        self.assertTrue(any("status" in d.field for d in ctx.exception.details))

    def test_validate_benefit_rule_bad_calc_type(self) -> None:
        with self.assertRaises(PolicyNormalizationPayloadInvalid) as ctx:
            validate_benefit_rules_payload(
                [
                    {
                        "benefit_key": "housing",
                        "benefit_category": "housing",
                        "calc_type": "invalid_calc_xyz",
                    }
                ],
                document_id="d1",
                request_id="r1",
            )
        self.assertEqual(ctx.exception.error_code, "INVALID_POLICY_VERSION_SCHEMA")


if __name__ == "__main__":
    unittest.main()
