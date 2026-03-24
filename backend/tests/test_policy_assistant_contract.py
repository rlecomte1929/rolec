"""Policy assistant Pydantic contract — round-trip and refusal factory."""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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
    refusal_for_out_of_scope_travel_legal,
)


class PolicyAssistantContractTests(unittest.TestCase):
    def test_answer_round_trip_json(self) -> None:
        msg = PolicyAssistantAnswer(
            answer_type=PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY,
            canonical_topic=PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
            answer_text="Your published policy includes temporary housing subject to the stated cap.",
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
        raw = msg.model_dump(mode="json")
        s = json.dumps(raw)
        back = PolicyAssistantAnswer.model_validate_json(s)
        self.assertEqual(back.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)

    def test_refusal_extra_forbidden(self) -> None:
        r = refusal_for_out_of_scope_travel_legal()
        self.assertEqual(
            r.refusal_code,
            PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_TAX_IMMIGRATION_TRAVEL,
        )
        with self.assertRaises(Exception):
            PolicyAssistantRefusal.model_validate(
                {
                    "refusal_code": "out_of_scope_general",
                    "refusal_text": "x",
                    "extra_field": "nope",
                }
            )


if __name__ == "__main__":
    unittest.main()
