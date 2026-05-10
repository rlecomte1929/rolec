"""
Regression: LTA Policy Summary — no draft explosion, section refs not values, stable topics.

Fixture models a typical uploaded *Long Term Assignment Policy Summary* table (pipe rows).
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_canonical_lta_template import get_canonical_lta_field
from backend.services.policy_grouped_policy_model import build_grouped_policy_review_view
from backend.services.policy_normalization import normalize_clauses_to_objects
from backend.services.policy_summary_row_parser import try_build_clauses_via_summary_rows
from backend.tests.lta_summary_regression_utils import (
    assert_section_refs_not_in_amount_tier_text,
    assert_section_refs_not_in_policy_text_bodies,
    assert_section_refs_not_leaked_as_numeric_values,
    fixture_policy_context_and_items,
    grouped_by_canonical_key,
    load_lta_policy_summary_regression_fixture,
)


class LtaPolicySummaryRegressionTests(unittest.TestCase):
    def test_regression_fixture_topics_grouping_and_guards(self) -> None:
        fx = load_lta_policy_summary_regression_fixture()
        ctx, items = fixture_policy_context_and_items(fx)
        clauses = try_build_clauses_via_summary_rows(items, ctx)
        self.assertIsNotNone(clauses)
        assert clauses is not None
        mapped = normalize_clauses_to_objects(clauses, ctx["id"])
        drafts = mapped.get("draft_rule_candidates") or []
        grouped, _ = build_grouped_policy_review_view(clauses, drafts)
        refs = fx["section_references_under_test"]
        expected_keys = sorted(fx["expected_canonical_keys"])

        # 9 — sensible row count (not 60+ exploded benefits)
        self.assertLessEqual(len(grouped), 24, "grouped items should stay in summary-sized range")
        self.assertEqual(len(grouped), 7)
        self.assertEqual(len(drafts), 7)
        self.assertEqual(len(clauses), 7)

        by_ck = grouped_by_canonical_key(grouped)
        self.assertEqual(sorted(by_ck.keys()), expected_keys)

        # 1 — work permits / visa: one immigration row, section ref preserved
        imm = by_ck["work_permits_and_visas"]
        self.assertEqual(imm.get("source_ref"), "2.1")
        self.assertEqual(imm.get("merged_draft_candidate_count"), 1)

        # 2 — relocation: assignee + dependant amounts
        rel = by_ck["relocation_allowance"]
        self.assertEqual(rel.get("source_ref"), "3.2")
        tiers = (rel.get("grouped_values") or {}).get("amount_tiers") or []
        roles = {t.get("role"): t.get("amount_text") for t in tiers if isinstance(t, dict)}
        self.assertEqual(roles.get("assignee"), "8000")
        self.assertEqual(roles.get("each_dependant"), "2000")

        # 3 — temporary living: 30-day duration
        tmp = by_ck["temporary_living_outbound"]
        self.assertEqual(tmp.get("source_ref"), "6.5")
        self.assertEqual((tmp.get("grouped_values") or {}).get("duration_days"), 30)

        # 4 — host housing: external cap / partial readiness
        host = by_ck["host_housing"]
        self.assertEqual(host.get("source_ref"), "8.3")
        r = host.get("readiness") or {}
        self.assertEqual(r.get("comparison_readiness"), "external_reference_partial")
        self.assertIn("external", (r.get("value_type") or "").lower())

        # 5 — spouse career → spouse_support (separate from the dedicated host housing row)
        sp = by_ck["spouse_support"]
        self.assertEqual(sp.get("source_ref"), "4.1")
        self.assertEqual(sp.get("canonical_key"), "spouse_support")
        host_only = [g for g in grouped if g.get("canonical_key") == "host_housing"]
        self.assertEqual(len(host_only), 1)

        # 6 — child education → family_support domain, not language_training
        edu = by_ck["child_education"]
        self.assertEqual(edu.get("source_ref"), "5.2")
        field = get_canonical_lta_field("child_education")
        self.assertIsNotNone(field)
        assert field is not None
        self.assertEqual(field.domain_id, "family_support")
        self.assertNotIn("language_training", by_ck)

        # 7 — home leave: variants present
        hl = by_ck["home_leave"]
        self.assertEqual(hl.get("source_ref"), "7.1")
        variants = (hl.get("grouped_values") or {}).get("leave_variants") or []
        self.assertGreaterEqual(len(variants), 2)
        joined = " ".join(str(v).lower() for v in variants)
        self.assertTrue("split" in joined or "standard" in joined)

        # 8 — section refs never as numeric / value payload
        assert_section_refs_not_leaked_as_numeric_values(clauses, drafts, refs)
        assert_section_refs_not_in_policy_text_bodies(clauses, refs)
        assert_section_refs_not_in_amount_tier_text(grouped, refs)

    def test_duplicate_identical_row_does_not_inflate_pipeline(self) -> None:
        """One logical topic duplicated in the table should not become two clauses / two groups."""
        fx = load_lta_policy_summary_regression_fixture()
        ctx, items = fixture_policy_context_and_items(fx)
        dup_first = dict(items[0])
        items_dup = [items[0], dup_first] + list(items[1:])
        clauses = try_build_clauses_via_summary_rows(items_dup, ctx)
        self.assertIsNotNone(clauses)
        assert clauses is not None
        mapped = normalize_clauses_to_objects(clauses, ctx["id"])
        drafts = mapped.get("draft_rule_candidates") or []
        grouped, _ = build_grouped_policy_review_view(clauses, drafts)
        self.assertEqual(len(clauses), 7)
        self.assertEqual(len(drafts), 7)
        self.assertEqual(len(grouped), 7)
        imm = [g for g in grouped if g.get("canonical_key") == "work_permits_and_visas"]
        self.assertEqual(len(imm), 1)


if __name__ == "__main__":
    unittest.main()
