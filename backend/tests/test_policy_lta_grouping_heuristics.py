"""LTA domain grouping heuristics: allowances, leave variants, family, external ref, governance, compensation."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import unittest

from backend.services.policy_lta_grouping_heuristics import (
    analyze_external_reference,
    analyze_lta_grouping_patterns,
    extract_governance_conditions,
    parse_allowance_value_structure,
    parse_travel_leave_variants,
)
from backend.services.policy_row_to_template_mapper import map_single_row_candidate
from backend.services.policy_summary_row_parser import PolicyRowCandidate


def _rc(summary: str, label: str | None = None, section: str | None = None) -> PolicyRowCandidate:
    return PolicyRowCandidate(
        row_id="t1",
        source_document_id="d1",
        page_number=1,
        section_context=section,
        component_label=label,
        summary_text=summary,
        section_reference="5.1",
    )


class LtaGroupingHeuristicsTests(unittest.TestCase):
    def test_allowance_assignee_dependant_one_off_capped(self) -> None:
        text = (
            "Relocation lump sum: assignee USD 12,000, each dependant USD 3,000 — one-off payment; "
            "capped reimbursement up to EUR 2,000 for incidental expenses."
        )
        alw = parse_allowance_value_structure(text)
        self.assertEqual(alw.get("allowance_payment_type"), "one_off")
        self.assertTrue(alw.get("reimbursement_cap_mentioned"))
        roles = {t["role"] for t in (alw.get("amount_tiers") or [])}
        self.assertEqual(roles, {"assignee", "each_dependant"})

    def test_travel_leave_variants_comma_list(self) -> None:
        text = (
            "Home leave including standard home leave, split family leave, dependant in education leave, "
            "and R&R travel where eligible."
        )
        v = parse_travel_leave_variants(text)
        self.assertGreaterEqual(len(v), 3)
        joined = " ".join(v).lower()
        self.assertTrue("split" in joined or "split family" in joined)

    def test_family_coverage_assignee_spouse_children_conditional(self) -> None:
        blob = (
            "Visa and work permit support for assignee; spouse included; children covered where eligible "
            "if in full-time education."
        )
        p = analyze_lta_grouping_patterns(blob)
        fc = p["family_coverage"]
        self.assertTrue(fc.get("assignee"))
        self.assertTrue(fc.get("spouse_partner"))
        self.assertTrue(fc.get("children"))
        self.assertTrue(fc.get("children_conditional"))

    def test_external_reference_global_travel_policy(self) -> None:
        text = "Business travel booked as per Global Travel Policy; economy class unless exception approved."
        ext = analyze_external_reference(text)
        self.assertTrue(ext.get("is_externally_governed"))
        self.assertEqual(ext.get("coverage_label"), "covered")
        self.assertIn(ext.get("comparison_readiness"), ("partial", "not_ready"))

    def test_external_reference_third_party_cap_not_ready(self) -> None:
        text = "Host housing capped level determined by third party data; subject to annual review."
        ext = analyze_external_reference(text)
        self.assertTrue(ext.get("is_externally_governed"))
        self.assertEqual(ext.get("comparison_readiness"), "not_ready")

    def test_governance_prior_approval_quotes_business_line(self) -> None:
        text = (
            "Household goods shipment with prior approval; two quotes required; "
            "business line approval needed above EUR 10,000."
        )
        gov = extract_governance_conditions(text)
        kinds = {g["kind"] for g in gov}
        self.assertIn("prior_approval", kinds)
        self.assertIn("quotes_required", kinds)
        self.assertIn("business_line_approval", kinds)

    def test_compensation_informational_split_payroll_row(self) -> None:
        m = map_single_row_candidate(
            _rc(
                "Compensation approach: split payroll between home and host country payroll delivery.",
                label="Compensation",
            )
        )
        self.assertEqual(m.primary_canonical_key, "policy_definitions_and_exceptions")
        self.assertEqual(m.comparison_readiness_hint, "not_ready")
        topics = (m.sub_values.get("informational_compensation_topics") or [])
        self.assertTrue(any("split" in t or "payroll" in t for t in topics))

    def test_mapped_row_home_leave_external_partial(self) -> None:
        m = map_single_row_candidate(
            _rc(
                "Home leave: standard / split family / dependant in education / R&R — flights as per Global Travel Policy.",
                label="Home leave",
            )
        )
        self.assertEqual(m.primary_canonical_key, "home_leave")
        self.assertGreaterEqual(len(m.sub_values.get("leave_variants") or []), 2)
        self.assertEqual(m.comparison_readiness_hint, "partial")
        self.assertTrue(m.sub_values.get("external_governance", {}).get("is_externally_governed"))

    def test_mapped_row_relocation_merges_heuristic_allowance_flags(self) -> None:
        m = map_single_row_candidate(
            _rc(
                "Mobility allowance one-off: assignee 8000 GBP, each dependant 1500; capped reimbursement for extras.",
                label="Relocation allowance",
            )
        )
        self.assertEqual(m.primary_canonical_key, "relocation_allowance")
        self.assertEqual(m.sub_values.get("allowance_payment_type"), "one_off")
        self.assertTrue(m.sub_values.get("reimbursement_cap_mentioned"))
        self.assertTrue(m.sub_values.get("family_coverage"))


if __name__ == "__main__":
    unittest.main()
