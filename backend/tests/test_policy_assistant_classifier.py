"""Policy assistant deterministic classifier."""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_assistant_classifier import classify_policy_chat_message
from backend.services.policy_assistant_contract import (
    PolicyAssistantCanonicalTopic,
    PolicyAssistantIntent,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)


class PolicyAssistantClassifierTests(unittest.TestCase):
    def test_clear_in_scope_entitlement_examples(self) -> None:
        r = classify_policy_chat_message(
            "Is temporary housing included?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r.supported)
        self.assertEqual(r.intent, PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION)
        self.assertEqual(r.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)
        self.assertIsNone(r.refusal_code)

        r2 = classify_policy_chat_message(
            "What is my shipment cap?",
            "employee",
            None,
        )
        self.assertTrue(r2.supported)
        self.assertEqual(r2.canonical_topic, PolicyAssistantCanonicalTopic.SHIPMENT)

        r3 = classify_policy_chat_message(
            "Does school search apply to my family?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r3.supported)
        self.assertEqual(r3.canonical_topic, PolicyAssistantCanonicalTopic.SCHOOL_SEARCH)

        r4 = classify_policy_chat_message(
            "Is approval required for spouse support?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r4.supported)
        self.assertEqual(r4.intent, PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION)
        self.assertEqual(r4.canonical_topic, PolicyAssistantCanonicalTopic.SPOUSE_SUPPORT)

    def test_comparison_readiness_question(self) -> None:
        r = classify_policy_chat_message(
            "Why is this informational only?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r.supported)
        self.assertEqual(r.intent, PolicyAssistantIntent.POLICY_COMPARISON_QUESTION)
        self.assertIsNone(r.canonical_topic)

    def test_unsupported_examples(self) -> None:
        cases = [
            ("Can I negotiate a better package?", PolicyAssistantRefusalCode.OUT_OF_SCOPE_NEGOTIATION),
            ("What visa should I apply for?", PolicyAssistantRefusalCode.OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY),
            ("I need an immigration attorney for my situation.", PolicyAssistantRefusalCode.OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY),
            ("How much tax will I owe if I relocate?", PolicyAssistantRefusalCode.OUT_OF_SCOPE_TAX_BEYOND_POLICY),
            ("Which school do you recommend for my kids?", PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE),
            ("Is this neighborhood safe?", PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE),
            ("Can you write an email to HR?", PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT),
        ]
        for msg, code in cases:
            with self.subTest(msg=msg):
                r = classify_policy_chat_message(msg, PolicyAssistantRoleScope.EMPLOYEE, None)
                self.assertFalse(r.supported, msg)
                self.assertEqual(r.intent, PolicyAssistantIntent.UNSUPPORTED_QUESTION, msg)
                self.assertEqual(r.refusal_code, code, msg)

    def test_ambiguous_no_topic_hit(self) -> None:
        r = classify_policy_chat_message(
            "Tell me something about benefits?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertFalse(r.supported)
        self.assertEqual(r.intent, PolicyAssistantIntent.AMBIGUOUS_QUESTION)
        self.assertEqual(r.refusal_code, PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED)

    def test_hr_only_draft_vs_published(self) -> None:
        q = "What changes if this draft is published?"
        hr = classify_policy_chat_message(q, PolicyAssistantRoleScope.HR, None)
        self.assertTrue(hr.supported)
        self.assertEqual(hr.intent, PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION)
        self.assertIsNone(hr.canonical_topic)

        em = classify_policy_chat_message(q, PolicyAssistantRoleScope.EMPLOYEE, None)
        self.assertFalse(em.supported)
        self.assertEqual(em.refusal_code, PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT)

    def test_topic_confusion_temporary_vs_host(self) -> None:
        r = classify_policy_chat_message(
            "Is housing included for my assignment?",
            PolicyAssistantRoleScope.EMPLOYEE,
            [
                PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
                PolicyAssistantCanonicalTopic.HOST_HOUSING,
            ],
        )
        # Both score from weak "housing" paths only if we add equal scores — message lacks disambiguators
        self.assertTrue(r.supported)
        self.assertIsNone(r.canonical_topic)
        self.assertIsNotNone(r.ambiguity_reason)
        self.assertIn("housing", (r.ambiguity_reason or "").lower())

    def test_host_housing_prefers_host_country_phrasing(self) -> None:
        r = classify_policy_chat_message(
            "What is the host country housing benefit?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r.supported)
        self.assertEqual(r.canonical_topic, PolicyAssistantCanonicalTopic.HOST_HOUSING)

    def test_temporary_housing_not_host_phrasing(self) -> None:
        r = classify_policy_chat_message(
            "Temporary accommodation up to 30 days — is that covered?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r.supported)
        self.assertEqual(r.canonical_topic, PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING)

    def test_visa_support_excludes_which_visa(self) -> None:
        # "which visa" is unsupported globally first
        r = classify_policy_chat_message(
            "Does the policy include visa support for my family?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r.supported)
        self.assertEqual(r.canonical_topic, PolicyAssistantCanonicalTopic.VISA_SUPPORT)

    def test_tax_briefing_supported_without_tax_return_phrase(self) -> None:
        """TAX_BRIEFING negatives include 'tax return'; wording must not false-trigger."""
        r = classify_policy_chat_message(
            "Does my policy include a tax briefing or orientation?",
            PolicyAssistantRoleScope.EMPLOYEE,
            None,
        )
        self.assertTrue(r.supported)
        self.assertEqual(r.canonical_topic, PolicyAssistantCanonicalTopic.TAX_BRIEFING)

    def test_available_topics_filters_unknown_topic(self) -> None:
        r = classify_policy_chat_message(
            "What is my shipment cap?",
            PolicyAssistantRoleScope.EMPLOYEE,
            [PolicyAssistantCanonicalTopic.HOME_LEAVE],
        )
        self.assertFalse(r.supported)
        self.assertEqual(r.intent, PolicyAssistantIntent.AMBIGUOUS_QUESTION)

    def test_normalized_question_populated(self) -> None:
        r = classify_policy_chat_message("  Hello?  ", PolicyAssistantRoleScope.EMPLOYEE, None)
        self.assertTrue(r.normalized_question)


if __name__ == "__main__":
    unittest.main()
