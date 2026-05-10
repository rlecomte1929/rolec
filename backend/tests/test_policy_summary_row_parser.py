"""Summary-table row parser: row candidates and clause integration."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY
from backend.services.policy_summary_row_parser import (
    parse_items_into_summary_row_candidates,
    should_use_summary_row_parser,
    summary_row_candidates_to_clause_dicts,
    try_build_clauses_via_summary_rows,
)
from backend.services.policy_document_clauses import segment_document_from_raw_text
from backend.services.policy_normalization import normalize_clauses_to_objects


def _ctx(**kwargs):
    base = {
        "id": "doc-test-1",
        "detected_document_type": DOC_TYPE_POLICY_SUMMARY,
        "extracted_metadata": {"likely_table_heavy": True},
    }
    base.update(kwargs)
    return base


class PolicySummaryRowParserTests(unittest.TestCase):
    def test_one_row_section_ref_separate_column(self) -> None:
        items = [
            {"text": "Housing | Up to 90 days temporary accommodation | 2.1", "page": 1, "is_table_row": True},
        ]
        self.assertTrue(should_use_summary_row_parser(_ctx(), items))
        rows = parse_items_into_summary_row_candidates(items, "doc-test-1")
        self.assertEqual(len(rows), 1)
        r0 = rows[0]
        self.assertEqual(r0.component_label, "Housing")
        self.assertIn("90 days", r0.summary_text)
        self.assertEqual(r0.section_reference, "2.1")
        self.assertNotIn("2.1", r0.summary_text)
        clauses = summary_row_candidates_to_clause_dicts(rows)
        self.assertEqual(len(clauses), 1)
        h = clauses[0]["normalized_hint_json"] or {}
        self.assertEqual(h.get("summary_row_candidate", {}).get("section_reference"), "2.1")
        nums = h.get("candidate_numeric_values") or []
        self.assertNotIn(2.1, nums)

    def test_heading_then_child_rows_section_context(self) -> None:
        items = [
            {"text": "Family Support", "page": 1, "is_table_row": False},
            {
                "text": "Spouse support | Lump sum per policy | 6.5",
                "page": 1,
                "is_table_row": True,
            },
        ]
        rows = parse_items_into_summary_row_candidates(items, "doc-x")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].section_context, "Family Support")
        self.assertEqual(rows[0].section_reference, "6.5")

    def test_missing_section_ref(self) -> None:
        items = [
            {"text": "Schooling | Tuition difference reimbursement where eligible", "page": 2, "is_table_row": True},
        ]
        rows = parse_items_into_summary_row_candidates(items, "doc-y")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].section_reference)
        self.assertIn("Tuition", rows[0].summary_text)

    def test_wrapped_line_merged_into_previous_row(self) -> None:
        items = [
            {"text": "Travel | Economy flights for employee", "page": 1, "is_table_row": True},
            {"text": "and one accompanying dependent per year.", "page": 1, "is_table_row": False},
        ]
        rows = parse_items_into_summary_row_candidates(items, "doc-z")
        self.assertEqual(len(rows), 1)
        self.assertIn("dependent", rows[0].summary_text.lower())
        self.assertGreaterEqual(len(rows[0].raw_fragments), 2)

    def test_multi_part_description_multiple_cells(self) -> None:
        items = [
            {
                "text": "Mobility | Premium | 15% of base | paid monthly | 8.3",
                "page": 1,
                "is_table_row": True,
            },
        ]
        rows = parse_items_into_summary_row_candidates(items, "doc-m")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].component_label, "Mobility")
        self.assertEqual(rows[0].section_reference, "8.3")
        self.assertIn("15%", rows[0].summary_text)
        self.assertIn("monthly", rows[0].summary_text)
        self.assertNotIn("8.3", rows[0].summary_text)

    def test_non_summary_document_returns_none_from_try_build(self) -> None:
        items = [
            {"text": "A | B | 1", "page": 1, "is_table_row": True},
            {"text": "C | D | 2", "page": 1, "is_table_row": True},
        ]
        ctx = {
            "id": "d2",
            "detected_document_type": "assignment_policy",
            "extracted_metadata": {},
        }
        self.assertFalse(should_use_summary_row_parser(ctx, items))
        self.assertIsNone(try_build_clauses_via_summary_rows(items, ctx))

    def test_end_to_end_normalize_single_draft_per_row(self) -> None:
        items = [
            {"text": "Temporary housing | EUR 5000 cap | 4.2", "page": 1, "is_table_row": True},
        ]
        clauses = try_build_clauses_via_summary_rows(items, _ctx())
        self.assertIsNotNone(clauses)
        assert clauses is not None
        out = normalize_clauses_to_objects(clauses, "doc-e2e")
        self.assertEqual(len(out["draft_rule_candidates"]), 1)
        self.assertGreaterEqual(len(out.get("benefit_rules") or []), 1)

    def test_segment_document_prefers_rows_when_gated(self) -> None:
        raw = "Family Support\nHousing | Cap EUR 5000 | 2.1\n"
        clauses, err = segment_document_from_raw_text(
            raw,
            "application/pdf",
            data=None,
            policy_context=_ctx(),
        )
        self.assertIsNone(err)
        self.assertEqual(len(clauses), 1)
        meta = (clauses[0].get("normalized_hint_json") or {}).get("summary_row_candidate") or {}
        self.assertEqual(meta.get("section_reference"), "2.1")


if __name__ == "__main__":
    unittest.main()
