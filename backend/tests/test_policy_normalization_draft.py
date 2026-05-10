"""Unit tests: normalization_draft model builder (metadata + clause/rule candidates + readiness)."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY, SCOPE_LONG_TERM
from backend.services.policy_normalization_draft import build_normalization_draft_model
from backend.services.policy_normalization_validate import evaluate_normalization_readiness


class PolicyNormalizationDraftTests(unittest.TestCase):
    def test_summary_no_mapped_layer2(self) -> None:
        doc = {
            "id": "doc-1",
            "company_id": "co-1",
            "detected_document_type": DOC_TYPE_POLICY_SUMMARY,
            "detected_policy_scope": SCOPE_LONG_TERM,
            "processing_status": "classified",
            "extracted_metadata": {"mentioned_assignment_types": ["long_term_assignment"]},
            "filename": "summary.pdf",
            "mime_type": "application/pdf",
        }
        clauses = [
            {
                "id": "c1",
                "clause_type": "scope",
                "raw_text": "The mobility program supports international assignees.",
                "normalized_hint_json": {},
                "confidence": 0.55,
            }
        ]
        mapped = {"benefit_rules": [], "exclusions": [], "conditions": [], "evidence_requirements": []}
        core = evaluate_normalization_readiness(doc, mapped)
        draft = build_normalization_draft_model(
            policy_document=doc,
            company_id="co-1",
            policy_id="pol-1",
            policy_version_id="ver-1",
            clauses=clauses,
            mapped=mapped,
            norm_core=core,
        )
        self.assertEqual(draft["schema_version"], 1)
        self.assertEqual(draft["document_metadata"]["source_policy_document_id"], "doc-1")
        self.assertIn("long_term", str(draft["document_metadata"]["assignment_type_hints"]).lower())
        self.assertEqual(len(draft["clause_candidates"]), 1)
        self.assertEqual(draft["rule_candidates"]["benefit_rules"], [])
        self.assertEqual(draft["readiness"]["normalization_readiness"]["status"], "partial")

    def test_weak_coverage_only_clause_hints(self) -> None:
        """Clause carries Layer-1 style hints but mapper emits no Layer-2 row."""
        doc = {
            "id": "d2",
            "company_id": "co-2",
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": SCOPE_LONG_TERM,
            "processing_status": "classified",
            "extracted_metadata": {},
            "filename": "p.pdf",
        }
        clauses = [
            {
                "id": "c1",
                "clause_type": "unknown",
                "raw_text": "Benefits may include support elements subject to approval.",
                "normalized_hint_json": {
                    "candidate_currency": "USD",
                    "candidate_numeric_values": [2500],
                    "candidate_assignment_types": ["long_term"],
                },
                "confidence": 0.4,
            }
        ]
        mapped = {"benefit_rules": [], "exclusions": [], "conditions": [], "evidence_requirements": []}
        core = evaluate_normalization_readiness(doc, mapped)
        draft = build_normalization_draft_model(
            policy_document=doc,
            company_id="co-2",
            policy_id="pol-2",
            policy_version_id="ver-2",
            clauses=clauses,
            mapped=mapped,
            norm_core=core,
        )
        cc = draft["clause_candidates"][0]
        self.assertEqual(cc["limit_fragments"]["currency"], "USD")
        self.assertTrue(cc["limit_fragments"]["numeric_values"])
        self.assertTrue(cc["applicability_fragments"]["assignment_types"])
        self.assertEqual(draft["document_metadata"]["default_currency"], "USD")

    def test_partial_structured_metadata_only(self) -> None:
        """Explicit type/scope on document; minimal clauses (single empty-ish row still counts as candidate)."""
        doc = {
            "id": "d3",
            "company_id": "co-3",
            "detected_document_type": "assignment_policy",
            "detected_policy_scope": SCOPE_LONG_TERM,
            "processing_status": "classified",
            "extracted_metadata": {"detected_title": "Global Mobility Policy"},
            "filename": "gm.pdf",
        }
        clauses = [
            {
                "id": "c1",
                "clause_type": "definition",
                "raw_text": "Definitions apply to this policy document.",
                "normalized_hint_json": {},
                "confidence": 0.3,
            }
        ]
        mapped = {"benefit_rules": [], "exclusions": [], "conditions": [], "evidence_requirements": []}
        core = evaluate_normalization_readiness(doc, mapped)
        draft = build_normalization_draft_model(
            policy_document=doc,
            company_id="co-3",
            policy_id="pol-3",
            policy_version_id="ver-3",
            clauses=clauses,
            mapped=mapped,
            norm_core=core,
        )
        self.assertEqual(draft["document_metadata"]["policy_name"], "Global Mobility Policy")
        self.assertEqual(draft["document_metadata"]["detected_document_type"], "assignment_policy")


if __name__ == "__main__":
    unittest.main()
