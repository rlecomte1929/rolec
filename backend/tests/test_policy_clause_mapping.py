"""Unit tests: normalize_clauses_to_objects (draft_rule_candidates vs publish-layer rows)."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_normalization import normalize_clauses_to_objects


def _clause(
    *,
    ctype: str = "unknown",
    raw: str = "",
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "policy_document_id": None,
        "clause_type": ctype,
        "raw_text": raw,
        "normalized_hint_json": hints or {},
        "confidence": 0.82,
        "section_label": None,
        "source_page_start": 1,
        "source_page_end": 1,
        "source_anchor": "p1",
    }


class PolicyClauseMappingTests(unittest.TestCase):
    def test_vague_summary_clause_draft_only_no_publish_benefit(self) -> None:
        raw = (
            "Temporary accommodation may be provided depending on assignment conditions."
        )
        clauses: List[Dict[str, Any]] = [_clause(ctype="unknown", raw=raw)]
        out = normalize_clauses_to_objects(clauses, "doc-1")
        self.assertEqual(len(out["benefit_rules"]), 0)
        self.assertEqual(len(out["exclusions"]), 0)
        self.assertEqual(len(out["draft_rule_candidates"]), 1)
        d0 = out["draft_rule_candidates"][0]
        self.assertEqual(d0["candidate_service_key"], "temporary_housing")
        self.assertEqual(d0["publishability_assessment"], "draft_only")
        self.assertEqual(d0["candidate_coverage_status"], "conditional")

    def test_explicit_exclusion_publish_layer_and_draft(self) -> None:
        raw = "School search not covered for single employees."
        clauses = [_clause(ctype="unknown", raw=raw)]
        out = normalize_clauses_to_objects(clauses, "doc-2")
        self.assertEqual(len(out["exclusions"]), 1)
        self.assertEqual(out["exclusions"][0]["domain"], "benefit")
        self.assertEqual(out["exclusions"][0]["benefit_key"], "schooling")
        self.assertEqual(len(out["benefit_rules"]), 0)
        d0 = out["draft_rule_candidates"][0]
        self.assertTrue(d0["candidate_exclusion_flag"])
        self.assertEqual(d0["publishability_assessment"], "publish_exclusion")
        self.assertIn("single", d0["applicability_fragments"]["family_status_terms"])

    def test_explicit_cap_publish_benefit_and_draft(self) -> None:
        raw = "Up to EUR 5,000 for temporary accommodation."
        clauses = [_clause(ctype="benefit", raw=raw)]
        out = normalize_clauses_to_objects(clauses, "doc-3")
        self.assertEqual(len(out["benefit_rules"]), 1)
        br = out["benefit_rules"][0]
        self.assertEqual(br["benefit_key"], "temporary_housing")
        self.assertEqual(br["currency"], "EUR")
        self.assertEqual(br["amount_value"], 5000.0)
        self.assertEqual(len(out["exclusions"]), 0)
        d0 = out["draft_rule_candidates"][0]
        self.assertEqual(d0["publishability_assessment"], "publish_benefit_rule")
        self.assertEqual(d0["candidate_coverage_status"], "capped")

    def test_applicability_only_clause_draft_with_assignment_fragment(self) -> None:
        raw = "This section applies only to long-term assignments."
        clauses = [_clause(ctype="scope", raw=raw)]
        out = normalize_clauses_to_objects(clauses, "doc-4")
        self.assertEqual(len(out["benefit_rules"]), 0)
        self.assertEqual(len(out["exclusions"]), 0)
        self.assertEqual(len(out["draft_rule_candidates"]), 1)
        d0 = out["draft_rule_candidates"][0]
        self.assertEqual(d0["publishability_assessment"], "draft_only")
        self.assertIn("LTA", d0["applicability_fragments"]["assignment_types"])

    def test_ambiguous_narrative_retained_as_draft_candidate(self) -> None:
        raw = (
            "The mobility team reviews each file and coordinates with internal "
            "stakeholders regarding outcomes."
        )
        clauses = [_clause(ctype="unknown", raw=raw)]
        out = normalize_clauses_to_objects(clauses, "doc-5")
        self.assertEqual(len(out["benefit_rules"]), 0)
        self.assertEqual(len(out["exclusions"]), 0)
        self.assertEqual(len(out["draft_rule_candidates"]), 1)
        d0 = out["draft_rule_candidates"][0]
        self.assertIsNone(d0["candidate_service_key"])
        self.assertEqual(d0["candidate_coverage_status"], "unknown")
        self.assertEqual(d0["publishability_assessment"], "draft_only")


if __name__ == "__main__":
    unittest.main()
