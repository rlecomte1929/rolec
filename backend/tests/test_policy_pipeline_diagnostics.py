"""policy_pipeline_diagnostics: per-clause table + flags (read-only helpers)."""
from __future__ import annotations

import os
import sys
import unittest
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_normalization import normalize_clauses_to_objects
from backend.services.policy_pipeline_diagnostics import (
    build_per_clause_pipeline_table,
    raw_text_diagnostic_flags,
)


class PolicyPipelineDiagnosticsTests(unittest.TestCase):
    def test_section_decimal_hint_flag(self) -> None:
        hints = {"candidate_numeric_values": [2.1, 8.0]}
        flags = raw_text_diagnostic_flags("See section 2.1 for housing.", hints, None)
        self.assertIn("section_ref_in_text", flags)
        self.assertIn("hint_numeric_looks_like_section_decimal", flags)

    def test_per_clause_table_aligns_with_mapping(self) -> None:
        cid = str(uuid.uuid4())
        clauses = [
            {
                "id": cid,
                "clause_type": "benefit",
                "raw_text": "Up to EUR 5,000 for temporary accommodation.",
                "normalized_hint_json": {},
                "section_label": None,
                "confidence": 0.9,
            }
        ]
        mapped = normalize_clauses_to_objects(clauses, "doc-x")
        rows, summary = build_per_clause_pipeline_table(clauses, mapped, document_id="doc-x")
        self.assertEqual(summary["clause_count"], 1)
        self.assertEqual(summary["draft_rule_candidates_count"], 1)
        self.assertEqual(rows[0]["publish_benefit_rules"], 1)
        self.assertEqual(rows[0]["publish_conditions"], 0)
        self.assertEqual(rows[0]["mapped_service_key"], "temporary_housing")


if __name__ == "__main__":
    unittest.main()
