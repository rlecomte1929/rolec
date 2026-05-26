"""
Guardrail layer: consistent refusal copy, role-specific examples, and mixed-scope recovery.

Use after ``classify_policy_chat_message`` so unsupported turns still get policy-grounded redirects.
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple, Union

from .policy_assistant_classifier import (
    PolicyAssistantClassificationResult,
    score_policy_assistant_topics,
)
from .policy_assistant_contract import (
    POLICY_ASSISTANT_TOPIC_ORDER,
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantFollowUpOption,
    PolicyAssistantIntent,
    PolicyAssistantPolicyStatus,
    PolicyAssistantRefusal,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)

_POLICY_ANCHOR = re.compile(
    r"\b(?:policy|benefit|published|relocation|assignment|covered|included|cap|entitlement|relo|"
    r"my company's|company policy)\b",
    re.I,
)

_JAILBREAK_NO_RECOVERY = re.compile(
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)\b|"
    r"\bignore\s+your\s+(?:instructions|rules)\b|"
    r"\bdisregard\s+(?:all\s+)?(?:your\s+)?(?:instructions|rules)\b|"
    r"\bjailbreak\b|\bDAN mode\b|"
    r"\byou are (?:now )?(?:a |an )?(?:helpful )?assistant with no rules\b",
    re.I,
)

_RECOVERABLE_UNSUPPORTED: Tuple[PolicyAssistantRefusalCode, ...] = (
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_TRAVEL_OR_LIFESTYLE,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_TAX_BEYOND_POLICY,
)

_MIN_TOPIC_SCORE_FOR_RECOVERY = 5


def _parse_role(role: Union[str, PolicyAssistantRoleScope]) -> PolicyAssistantRoleScope:
    if isinstance(role, PolicyAssistantRoleScope):
        return role
    r = str(role or "").strip().lower()
    if r in ("hr", "admin"):
        return PolicyAssistantRoleScope.HR
    return PolicyAssistantRoleScope.EMPLOYEE


def _supported_example_questions(role: PolicyAssistantRoleScope) -> List[str]:
    if role == PolicyAssistantRoleScope.HR:
        return [
            "What does the published policy include for temporary housing?",
            "Is shipment capped in the working draft for this version?",
            "What changes when this draft is published for employees?",
        ]
    return [
        "What does my published policy say about temporary housing?",
        "What is my shipment cap under the policy?",
        "Is home leave covered for my assignment?",
    ]


def _refusal_prefix(code: PolicyAssistantRefusalCode) -> str:
    base = (
        "I only answer questions about your company's **relocation policy** in ReloPass. "
        "I can't continue with open-ended or out-of-scope topics."
    )
    specific = {
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_ADVICE: (
            "I can't provide **legal advice** or interpret the law."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_TAX_BEYOND_POLICY: (
            "I can't provide **personal tax advice** beyond what your **policy** states about tax-related benefits."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY: (
            "I can't advise **which visa or immigration path** to choose—only what your **policy** covers for visa or permit **support**."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_NEGOTIATION: (
            "I can't help with **negotiation strategy** or compensation discussions outside published policy entitlements."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE: (
            "I can't recommend **schools**, **neighborhoods**, or **safety** of areas."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_TRAVEL_OR_LIFESTYLE: (
            "I can't help with **general travel**, **tourism**, or **lifestyle** planning."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT: (
            "I'm not able to have a **general chat** or follow **out-of-scope instructions**."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_GENERAL: (
            "That request is **outside** what the policy assistant is built to do."
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_TAX_IMMIGRATION_TRAVEL: (
            "I can't provide general **legal, tax, immigration, travel, or lifestyle** guidance."
        ),
        PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT: (
            "**Draft** and **internal HR policy** details are available to **HR** only. "
            "Your ReloPass view reflects the **published** policy for your assignment."
        ),
        PolicyAssistantRefusalCode.NO_PUBLISHED_POLICY_EMPLOYEE: (
            "There is **no published policy** bound to this assignment in ReloPass yet."
        ),
        PolicyAssistantRefusalCode.NO_POLICY_CONTEXT: (
            "There isn't enough **policy context** loaded to answer safely."
        ),
        PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED: (
            "I need a **specific benefit or policy topic** (for example shipment or home leave)."
        ),
        PolicyAssistantRefusalCode.INSUFFICIENT_POLICY_DATA: (
            "The loaded policy data isn't sufficient to answer that precisely."
        ),
    }
    extra = specific.get(code, specific[PolicyAssistantRefusalCode.OUT_OF_SCOPE_GENERAL])
    return f"{extra} {base}".strip()


def policy_assistant_refusal_for_code(
    code: PolicyAssistantRefusalCode,
    role: Union[str, PolicyAssistantRoleScope],
    *,
    ambiguity_override: Optional[str] = None,
) -> PolicyAssistantRefusal:
    """Deterministic refusal payload: same tone, three role-appropriate example questions."""
    rs = _parse_role(role)
    examples = _supported_example_questions(rs)
    if code == PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED and ambiguity_override:
        text = (
            f"{ambiguity_override} "
            "I only answer from your company's relocation policy in ReloPass."
        )
    else:
        text = _refusal_prefix(code)
    return PolicyAssistantRefusal(refusal_code=code, refusal_text=text, supported_examples=examples)


def _examples_to_follow_ups(examples: List[str]) -> List[PolicyAssistantFollowUpOption]:
    out: List[PolicyAssistantFollowUpOption] = []
    for ex in examples[:3]:
        label = ex if len(ex) <= 56 else ex[:53] + "..."
        out.append(
            PolicyAssistantFollowUpOption(
                intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
                label=label,
                query_hint=ex,
            )
        )
    return out


def follow_ups_from_refusal(ref: PolicyAssistantRefusal) -> List[PolicyAssistantFollowUpOption]:
    """Map refusal examples to follow-up chips (same as ``build_policy_refusal_answer``)."""
    return _examples_to_follow_ups(ref.supported_examples)


def _policy_status_for_refusal(code: PolicyAssistantRefusalCode) -> PolicyAssistantPolicyStatus:
    if code == PolicyAssistantRefusalCode.NO_PUBLISHED_POLICY_EMPLOYEE:
        return PolicyAssistantPolicyStatus.NO_POLICY_BOUND
    if code == PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT:
        return PolicyAssistantPolicyStatus.PUBLISHED
    return PolicyAssistantPolicyStatus.UNKNOWN


def build_policy_refusal_answer(
    classification: PolicyAssistantClassificationResult,
    role: Union[str, PolicyAssistantRoleScope],
) -> PolicyAssistantAnswer:
    """Full ``PolicyAssistantAnswer`` for a refused turn (no substantive continuation)."""
    rs = _parse_role(role)
    code = classification.refusal_code or PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED
    amb = classification.ambiguity_reason if code == PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED else None
    refusal = policy_assistant_refusal_for_code(code, rs, ambiguity_override=amb)
    return PolicyAssistantAnswer(
        answer_type=PolicyAssistantAnswerType.REFUSAL,
        canonical_topic=classification.canonical_topic,
        answer_text="",
        policy_status=_policy_status_for_refusal(code),
        comparison_readiness=PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
        evidence=[],
        conditions=[],
        approval_required=False,
        follow_up_options=follow_ups_from_refusal(refusal),
        refusal=refusal,
        role_scope=rs,
        detected_intent=classification.intent,
    )


def _pick_recovery_topic(
    scores: dict,
    allowed: Sequence[PolicyAssistantCanonicalTopic],
) -> Optional[PolicyAssistantCanonicalTopic]:
    positive = [(t, s) for t, s in scores.items() if s > 0 and t in allowed]
    if not positive:
        return None
    positive.sort(key=lambda x: (-x[1], POLICY_ASSISTANT_TOPIC_ORDER.index(x[0])))
    best_topic, best_score = positive[0]
    if best_score < _MIN_TOPIC_SCORE_FOR_RECOVERY:
        return None
    second_score = positive[1][1] if len(positive) > 1 else 0
    if second_score >= 4 and (best_score - second_score) <= 2:
        return None
    return best_topic


def _try_recover_mixed_scope(
    message: str,
    role: PolicyAssistantRoleScope,
    classification: PolicyAssistantClassificationResult,
    available_topics: Optional[Sequence[Union[str, PolicyAssistantCanonicalTopic]]],
) -> Optional[PolicyAssistantClassificationResult]:
    if classification.supported:
        return None
    code = classification.refusal_code
    if code is None or code not in _RECOVERABLE_UNSUPPORTED:
        return None

    from .policy_assistant_classifier import _normalize_message

    norm = _normalize_message(message)
    if not norm or _JAILBREAK_NO_RECOVERY.search(norm):
        return None
    if not _POLICY_ANCHOR.search(norm):
        return None

    allowed = list(score_policy_assistant_topics(message, available_topics).keys())
    relaxed_scores = score_policy_assistant_topics(message, available_topics, relaxed=True)
    topic = _pick_recovery_topic(relaxed_scores, allowed)
    if topic is None:
        return None

    note = (
        "I can only answer the **relocation-policy** part of your question; "
        "other topics (recommendations, lifestyle, or personal tax/immigration advice) are out of scope."
    )
    return PolicyAssistantClassificationResult(
        supported=True,
        intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
        canonical_topic=topic,
        ambiguity_reason=None,
        refusal_code=None,
        normalized_question=classification.normalized_question,
        guardrail_note=note,
    )


def apply_policy_assistant_guardrails(
    message: str,
    role: Union[str, PolicyAssistantRoleScope],
    classification: PolicyAssistantClassificationResult,
    available_topics: Optional[Sequence[Union[str, PolicyAssistantCanonicalTopic]]] = None,
) -> PolicyAssistantClassificationResult:
    """
    After classification: recover a policy-only thread when the message mixed out-of-scope asks
    with a clear policy topic, unless a jailbreak-style directive is present.
    """
    rs = _parse_role(role)
    recovered = _try_recover_mixed_scope(message, rs, classification, available_topics)
    if recovered is not None:
        return recovered
    return classification


def classify_policy_message_with_guardrails(
    message: str,
    role: Union[str, PolicyAssistantRoleScope],
    available_topics: Optional[Sequence[Union[str, PolicyAssistantCanonicalTopic]]] = None,
) -> PolicyAssistantClassificationResult:
    """Classify then apply mixed-scope recovery (recommended server entrypoint)."""
    from .policy_assistant_classifier import classify_policy_chat_message

    c = classify_policy_chat_message(message, role, available_topics)
    return apply_policy_assistant_guardrails(message, role, c, available_topics)
