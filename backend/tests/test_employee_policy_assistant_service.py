"""Employee policy assistant service and API."""
from __future__ import annotations

import os
import sys
import unittest
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.employee_policy_assistant_service import (
    build_resolved_policy_context_from_employee_resolution,
    employee_policy_assistant_query_response_dict,
    execute_employee_policy_assistant_query,
)
from backend.services.policy_assistant_contract import (
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)


class EmployeePolicyAssistantServiceTests(unittest.TestCase):
    def test_build_context_no_published_policy(self) -> None:
        ctx = build_resolved_policy_context_from_employee_resolution(
            {"has_policy": False, "benefits": [], "exclusions": []}
        )
        self.assertFalse(ctx.has_published_benefits)
        self.assertFalse(ctx.draft_exists)
        self.assertEqual(ctx.topics, {})

    def test_build_context_partial_version_readiness(self) -> None:
        ctx = build_resolved_policy_context_from_employee_resolution(
            {
                "has_policy": True,
                "benefits": [],
                "exclusions": [],
                "comparison_readiness": {
                    "comparison_ready": False,
                    "partial_numeric_coverage": True,
                    "comparison_blockers": [],
                },
            }
        )
        self.assertEqual(ctx.topicless_comparison_readiness, "external_reference_partial")

    def test_build_context_supported_benefit_row(self) -> None:
        ctx = build_resolved_policy_context_from_employee_resolution(
            {
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
                    }
                ],
                "exclusions": [],
                "policy": {"title": "Mobility Policy", "version": 2, "company_name": "Acme"},
            }
        )
        row = ctx.topics.get("temporary_housing")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertTrue(row.included)
        self.assertTrue(row.has_numeric_cap)
        self.assertEqual(row.policy_source_type, "published_benefit_rule")

    def test_supported_employee_question_via_pipeline(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "temporary_housing",
                        "included": True,
                        "max_value": 10000,
                        "currency": "USD",
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "full",
                            "supports_budget_delta": True,
                            "reasons": [],
                        },
                    }
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }

        ans, rid, _sess = execute_employee_policy_assistant_query(
            "assignment-1",
            "Is temporary housing included?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id="req-test-1",
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(rid, "req-test-1")
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY)
        self.assertEqual(ans.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)
        self.assertIn("Temporary", ans.answer_text)
        self.assertEqual(ans.role_scope, PolicyAssistantRoleScope.EMPLOYEE)

    def test_unsupported_employee_question(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {"has_policy": True, "benefits": [], "exclusions": []}

        ans, _, _sess = execute_employee_policy_assistant_query(
            "assignment-1",
            "Can I negotiate a better salary package?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id=None,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        self.assertIsNotNone(ans.refusal)
        assert ans.refusal is not None
        self.assertEqual(ans.refusal.refusal_code, PolicyAssistantRefusalCode.OUT_OF_SCOPE_NEGOTIATION)

    def test_employee_draft_question_refusal(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {"has_policy": True, "benefits": [], "exclusions": []}

        ans, _, _sess = execute_employee_policy_assistant_query(
            "assignment-1",
            "What changes if the draft is published?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id=None,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        assert ans.refusal is not None
        self.assertEqual(ans.refusal.refusal_code, PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT)

    def test_no_published_policy_refusal_or_empty_topics(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {"has_policy": False, "benefits": [], "exclusions": []}

        ans, _, _sess = execute_employee_policy_assistant_query(
            "assignment-1",
            "Is temporary housing included?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id=None,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans.answer_type, PolicyAssistantAnswerType.REFUSAL)
        assert ans.refusal is not None
        self.assertEqual(ans.refusal.refusal_code, PolicyAssistantRefusalCode.NO_PUBLISHED_POLICY_EMPLOYEE)

    def test_partial_rule_comparison_readiness_on_topic(self) -> None:
        ctx = build_resolved_policy_context_from_employee_resolution(
            {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "shipment",
                        "included": True,
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "partial",
                            "supports_budget_delta": False,
                            "reasons": ["VAGUE_FRAMING"],
                        },
                    }
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }
        )
        row = ctx.topics.get("shipment")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.comparison_readiness, "external_reference_partial")

        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "shipment",
                        "included": True,
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "partial",
                            "supports_budget_delta": False,
                            "reasons": ["VAGUE_FRAMING"],
                        },
                    }
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }

        ans, _, _sess = execute_employee_policy_assistant_query(
            "assignment-1",
            "What is my shipment cap?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id=None,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans.comparison_readiness, PolicyAssistantComparisonReadiness.EXTERNAL_REFERENCE_PARTIAL)
        self.assertIn("invent numeric comparisons", ans.answer_text.lower())

    def test_query_response_envelope_includes_request_id(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {"has_policy": False, "benefits": [], "exclusions": []}

        out = employee_policy_assistant_query_response_dict(
            "aid-9",
            "Hello",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id="trace-123",
            resolve_published_policy=fake_resolve,
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("request_id"), "trace-123")
        self.assertEqual(out.get("assignment_id"), "aid-9")
        self.assertIn("answer", out)
        self.assertIn("session", out)
        self.assertEqual(out["session"].get("scope_id"), "aid-9")

    def test_session_pronoun_follow_up_after_entitlement_answer(self) -> None:
        def fake_resolve(aid: str, user: dict, rid, *, read_only: bool = False):
            return {
                "has_policy": True,
                "benefits": [
                    {
                        "benefit_key": "temporary_housing",
                        "included": True,
                        "max_value": 8000,
                        "currency": "USD",
                        "approval_required": False,
                        "rule_comparison_readiness": {
                            "level": "full",
                            "supports_budget_delta": True,
                            "reasons": [],
                        },
                    }
                ],
                "exclusions": [],
                "comparison_readiness": {"comparison_ready": True},
            }

        ans1, _, sess = execute_employee_policy_assistant_query(
            "assignment-1",
            "Is temporary housing included?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id=None,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans1.answer_type, PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY)
        ans2, _, _ = execute_employee_policy_assistant_query(
            "assignment-1",
            "What about it?",
            {"id": "u1", "role": "EMPLOYEE"},
            request_id=None,
            session=sess,
            resolve_published_policy=fake_resolve,
        )
        self.assertEqual(ans2.answer_type, PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY)
        self.assertEqual(ans2.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)


if __name__ == "__main__":
    unittest.main()
