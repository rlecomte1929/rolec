"""Grouped policy items vs atomic comparison subrules; HR row deduplication."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import unittest

from backend.services.policy_grouped_policy_model import (
    build_grouped_policy_items,
    build_grouped_policy_review_view,
    derive_comparison_subrules_from_grouped_item,
    grouped_items_to_atomic_comparison_subrules,
)


def _clause(
    idx: int,
    raw: str,
    *,
    title: str | None = None,
    mapping: dict | None = None,
    summary_section_ref: str | None = None,
) -> dict:
    hints: dict = {}
    if summary_section_ref:
        hints["summary_row_candidate"] = {"section_reference": summary_section_ref}
    if mapping:
        hints["canonical_lta_row_mapping"] = mapping
    return {
        "id": f"c{idx}",
        "clause_type": "benefit",
        "title": title,
        "raw_text": raw,
        "section_label": "Test",
        "normalized_hint_json": hints,
        "source_page_start": 1,
        "source_page_end": 1,
        "source_anchor": raw[:80],
        "confidence": 0.85,
    }


def _draft(clause_index: int, excerpt: str, *, section_ref: str = "2.1") -> dict:
    return {
        "clause_index": clause_index,
        "clause_id": f"c{clause_index}",
        "clause_type": "benefit",
        "candidate_service_key": "relocation_services",
        "candidate_coverage_status": "mentioned",
        "candidate_exclusion_flag": False,
        "amount_fragments": {},
        "duration_quantity_fragments": None,
        "applicability_fragments": {},
        "source_trace": {
            "document_id": "d1",
            "source_page_start": 1,
            "source_page_end": 1,
            "source_anchor": excerpt[:80],
            "section_label": "Test",
            "section_ref": section_ref,
        },
        "source_excerpt": excerpt,
        "confidence": 0.85,
        "publishability_assessment": "draft_only",
        "publish_layer_targets": [],
    }


class GroupedPolicyModelTests(unittest.TestCase):
    def test_duplicate_drafts_same_canonical_cluster_one_hr_grouped_item(self) -> None:
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
            "applicability": [],
            "draft_only_unresolved": False,
            "provenance": {"section_reference": "4.2"},
        }
        clauses = [
            _clause(0, "row a", mapping=m, summary_section_ref="4.2"),
            _clause(1, "row b", mapping=m, summary_section_ref="4.2"),
        ]
        drafts = [
            _draft(0, "Relocation allowance assignee 5000 each dependant 1000", section_ref="4.2"),
            _draft(1, "Relocation allowance assignee 5000 each dependant 1000", section_ref="4.2"),
        ]
        grouped = build_grouped_policy_items(clauses, drafts)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["merged_draft_candidate_count"], 2)
        self.assertEqual(len(drafts), 2)

    def test_relocation_grouped_subrules_for_tiers(self) -> None:
        item = {
            "grouped_item_id": "gpi-test",
            "canonical_key": "relocation_allowance",
            "grouped_values": {
                "amount_tiers": [
                    {"role": "assignee", "amount_text": "5000"},
                    {"role": "each_dependant", "amount_text": "1000"},
                ]
            },
        }
        subs = derive_comparison_subrules_from_grouped_item(item)
        self.assertEqual(len(subs), 2)
        self.assertTrue(all(s["kind"] == "amount_tier" for s in subs))
        self.assertTrue(all(s["compare_eligible"] for s in subs))

    def test_home_leave_variants_not_numeric_compare(self) -> None:
        item = {
            "grouped_item_id": "gpi-hl",
            "canonical_key": "home_leave",
            "grouped_values": {"leave_variants": ["standard", "split family", "R&R"]},
        }
        subs = derive_comparison_subrules_from_grouped_item(item)
        self.assertGreaterEqual(len(subs), 1)
        self.assertTrue(all(s["kind"] == "travel_variant" for s in subs))
        self.assertFalse(any(s["compare_eligible"] for s in subs))

    def test_child_education_differential_subrule(self) -> None:
        item = {
            "grouped_item_id": "gpi-edu",
            "canonical_key": "child_education",
            "grouped_values": {"reimbursement_logic": "difference_only"},
        }
        subs = derive_comparison_subrules_from_grouped_item(item)
        kinds = {s["kind"] for s in subs}
        self.assertIn("reimbursement_differential", kinds)
        diff = next(s for s in subs if s["kind"] == "reimbursement_differential")
        self.assertTrue(diff["compare_eligible"])

    def test_host_housing_external_no_budget_subrule_without_explicit_cap(self) -> None:
        item = {
            "grouped_item_id": "gpi-hs",
            "canonical_key": "host_housing",
            "comparison_readiness_hint": "external_reference",
            "explicit_numeric_cap": False,
            "grouped_values": {"cap_basis": "external_or_third_party"},
        }
        subs = derive_comparison_subrules_from_grouped_item(item)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["kind"], "external_reference")
        self.assertFalse(subs[0]["compare_eligible"])

    def test_host_housing_explicit_cap_allows_compare_subrule(self) -> None:
        item = {
            "grouped_item_id": "gpi-hs2",
            "canonical_key": "host_housing",
            "comparison_readiness_hint": "external_reference",
            "explicit_numeric_cap": True,
            "grouped_values": {"cap_basis": "external_or_third_party"},
        }
        subs = derive_comparison_subrules_from_grouped_item(item)
        self.assertTrue(any(s["kind"] == "housing_cap" and s["compare_eligible"] for s in subs))

    def test_grouped_fewer_than_drafts_when_duplicate_clusters(self) -> None:
        """Mimics two normalization drafts for the same canonical cluster → one HR grouped item."""
        fp = "same text fingerprint"
        mapping = {
            "primary_canonical_key": "work_permits_and_visas",
            "sub_values": {},
            "normalized_text_fingerprint": fp,
            "comparison_readiness_hint": "ready",
            "coverage_status": "specified",
            "applicability": ["employee", "family"],
            "draft_only_unresolved": False,
            "provenance": {"section_reference": "1.2"},
        }
        clauses = [
            _clause(0, "Visa for assignee and family", mapping=mapping, summary_section_ref="1.2"),
            _clause(1, "Visa for assignee and family", mapping=mapping, summary_section_ref="1.2"),
        ]
        drafts = [
            _draft(0, "Visa for assignee and family", section_ref="1.2"),
            _draft(1, "Visa for assignee and family", section_ref="1.2"),
        ]
        self.assertEqual(len(drafts), 2)
        grouped, subrules = build_grouped_policy_review_view(clauses, drafts)
        self.assertEqual(len(grouped), 1)
        self.assertLess(len(grouped), len(drafts))
        self.assertEqual(grouped_items_to_atomic_comparison_subrules(grouped), subrules)

    def test_temporary_living_duration_in_subrules_after_view_merge(self) -> None:
        mapping = {
            "primary_canonical_key": "temporary_living_outbound",
            "sub_values": {},
            "quantification": {"duration_days": 30},
            "normalized_text_fingerprint": "temp living 30 days",
            "comparison_readiness_hint": "ready",
            "coverage_status": "specified",
            "applicability": [],
            "draft_only_unresolved": False,
            "provenance": {"section_reference": "3"},
        }
        clauses = [
            _clause(
                0,
                "Temporary living up to 30 days maximum",
                mapping=mapping,
                summary_section_ref="3",
            )
        ]
        drafts = [_draft(0, "Temporary living up to 30 days maximum", section_ref="3")]
        grouped, subrules = build_grouped_policy_review_view(clauses, drafts)
        self.assertEqual(grouped[0]["grouped_values"].get("duration_days"), 30)
        self.assertTrue(any(s["kind"] == "duration_cap" and s["duration_days"] == 30 for s in subrules))


if __name__ == "__main__":
    unittest.main()
