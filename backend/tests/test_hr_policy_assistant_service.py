"""HR policy assistant service (draft/published, visibility, comparison partial, unsupported)."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.hr_policy_assistant_service import (
    execute_hr_policy_assistant_query,
    hr_policy_assistant_query_response_dict,
)
from backend.services.policy_assistant_answer_engine import (
    PolicyAssistantResolvedTopic,
    ResolvedPolicyContext,
)
from backend.services.policy_assistant_contract import (
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantIntent,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)


def _ctx_draft_published() -> ResolvedPolicyContext:
    return ResolvedPolicyContext(
        has_published_benefits=True,
        draft_exists=True,
        draft_has_unpublished_changes=True,
        employee_visible_summary="Acme Mobility (published v3).",
        topicless_comparison_readiness=None,
        topics={},
    )


def _ctx_employee_visibility() -> ResolvedPolicyContext:
    return ResolvedPolicyContext(
        has_published_benefits=True,
        draft_exists=True,
        draft_has_unpublished_changes=False,
        employee_visible_summary="Published policy is active.",
        topicless_comparison_readiness=None,
        topics={},
        hr_employee_visibility={
            "employee_sees_published_policy_matrix": True,
            "publish_readiness_status": "ready",
            "comparison_readiness_status": "partial",
            "comparison_ready_strict": False,
        },
    )


def _ctx_topicless_partial() -> ResolvedPolicyContext:
    return ResolvedPolicyContext(
        has_published_benefits=True,
        draft_exists=False,
        draft_has_unpublished_changes=False,
        employee_visible_summary=None,
        topicless_comparison_readiness="external_reference_partial",
        topics={},
    )


class HrPolicyAssistantServiceTests(unittest.TestCase):
    def test_hr_draft_vs_published_question(self) -> None:
        def fake_resolve(db, policy_id, document_id, request_id):
            return _ctx_draft_published()

        ans, rid, _sess = execute_hr_policy_assistant_query(
            "What is the difference between draft vs published for employees?",
            {"id": "hr1", "role": "HR"},
            "pol-1",
            document_id=None,
            request_id="req-hr-1",
            resolve_context=fake_resolve,
        )
        self.assertEqual(rid, "req-hr-1")
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.DRAFT_PUBLISHED_SUMMARY)
        self.assertEqual(ans.detected_intent, PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION)
        self.assertIn("draft", ans.answer_text.lower())
        self.assertIn("published", ans.answer_text.lower())
        self.assertEqual(ans.role_scope, PolicyAssistantRoleScope.HR)

    def test_hr_what_employees_see_now(self) -> None:
        def fake_resolve(db, policy_id, document_id, request_id):
            return _ctx_employee_visibility()

        ans, _, _sess = execute_hr_policy_assistant_query(
            "What do employees see now for this policy?",
            {"id": "hr1", "role": "HR"},
            "pol-1",
            resolve_context=fake_resolve,
        )
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.STATUS_SUMMARY)
        self.assertEqual(ans.detected_intent, PolicyAssistantIntent.EMPLOYEE_VISIBILITY_QUESTION)
        self.assertIn("published", ans.answer_text.lower())
        self.assertIn("yes", ans.answer_text.lower())

    def test_hr_why_comparison_is_partial_topicless(self) -> None:
        def fake_resolve(db, policy_id, document_id, request_id):
            return _ctx_topicless_partial()

        ans, _, _sess = execute_hr_policy_assistant_query(
            "Why is this informational only for comparisons?",
            {"id": "hr1", "role": "HR"},
            "pol-1",
            resolve_context=fake_resolve,
        )
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.COMPARISON_SUMMARY)
        self.assertEqual(ans.detected_intent, PolicyAssistantIntent.POLICY_COMPARISON_QUESTION)
        self.assertEqual(ans.comparison_readiness, PolicyAssistantComparisonReadiness.EXTERNAL_REFERENCE_PARTIAL)
        self.assertIn("not fully comparison-ready", ans.answer_text.lower())

    def test_hr_unsupported_strategy_question(self) -> None:
        def fake_resolve(db, policy_id, document_id, request_id):
            return _ctx_draft_published()

        ans, _, _sess = execute_hr_policy_assistant_query(
            "How should we structure our benefits policy for the market?",
            {"id": "hr1", "role": "HR"},
            "pol-1",
            resolve_context=fake_resolve,
        )
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        assert ans.refusal is not None
        self.assertEqual(ans.refusal.refusal_code, PolicyAssistantRefusalCode.OUT_OF_SCOPE_GENERAL)

    def test_hr_publish_preview_suffix_on_entitlement_when_publish_and_employees_see(self) -> None:
        row = PolicyAssistantResolvedTopic(
            included=True,
            explicitly_excluded=False,
            has_numeric_cap=True,
            cap_amount=5000.0,
            cap_currency="USD",
            approval_required=False,
            comparison_readiness="comparison_ready",
            policy_source_type="draft_benefit_rule",
            source_label="Draft",
        )

        def fake_resolve(db, policy_id, document_id, request_id):
            return ResolvedPolicyContext(
                has_published_benefits=True,
                draft_exists=True,
                draft_has_unpublished_changes=True,
                employee_visible_summary="v2 published.",
                topicless_comparison_readiness=None,
                topics={"shipment": row},
            )

        ans, _, _sess = execute_hr_policy_assistant_query(
            "If I publish this draft, what would employees see for shipment cap?",
            {"id": "hr1", "role": "HR"},
            "pol-1",
            resolve_context=fake_resolve,
        )
        self.assertEqual(ans.canonical_topic, PolicyAssistantCanonicalTopic.SHIPMENT)
        self.assertIn("publish", ans.answer_text.lower())
        self.assertIn("published", ans.answer_text.lower())

    def test_query_response_envelope(self) -> None:
        def fake_resolve(db, policy_id, document_id, request_id):
            return _ctx_draft_published()

        out = hr_policy_assistant_query_response_dict(
            "draft vs published?",
            {"id": "hr1", "role": "HR"},
            "pol-9",
            document_id="doc-2",
            request_id="trace-hr",
            resolve_context=fake_resolve,
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("policy_id"), "pol-9")
        self.assertEqual(out.get("document_id"), "doc-2")
        self.assertEqual(out.get("request_id"), "trace-hr")
        self.assertIn("answer", out)
        self.assertIn("session", out)
        self.assertEqual(out["session"].get("scope_id"), "pol-9")


if __name__ == "__main__":
    unittest.main()
