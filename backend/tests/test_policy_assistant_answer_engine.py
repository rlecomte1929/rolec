"""Deterministic policy assistant answer engine."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_assistant_answer_engine import (
    PolicyAssistantResolvedTopic,
    ResolvedPolicyContext,
    generate_policy_assistant_answer,
)
from backend.services.policy_assistant_classifier import PolicyAssistantClassificationResult
from backend.services.policy_assistant_contract import (
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantIntent,
    PolicyAssistantPolicyStatus,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)


def _cls(
    *,
    supported: bool = True,
    intent: PolicyAssistantIntent = PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
    topic: PolicyAssistantCanonicalTopic | None = PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
    refusal_code=None,
) -> PolicyAssistantClassificationResult:
    return PolicyAssistantClassificationResult(
        supported=supported,
        intent=intent,
        canonical_topic=topic,
        refusal_code=refusal_code,
        normalized_question="test",
    )


class PolicyAssistantAnswerEngineTests(unittest.TestCase):
    def test_included_with_cap(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topics={
                "shipment": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=True,
                    cap_amount=10000,
                    cap_currency="USD",
                    cap_frequency="one_time",
                    comparison_readiness="comparison_ready",
                    section_ref="4.1",
                    source_label="Published benefit matrix",
                    policy_source_type="published_benefit_rule",
                    excerpt="Household goods up to USD 10,000.",
                    benefit_reference="br-ship-1",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.SHIPMENT)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY)
        self.assertIn("USD", ans.answer_text)
        self.assertIn("10000", ans.answer_text.replace(",", ""))
        self.assertEqual(ans.comparison_readiness, PolicyAssistantComparisonReadiness.COMPARISON_READY)
        self.assertEqual(len(ans.evidence), 1)
        self.assertEqual(ans.evidence[0].section_ref, "4.1")
        self.assertEqual(ans.evidence[0].policy_source_type, "published_benefit_rule")
        self.assertTrue(len(ans.follow_up_options) <= 3)

    def test_included_without_cap(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topics={
                "home_search": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=False,
                    comparison_readiness="comparison_ready",
                    policy_source_type="published_benefit_rule",
                    source_label="Published policy",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.HOME_SEARCH)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertIn("no numeric cap", ans.answer_text.lower())
        self.assertFalse(ans.approval_required)

    def test_excluded(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topics={
                "tax_return_support": PolicyAssistantResolvedTopic(
                    included=False,
                    explicitly_excluded=True,
                    comparison_readiness="not_applicable",
                    policy_source_type="published_exclusion",
                    source_label="Published exclusions",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.TAX_RETURN_SUPPORT)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertIn("not included", ans.answer_text.lower())

    def test_approval_required(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topics={
                "spouse_support": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=False,
                    approval_required=True,
                    comparison_readiness="informational_only",
                    policy_source_type="published_benefit_rule",
                    source_label="Published policy",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.SPOUSE_SUPPORT)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertTrue(ans.approval_required)
        self.assertIn("approval", ans.answer_text.lower())
        self.assertTrue(any("approval" in c.text.lower() for c in ans.conditions))

    def test_informational_only_no_invented_comparison(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topics={
                "visa_support": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=False,
                    comparison_readiness="informational_only",
                    policy_source_type="published_benefit_rule",
                    source_label="Published policy",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.VISA_SUPPORT)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertEqual(ans.comparison_readiness, PolicyAssistantComparisonReadiness.INFORMATIONAL_ONLY)
        self.assertIn("informational", ans.answer_text.lower())
        self.assertNotIn("usd 999", ans.answer_text.lower())

    def test_partial_readiness_external_reference(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topics={
                "host_housing": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=False,
                    comparison_readiness="external_reference_partial",
                    policy_source_type="published_benefit_rule",
                    source_label="Published policy",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.HOST_HOUSING)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertEqual(
            ans.comparison_readiness,
            PolicyAssistantComparisonReadiness.EXTERNAL_REFERENCE_PARTIAL,
        )
        self.assertIn("invent numeric comparisons", ans.answer_text.lower())

    def test_hr_draft_vs_published(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            draft_exists=True,
            draft_has_unpublished_changes=True,
            employee_visible_summary="Published LTA matrix v3 (caps as of Jan 2025).",
        )
        c = PolicyAssistantClassificationResult(
            supported=True,
            intent=PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION,
            canonical_topic=None,
            normalized_question="draft",
        )
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.HR)
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.DRAFT_PUBLISHED_SUMMARY)
        self.assertEqual(ans.policy_status, PolicyAssistantPolicyStatus.DRAFT_AND_PUBLISHED)
        self.assertIn("not live", ans.answer_text.lower())
        self.assertIn("employees", ans.answer_text.lower())
        self.assertGreaterEqual(len(ans.evidence), 1)
        types = {e.policy_source_type for e in ans.evidence}
        self.assertTrue(types & {"draft_normalization", "published_version"})

    def test_employee_draft_topic_refusal(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            draft_exists=True,
            topics={
                "relocation_allowance": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=True,
                    cap_amount=25000,
                    cap_currency="EUR",
                    comparison_readiness="comparison_ready",
                    policy_source_type="draft_grouped_item",
                    source_label="Draft grouped item (HR)",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        self.assertIsNotNone(ans.refusal)
        assert ans.refusal is not None
        self.assertEqual(ans.refusal.refusal_code, PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT)
        self.assertNotIn("EUR", ans.answer_text)
        self.assertNotIn("25000", ans.answer_text)

    def test_employee_draft_intent_refusal(self) -> None:
        c = PolicyAssistantClassificationResult(
            supported=True,
            intent=PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION,
            canonical_topic=None,
            normalized_question="x",
        )
        ans = generate_policy_assistant_answer(c, ResolvedPolicyContext(), PolicyAssistantRoleScope.EMPLOYEE)
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        assert ans.refusal is not None
        self.assertEqual(ans.refusal.refusal_code, PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT)

    def test_hr_can_see_draft_row(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            draft_exists=True,
            topics={
                "relocation_allowance": PolicyAssistantResolvedTopic(
                    included=True,
                    has_numeric_cap=True,
                    cap_amount=9000,
                    cap_currency="USD",
                    comparison_readiness="comparison_ready",
                    policy_source_type="draft_grouped_item",
                    source_label="Draft normalization",
                )
            },
        )
        c = _cls(topic=PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE)
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.HR)
        self.assertIsNone(ans.refusal)
        self.assertIn("9000", ans.answer_text.replace(",", ""))
        self.assertEqual(ans.policy_status, PolicyAssistantPolicyStatus.DRAFT)

    def test_topicless_comparison_question(self) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topicless_comparison_readiness="review_required",
        )
        c = PolicyAssistantClassificationResult(
            supported=True,
            intent=PolicyAssistantIntent.POLICY_COMPARISON_QUESTION,
            canonical_topic=None,
            normalized_question="why",
        )
        ans = generate_policy_assistant_answer(c, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.COMPARISON_SUMMARY)
        self.assertEqual(ans.comparison_readiness, PolicyAssistantComparisonReadiness.REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
