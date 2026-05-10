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
    EVENT_ASSISTANT_ANSWER_RECEIVED,
    EVENT_ASSISTANT_ANSWER_TOPIC,
    EVENT_ASSISTANT_DISMISSED,
    EVENT_ASSISTANT_FOLLOW_UP_CLICKED,
    EVENT_ASSISTANT_OPENED,
    EVENT_ASSISTANT_QUESTION_ASKED,
    EVENT_ASSISTANT_QUESTION_SUBMITTED,
    EVENT_ASSISTANT_QUESTION_SUPPORTED,
    EVENT_ASSISTANT_QUESTION_UNSUPPORTED,
    EVENT_ASSISTANT_REFUSAL_SHOWN,
    emit_assistant_answer_received,
    emit_assistant_dismissed,
    emit_assistant_follow_up_clicked,
    emit_assistant_opened,
    emit_assistant_question_submitted,
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

        gen_kw = next(c.kwargs for c in mock_emit.call_args_list if c.args[0] == EVENT_ASSISTANT_ANSWER_GENERATED)
        ex = gen_kw.get("extra") or {}
        self.assertEqual(ex.get("canonical_topic"), "shipment")
        self.assertEqual(ex.get("answer_value_bucket"), "comparison_ready")
        self.assertEqual(ex.get("policy_grounding_bucket"), "published")
        self.assertTrue(ex.get("resolved_from_published"))

        asked_kw = next(c.kwargs for c in mock_emit.call_args_list if c.args[0] == EVENT_ASSISTANT_QUESTION_ASKED)
        self.assertEqual((asked_kw.get("extra") or {}).get("canonical_topic"), "shipment")

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

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_follow_up_beacon_extra_includes_turn_correlation(self, mock_emit) -> None:
        emit_assistant_follow_up_clicked(
            role=PolicyAssistantRoleScope.HR,
            request_id="http-rid",
            follow_up_intent="policy_entitlement_question",
            follow_up_index=0,
            canonical_topic="shipment",
            assistant_turn_request_id="turn-uuid-1",
        )
        mock_emit.assert_called_once()
        self.assertEqual(mock_emit.call_args[0][0], EVENT_ASSISTANT_FOLLOW_UP_CLICKED)
        ex = (mock_emit.call_args[1].get("extra") or {})
        self.assertEqual(ex.get("assistant_turn_request_id"), "turn-uuid-1")


class Sprint15BeaconEmittersTests(unittest.TestCase):
    """Sprint 1.5: the four UI-driven beacon emitters added to back the
    assistant_opened / question_submitted / answer_received / dismissed
    events. Each one writes through the shared analytics_service emit
    pathway with surface + small enums + booleans only — no PII."""

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_opened_emits_with_surface(self, mock_emit) -> None:
        emit_assistant_opened(
            role=PolicyAssistantRoleScope.EMPLOYEE,
            request_id="rid-1",
            surface="employee_fab",
        )
        mock_emit.assert_called_once()
        self.assertEqual(mock_emit.call_args[0][0], EVENT_ASSISTANT_OPENED)
        kwargs = mock_emit.call_args[1]
        self.assertEqual(kwargs.get("user_role"), "employee")
        self.assertEqual(kwargs.get("request_id"), "rid-1")
        self.assertEqual((kwargs.get("extra") or {}).get("surface"), "employee_fab")

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_question_submitted_records_source(self, mock_emit) -> None:
        emit_assistant_question_submitted(
            role=PolicyAssistantRoleScope.HR,
            request_id="rid-2",
            surface="hr_sidesheet",
            source="shortcut",
        )
        mock_emit.assert_called_once()
        self.assertEqual(mock_emit.call_args[0][0], EVENT_ASSISTANT_QUESTION_SUBMITTED)
        ex = mock_emit.call_args[1].get("extra") or {}
        self.assertEqual(ex.get("surface"), "hr_sidesheet")
        self.assertEqual(ex.get("source"), "shortcut")

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_answer_received_carries_status_and_turn_id(self, mock_emit) -> None:
        emit_assistant_answer_received(
            role=PolicyAssistantRoleScope.EMPLOYEE,
            request_id="rid-3",
            surface="employee_fab",
            answer_type="entitlement_summary",
            status="answered",
            assistant_turn_request_id="turn-id-3",
        )
        mock_emit.assert_called_once()
        self.assertEqual(mock_emit.call_args[0][0], EVENT_ASSISTANT_ANSWER_RECEIVED)
        ex = mock_emit.call_args[1].get("extra") or {}
        self.assertEqual(ex.get("status"), "answered")
        self.assertEqual(ex.get("answer_type"), "entitlement_summary")
        self.assertEqual(ex.get("assistant_turn_request_id"), "turn-id-3")

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_dismissed_carries_engagement_booleans(self, mock_emit) -> None:
        emit_assistant_dismissed(
            role=PolicyAssistantRoleScope.EMPLOYEE,
            request_id="rid-4",
            surface="employee_fab",
            had_question=True,
            had_answer=False,
        )
        mock_emit.assert_called_once()
        self.assertEqual(mock_emit.call_args[0][0], EVENT_ASSISTANT_DISMISSED)
        ex = mock_emit.call_args[1].get("extra") or {}
        self.assertEqual(ex.get("had_question"), True)
        self.assertEqual(ex.get("had_answer"), False)

    @patch("backend.services.policy_assistant_analytics.emit_event")
    def test_dismissed_with_no_engagement(self, mock_emit) -> None:
        """User opened then closed without typing — both booleans False."""
        emit_assistant_dismissed(
            role=PolicyAssistantRoleScope.EMPLOYEE,
            request_id="rid-5",
            surface="employee_fab",
            had_question=False,
            had_answer=False,
        )
        ex = mock_emit.call_args[1].get("extra") or {}
        self.assertEqual(ex.get("had_question"), False)
        self.assertEqual(ex.get("had_answer"), False)


if __name__ == "__main__":
    unittest.main()
