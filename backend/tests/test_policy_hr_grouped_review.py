"""HR grouped_review: template domains + collapsed rows vs draft explosion."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_hr_grouped_review import build_grouped_hr_review
from backend.services.policy_grouped_policy_model import build_grouped_policy_review_view
from backend.services.policy_normalization import normalize_clauses_to_objects
from backend.services.policy_summary_row_parser import PolicyRowCandidate, summary_row_candidates_to_clause_dicts
from backend.services.policy_template_first_import import build_template_first_import_payload
from backend.tests.test_policy_grouped_policy_model import _clause, _draft


class PolicyHrGroupedReviewTests(unittest.TestCase):
    def test_duplicate_drafts_yield_one_grouped_row_not_many(self) -> None:
        fp = "relocation allowance assignee 5000 each dependant 1000"
        m = {
            "primary_canonical_key": "relocation_allowance",
            "sub_values": {
                "amount_tiers": [
                    {"role": "assignee", "amount_text": "5000"},
                    {"role": "each_dependant", "amount_text": "1000"},
                ]
            },
            "normalized_text_fingerprint": fp,
            "comparison_readiness_hint": "ready",
            "coverage_status": "specified",
            "applicability": ["employee", "family"],
            "draft_only_unresolved": False,
            "provenance": {"section_reference": "4.2", "summary_text": fp},
        }
        clauses = [
            _clause(0, "row a", mapping=m, summary_section_ref="4.2"),
            _clause(1, "row b", mapping=m, summary_section_ref="4.2"),
        ]
        drafts = [
            _draft(0, "Relocation allowance assignee 5000 each dependant 1000", section_ref="4.2"),
            _draft(1, "Relocation allowance assignee 5000 each dependant 1000", section_ref="4.2"),
        ]
        grouped, _ = build_grouped_policy_review_view(clauses, drafts)
        tfi = build_template_first_import_payload(clauses, drafts, grouped_policy_items_count=len(grouped))
        gr = build_grouped_hr_review(grouped, clauses, drafts, template_first_import=tfi)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(gr["counts"]["draft_rule_candidates_count"], 2)
        self.assertEqual(gr["counts"]["grouped_review_rows"], 1)
        self.assertEqual(gr["duplicate_merge_summary"]["extra_drafts_merged_into_groups"], 1)

        move = gr["template_domains"]["move_logistics"]
        self.assertEqual(len(move["items"]), 1)
        row = move["items"][0]
        self.assertEqual(row["canonical_key"], "relocation_allowance")
        self.assertIn("Relocation", row["title"] or "")
        self.assertTrue(row.get("imported_value_summary"))
        self.assertIn("Employee", row.get("applicability_summary") or "")
        self.assertIn(
            row.get("comparison_readiness"),
            ("comparison_ready", "review_required", "external_reference_partial"),
        )
        self.assertEqual(row.get("source_ref"), "4.2")
        self.assertIsNotNone(row.get("confidence"))
        self.assertEqual(row.get("review_needed"), row.get("comparison_readiness") != "comparison_ready")
        self.assertIsNotNone(row.get("child_variants"))

    def test_summary_document_grouped_review_domains(self) -> None:
        def _cand(
            row_id: str,
            summary: str,
            *,
            label: str | None = None,
            section_ref: str | None = None,
        ) -> PolicyRowCandidate:
            return PolicyRowCandidate(
                row_id=row_id,
                source_document_id="doc-sum",
                page_number=1,
                section_context=None,
                component_label=label,
                summary_text=summary,
                section_reference=section_ref,
            )

        candidates = [
            _cand(
                "r1",
                "USD 8,000 relocation lump sum for the employee.",
                label="Relocation",
                section_ref="3.1",
            ),
            _cand(
                "r2",
                "Home leave: standard / split family / R&R options.",
                label="Home leave",
                section_ref="3.2",
            ),
        ]
        clauses = summary_row_candidates_to_clause_dicts(candidates)
        mapped = normalize_clauses_to_objects(clauses, "doc-sum")
        drafts = mapped.get("draft_rule_candidates") or []
        grouped, _ = build_grouped_policy_review_view(clauses, drafts)
        tfi = build_template_first_import_payload(clauses, drafts, grouped_policy_items_count=len(grouped))
        gr = build_grouped_hr_review(grouped, clauses, drafts, template_first_import=tfi)

        self.assertGreaterEqual(len(drafts), 2, "diagnostic drafts should remain available")
        self.assertLessEqual(
            len(grouped),
            len(drafts),
            "grouped HR rows should not exceed draft rows; duplicates collapse",
        )
        self.assertIn("move_logistics", gr["domain_order"])
        self.assertIn("leave_and_travel", gr["domain_order"])

        move_items = gr["template_domains"]["move_logistics"]["items"]
        leave_items = gr["template_domains"]["leave_and_travel"]["items"]
        self.assertTrue(any(it.get("canonical_key") == "relocation_allowance" for it in move_items))
        self.assertTrue(any(it.get("canonical_key") == "home_leave" for it in leave_items))

        self.assertIn("import_summary", gr)
        self.assertIn("duplicate_merge_summary", gr)
        self.assertIn("items_needing_review", gr)
        self.assertIn("items_populated_from_upload", gr["counts"])
        self.assertIn("items_still_empty_in_template", gr["counts"])
        self.assertIsInstance(gr["empty_template_slots_by_domain"], dict)
