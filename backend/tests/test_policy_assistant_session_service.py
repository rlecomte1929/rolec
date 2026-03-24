"""Bounded policy assistant session memory."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_assistant_classifier import PolicyAssistantClassificationResult
from backend.services.policy_assistant_contract import (
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantIntent,
    PolicyAssistantPolicyStatus,
    PolicyAssistantRefusal,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)
from backend.services.policy_assistant_answer_engine import ResolvedPolicyContext, generate_policy_assistant_answer
from backend.services.employee_policy_assistant_service import execute_employee_policy_assistant_query
from backend.services.policy_assistant_session_service import (
    SESSION_TOPIC_MENU_MARKER,
    PolicyAssistantSessionState,
    apply_bounded_session_memory,
    classify_with_bounded_session,
    parse_policy_assistant_session,
    update_session_after_turn,
)


def _ambig() -> PolicyAssistantClassificationResult:
    return PolicyAssistantClassificationResult(
        supported=False,
        intent=PolicyAssistantIntent.AMBIGUOUS_QUESTION,
        canonical_topic=None,
        ambiguity_reason="Could not map to a known policy topic",
        refusal_code=PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED,
        normalized_question="x",
    )


def _supported_temp_housing() -> PolicyAssistantClassificationResult:
    return PolicyAssistantClassificationResult(
        supported=True,
        intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
        canonical_topic=PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
        normalized_question="q",
    )


def _entitlement_answer() -> PolicyAssistantAnswer:
    return PolicyAssistantAnswer(
        answer_type=PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY,
        canonical_topic=PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
        answer_text="**Temporary housing** is included up to **5000 USD**.",
        policy_status=PolicyAssistantPolicyStatus.PUBLISHED,
        comparison_readiness=PolicyAssistantComparisonReadiness.COMPARISON_READY,
        evidence=[],
        conditions=[],
        approval_required=False,
        follow_up_options=[],
        refusal=None,
        role_scope=PolicyAssistantRoleScope.EMPLOYEE,
        detected_intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
    )


class PolicyAssistantSessionServiceTests(unittest.TestCase):
    def test_parse_session_scope_mismatch_resets(self) -> None:
        raw = {
            "v": 1,
            "scope_kind": "employee_assignment",
            "scope_id": "other",
            "last_canonical_topic": "shipment",
            "had_supported_policy_turn": True,
        }
        s = parse_policy_assistant_session(raw, scope_kind="employee_assignment", scope_id="asg-1")
        self.assertEqual(s.scope_id, "asg-1")
        self.assertIsNone(s.last_canonical_topic)
        self.assertFalse(s.had_supported_policy_turn)

    def test_pronoun_follow_up_carries_topic(self) -> None:
        state = PolicyAssistantSessionState.for_scope("employee_assignment", "asg-1")
        state.had_supported_policy_turn = True
        state.last_canonical_topic = "temporary_housing"
        state.last_intent = PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION.value
        refined = apply_bounded_session_memory(
            "What about it?",
            PolicyAssistantRoleScope.EMPLOYEE,
            state,
            _ambig(),
        )
        self.assertTrue(refined.supported)
        self.assertEqual(refined.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)

    def test_comparison_intent_carried_on_pronoun_follow_up(self) -> None:
        state = PolicyAssistantSessionState.for_scope("employee_assignment", "asg-1")
        state.had_supported_policy_turn = True
        state.last_canonical_topic = "shipment"
        state.last_intent = PolicyAssistantIntent.POLICY_COMPARISON_QUESTION.value
        refined = apply_bounded_session_memory(
            "How about that?",
            PolicyAssistantRoleScope.EMPLOYEE,
            state,
            _ambig(),
        )
        self.assertTrue(refined.supported)
        self.assertEqual(refined.intent, PolicyAssistantIntent.POLICY_COMPARISON_QUESTION)
        self.assertEqual(refined.canonical_topic, PolicyAssistantCanonicalTopic.SHIPMENT)

    def test_topic_switch_updates_session(self) -> None:
        s = PolicyAssistantSessionState.for_scope("employee_assignment", "asg-1")
        s.had_supported_policy_turn = True
        s.last_canonical_topic = "temporary_housing"
        cls = PolicyAssistantClassificationResult(
            supported=True,
            intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
            canonical_topic=PolicyAssistantCanonicalTopic.SHIPMENT,
            normalized_question="what about shipment",
        )
        ans = PolicyAssistantAnswer(
            answer_type=PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY,
            canonical_topic=PolicyAssistantCanonicalTopic.SHIPMENT,
            answer_text="**Shipment** cap is **10000 USD**.",
            policy_status=PolicyAssistantPolicyStatus.PUBLISHED,
            comparison_readiness=PolicyAssistantComparisonReadiness.COMPARISON_READY,
            evidence=[],
            conditions=[],
            approval_required=False,
            follow_up_options=[],
            refusal=None,
            role_scope=PolicyAssistantRoleScope.EMPLOYEE,
        )
        out = update_session_after_turn(s, cls, ans)
        self.assertEqual(out.last_canonical_topic, "shipment")
        self.assertIn("Shipment", out.last_answer_summary)

    def test_drift_after_supported_refuses_unrelated(self) -> None:
        state = PolicyAssistantSessionState.for_scope("employee_assignment", "asg-1")
        state.had_supported_policy_turn = True
        state.last_canonical_topic = "temporary_housing"
        refined = apply_bounded_session_memory(
            "yeah whatever",
            PolicyAssistantRoleScope.EMPLOYEE,
            state,
            _ambig(),
        )
        self.assertFalse(refined.supported)
        self.assertEqual(refined.refusal_code, PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT)

    def test_employee_draft_question_after_valid_turn_still_refused(self) -> None:
        # Simulate session after one good answer
        s = PolicyAssistantSessionState.for_scope("employee_assignment", "asg-1")
        s = update_session_after_turn(s, _supported_temp_housing(), _entitlement_answer())
        self.assertTrue(s.had_supported_policy_turn)
        c = classify_with_bounded_session(
            "What changes if the draft is published for employees?",
            PolicyAssistantRoleScope.EMPLOYEE,
            s,
        )
        self.assertFalse(c.supported)
        self.assertEqual(c.refusal_code, PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT)
        refusal_ans = generate_policy_assistant_answer(
            c,
            ResolvedPolicyContext(has_published_benefits=True),
            PolicyAssistantRoleScope.EMPLOYEE,
        )
        self.assertEqual(refusal_ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        s2 = update_session_after_turn(s, c, refusal_ans)
        self.assertFalse(s2.had_supported_policy_turn)
        self.assertIsNone(s2.last_canonical_topic)

    def test_forced_topic_menu_after_repeated_ambiguity(self) -> None:
        state = PolicyAssistantSessionState.for_scope("hr_policy", "pol-1")
        state.ambiguous_streak = 2
        refined = apply_bounded_session_memory(
            "hmm",
            PolicyAssistantRoleScope.HR,
            state,
            _ambig(),
        )
        self.assertTrue(refined.supported)
        self.assertIsNone(refined.canonical_topic)
        self.assertIn("Name one benefit", refined.ambiguity_reason or "")
        self.assertEqual(refined.guardrail_note, SESSION_TOPIC_MENU_MARKER)

    def test_relaxed_topic_recovery_after_supported_turn(self) -> None:
        """Topic switch / follow-up phrasing: strong relaxed score overrides ambiguous classifier."""
        state = PolicyAssistantSessionState.for_scope("employee_assignment", "asg-1")
        state.had_supported_policy_turn = True
        refined = apply_bounded_session_memory(
            "household goods cap under my policy",
            PolicyAssistantRoleScope.EMPLOYEE,
            state,
            _ambig(),
        )
        self.assertTrue(refined.supported)
        self.assertEqual(refined.canonical_topic, PolicyAssistantCanonicalTopic.SHIPMENT)

    def test_one_valid_follow_up_end_to_end(self) -> None:
        """Pronoun follow-up resolves via session (bounded continuity)."""

        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "temporary_housing",
                        "included": True,
                        "max_value": 5000,
                        "currency": "USD",
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "full",
                            "supports_budget_delta": True,
                            "reasons": [],
                        },
                    },
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }

        user = {"id": "u1", "role": "EMPLOYEE"}
        ans1, _, sess1 = execute_employee_policy_assistant_query(
            "asg-1",
            "What is my temporary housing cap?",
            user,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans1.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)
        ans2, _, _sess2 = execute_employee_policy_assistant_query(
            "asg-1",
            "What about it?",
            user,
            session=sess1,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans2.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)

    def test_topic_switch_within_policy_end_to_end(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "temporary_housing",
                        "included": True,
                        "max_value": 5000,
                        "currency": "USD",
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "full",
                            "supports_budget_delta": True,
                            "reasons": [],
                        },
                    },
                    {
                        "benefit_key": "shipment",
                        "included": True,
                        "max_value": 8000,
                        "currency": "USD",
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "full",
                            "supports_budget_delta": True,
                            "reasons": [],
                        },
                    },
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }

        user = {"id": "u1", "role": "EMPLOYEE"}
        _, _, sess1 = execute_employee_policy_assistant_query(
            "asg-1",
            "Temporary housing limit?",
            user,
            resolve_published_policy=fake_resolve,
        )
        ans2, _, sess2 = execute_employee_policy_assistant_query(
            "asg-1",
            "What is my shipment cap?",
            user,
            session=sess1,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans2.canonical_topic, PolicyAssistantCanonicalTopic.SHIPMENT)
        self.assertEqual(sess2.get("last_canonical_topic"), "shipment")

    def test_drift_to_unsupported_resets_session(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "temporary_housing",
                        "included": True,
                        "max_value": 5000,
                        "currency": "USD",
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "full",
                            "supports_budget_delta": True,
                            "reasons": [],
                        },
                    },
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }

        user = {"id": "u1", "role": "EMPLOYEE"}
        _, _, sess1 = execute_employee_policy_assistant_query(
            "asg-1",
            "What is my temporary housing cap?",
            user,
            resolve_published_policy=fake_resolve,
        )
        self.assertTrue(sess1.get("had_supported_policy_turn"))
        ans2, _, sess2 = execute_employee_policy_assistant_query(
            "asg-1",
            "yeah whatever",
            user,
            session=sess1,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans2.answer_type, PolicyAssistantAnswerType.REFUSAL)
        assert ans2.refusal is not None
        self.assertEqual(ans2.refusal.refusal_code, PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT)
        self.assertFalse(sess2.get("had_supported_policy_turn"))


if __name__ == "__main__":
    unittest.main()
