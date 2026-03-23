"""Tests: three-tier policy_readiness (normalization / publish / comparison)."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY, SCOPE_LONG_TERM
from backend.services.policy_processing_readiness import (
    NO_CLAUSE_CANDIDATES,
    READY_FOR_COMPARISON,
    READY_FOR_PUBLISH,
    build_processing_readiness_envelope,
    evaluate_stored_policy_readiness,
)
from backend.services.policy_normalization_validate import (
    NormalizationReadinessResult,
    evaluate_normalization_readiness,
)


def _doc(
    *,
    dtype: str = DOC_TYPE_POLICY_SUMMARY,
    scope: str = SCOPE_LONG_TERM,
    processing_status: str = "classified",
) -> dict:
    return {
        "id": "d1",
        "detected_document_type": dtype,
        "detected_policy_scope": scope,
        "processing_status": processing_status,
        "extracted_metadata": {},
    }


def _clause(raw: str, ctype: str = "scope") -> dict:
    return {
        "id": "c1",
        "raw_text": raw,
        "clause_type": ctype,
        "normalized_hint_json": {},
        "confidence": 0.7,
    }


class PolicyProcessingReadinessTests(unittest.TestCase):
    def test_policy_summary_narrative_clauses_only(self) -> None:
        doc = _doc()
        clauses = [_clause("The company supports employees on international assignment broadly.")]
        normalized = {
            "benefit_rules": [],
            "exclusions": [],
            "conditions": [],
            "assignment_applicability": [],
        }
        core = evaluate_normalization_readiness(doc, normalized)
        env = build_processing_readiness_envelope(doc, clauses, normalized, core)
        self.assertEqual(env["normalization_readiness"]["status"], "partial")
        self.assertTrue(
            any(
                i["code"] == "ONLY_SUMMARY_LEVEL_SIGNALS"
                for i in env["normalization_readiness"]["issues"]
            )
        )
        self.assertEqual(env["publish_readiness"]["status"], "not_ready")
        self.assertEqual(env["comparison_readiness"]["status"], "not_ready")

    def test_one_benefit_rule_no_numeric_cap_partial_comparison(self) -> None:
        doc = _doc(dtype="assignment_policy")
        clauses = [_clause("x", "benefit")]
        normalized = {
            "benefit_rules": [
                {
                    "benefit_key": "housing",
                    "benefit_category": "housing",
                    "calc_type": "other",
                    "amount_value": None,
                }
            ],
            "exclusions": [],
            "conditions": [],
            "assignment_applicability": [],
        }
        core = evaluate_normalization_readiness(doc, normalized)
        env = build_processing_readiness_envelope(doc, clauses, normalized, core)
        self.assertEqual(env["normalization_readiness"]["status"], "ready")
        self.assertEqual(env["publish_readiness"]["status"], "ready")
        self.assertEqual(env["comparison_readiness"]["status"], "partial")
        self.assertTrue(
            any(i["code"] == "NO_STRUCTURED_LIMITS" for i in env["comparison_readiness"]["issues"])
        )

    def test_exclusion_only_publish_ready_comparison_not_ready(self) -> None:
        doc = _doc(dtype="assignment_policy")
        clauses = [_clause("Tax equalization excluded in host state.", "exclusion")]
        normalized = {
            "benefit_rules": [],
            "exclusions": [{"domain": "tax", "description": "x"}],
            "conditions": [],
            "assignment_applicability": [],
        }
        core = evaluate_normalization_readiness(doc, normalized)
        env = build_processing_readiness_envelope(doc, clauses, normalized, core)
        self.assertEqual(env["publish_readiness"]["status"], "ready")
        self.assertTrue(any(i["code"] == READY_FOR_PUBLISH for i in env["publish_readiness"]["issues"]))
        self.assertEqual(env["comparison_readiness"]["status"], "not_ready")

    def test_structured_cap_based_all_ready(self) -> None:
        doc = _doc(dtype="assignment_policy")
        clauses = [_clause("caps", "benefit")]
        normalized = {
            "benefit_rules": [
                {
                    "benefit_key": "temporary_housing",
                    "benefit_category": "housing",
                    "calc_type": "flat_amount",
                    "amount_value": 5000,
                    "currency": "USD",
                },
                {
                    "benefit_key": "schooling",
                    "benefit_category": "schools",
                    "calc_type": "flat_amount",
                    "amount_value": 20000,
                    "currency": "USD",
                },
                {
                    "benefit_key": "shipment",
                    "benefit_category": "movers",
                    "calc_type": "flat_amount",
                    "amount_value": 10000,
                    "currency": "USD",
                },
            ],
            "exclusions": [],
            "conditions": [],
            "assignment_applicability": [{"assignment_type": "long_term_assignment", "benefit_rule_id": "x"}],
        }
        core = evaluate_normalization_readiness(doc, normalized)
        env = build_processing_readiness_envelope(doc, clauses, normalized, core)
        self.assertEqual(env["comparison_readiness"]["status"], "ready")
        self.assertTrue(any(i["code"] == READY_FOR_COMPARISON for i in env["comparison_readiness"]["issues"]))
        self.assertIn("comparison_rule_readiness", env)
        self.assertEqual(env["comparison_rule_readiness"]["policy_level"], "full")

    def test_empty_extraction_no_clauses(self) -> None:
        doc = _doc()
        clauses: list = []
        normalized = {"benefit_rules": [], "exclusions": [], "conditions": []}
        core = NormalizationReadinessResult(
            draft_blocked=True,
            draft_block_details=[],
            publishable=False,
            readiness_status="normalization_blocked",
            readiness_issues=[],
        )
        env = build_processing_readiness_envelope(doc, clauses, normalized, core)
        self.assertEqual(env["normalization_readiness"]["status"], "not_ready")
        self.assertTrue(
            any(i["code"] == NO_CLAUSE_CANDIDATES for i in env["normalization_readiness"]["issues"])
        )

    def test_stored_policy_readiness_published(self) -> None:
        env = evaluate_stored_policy_readiness(
            latest_version={"id": "v1", "status": "auto_generated", "source_policy_document_id": None},
            published_version={"id": "pv", "status": "published"},
            benefit_rules=[
                {
                    "benefit_key": "temporary_housing",
                    "calc_type": "flat_amount",
                    "amount_value": 1,
                    "currency": "USD",
                },
                {
                    "benefit_key": "schooling",
                    "calc_type": "flat_amount",
                    "amount_value": 1,
                    "currency": "USD",
                },
                {
                    "benefit_key": "shipment",
                    "calc_type": "flat_amount",
                    "amount_value": 1,
                    "currency": "USD",
                },
            ],
            exclusions=[],
            conditions=[],
            assignment_applicability=[{"x": 1}],
            source_document=None,
        )
        self.assertEqual(env["publish_readiness"]["status"], "ready")
        self.assertEqual(env["normalization_readiness"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
