"""Policy assistant analytics emission."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_assistant_analytics import (
    EVENT_ASSISTANT_ANSWER_GENERATED,
    EVENT_ASSISTANT_ANSWER_READINESS,
    EVENT_ASSISTANT_ANSWER_TOPIC,
    EVENT_ASSISTANT_QUESTION_ASKED,
    EVENT_ASSISTANT_QUESTION_SUPPORTED,
    EVENT_ASSISTANT_QUESTION_UNSUPPORTED,
    EVENT_ASSISTANT_REFUSAL_SHOWN,
    record_policy_assistant_turn,
)
from backend.services.policy_assistant_answer_engine import ResolvedPolicyContext
from backend.services.policy_assistant_classifier import PolicyAssistantClassificationResult
from backend.services.policy_assistant_contract import (
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantIntent,
    PolicyAssistantPolicyStatus,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)


class PolicyAssistantAnalyticsTests(unittest.TestCase):
    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_supported_entitlement_emits_core_events(self, mock_emit) -> None:
        ctx = ResolvedPolicyContext(
            has_published_benefits=True,
            topicless_comparison_readiness=None,
        )
        cls = PolicyAssistantClassificationResult(
            supported=True,
            intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
            canonical_topic=PolicyAssistantCanonicalTopic.SHIPMENT,
            normalized_question="x",
        )
        ans = PolicyAssistantAnswer(
            answer_type=PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY,
            canonical_topic=PolicyAssistantCanonicalTopic.SHIPMENT,
            answer_text="ok",
            policy_status=PolicyAssistantPolicyStatus.PUBLISHED,
            comparison_readiness=PolicyAssistantComparisonReadiness.COMPARISON_READY,
            evidence=[],
            conditions=[],
            approval_required=False,
            follow_up_options=[],
            refusal=None,
            role_scope=PolicyAssistantRoleScope.EMPLOYEE,
        )
        record_policy_assistant_turn(
            message="What is my shipment cap?",
            role=PolicyAssistantRoleScope.EMPLOYEE,
            classification=cls,
            answer=ans,
            ctx=ctx,
            request_id="r1",
            employee_resolution={"comparison_readiness": {"comparison_ready": True}},
        )
        names = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn(EVENT_ASSISTANT_QUESTION_ASKED, names)
        self.assertIn(EVENT_ASSISTANT_QUESTION_SUPPORTED, names)
        self.assertIn(EVENT_ASSISTANT_ANSWER_GENERATED, names)
        self.assertIn(EVENT_ASSISTANT_ANSWER_TOPIC, names)
        self.assertIn(EVENT_ASSISTANT_ANSWER_READINESS, names)
        self.assertNotIn(EVENT_ASSISTANT_REFUSAL_SHOWN, names)

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_refusal_emits_refusal_shown(self, mock_emit) -> None:
        ctx = ResolvedPolicyContext(has_published_benefits=False)
        cls = PolicyAssistantClassificationResult(
            supported=False,
            intent=PolicyAssistantIntent.UNSUPPORTED_QUESTION,
            refusal_code=PolicyAssistantRefusalCode.OUT_OF_SCOPE_TRAVEL_OR_LIFESTYLE,
            normalized_question="x",
        )
        from backend.services.policy_assistant_answer_engine import generate_policy_assistant_answer

        ans = generate_policy_assistant_answer(cls, ctx, PolicyAssistantRoleScope.EMPLOYEE)
        record_policy_assistant_turn(
            message="best hotels in paris",
            role=PolicyAssistantRoleScope.EMPLOYEE,
            classification=cls,
            answer=ans,
            ctx=ctx,
            request_id="r2",
            employee_resolution={},
        )
        names = [c.args[0] for c in mock_emit.call_args_list]
        self.assertIn(EVENT_ASSISTANT_QUESTION_UNSUPPORTED, names)
        self.assertIn(EVENT_ASSISTANT_REFUSAL_SHOWN, names)


if __name__ == "__main__":
    unittest.main()
