"""
Bounded in-request session memory for policy assistant turns.

Stores only policy-scoped continuity (assignment/policy id, last topic, last answer snippet,
comparison surface). No persona or open-ended chat memory. Client round-trips ``session`` JSON;
server rejects mismatched ``scope_id`` to prevent cross-context leakage.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from .policy_assistant_classifier import (
    PolicyAssistantClassificationResult,
    _normalize_message,
    score_policy_assistant_topics,
)
from .policy_assistant_contract import (
    POLICY_ASSISTANT_TOPIC_ORDER,
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantIntent,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)
from .policy_assistant_refusal_service import classify_policy_message_with_guardrails

SESSION_TOPIC_MENU_MARKER = "_rp_session_topic_menu_v1"

_MAX_SUMMARY_LEN = 400
_MAX_AMBIGUOUS_STREAK_BEFORE_MENU = 2

_PRONOUN_FOLLOWUP = re.compile(
    r"\bwhat\s+about\s+it\b|"
    r"\bhow\s+about\s+that\b|"
    r"\bsame\s+for\s+(?:that|this|the\s+cap|the\s+limit)\b|"
    r"\band\s+the\s+(?:cap|limit)\??\b|"
    r"\bis\s+it\s+the\s+same\b|"
    r"\bwhat\s+about\s+that\s+one\b",
    re.I,
)

_POLICY_ANCHOR = re.compile(
    r"\b(?:policy|benefit|published|relocation|assignment|covered|included|cap|entitlement|relo|"
    r"draft|employees?\s+see|comparison|informational)\b",
    re.I,
)


def _parse_role(role: Union[str, PolicyAssistantRoleScope]) -> PolicyAssistantRoleScope:
    if isinstance(role, PolicyAssistantRoleScope):
        return role
    r = str(role or "").strip().lower()
    if r in ("hr", "admin"):
        return PolicyAssistantRoleScope.HR
    return PolicyAssistantRoleScope.EMPLOYEE


class PolicyAssistantSessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: int = Field(1, description="Session schema version.")
    scope_kind: str = Field(..., description="employee_assignment | hr_policy")
    scope_id: str = Field(..., min_length=1)
    last_canonical_topic: Optional[str] = None
    last_answer_summary: str = Field("", max_length=_MAX_SUMMARY_LEN)
    last_comparison_mode: Optional[str] = Field(
        None,
        description="Last answer comparison_readiness value, or comparison_intent marker.",
    )
    last_intent: Optional[str] = Field(None, description="PolicyAssistantIntent value string.")
    ambiguous_streak: int = Field(0, ge=0, le=20)
    had_supported_policy_turn: bool = False

    def to_json_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def for_scope(cls, scope_kind: str, scope_id: str) -> PolicyAssistantSessionState:
        return cls(v=1, scope_kind=scope_kind, scope_id=scope_id)


def parse_policy_assistant_session(
    raw: Optional[Dict[str, Any]],
    *,
    scope_kind: str,
    scope_id: str,
) -> PolicyAssistantSessionState:
    if not raw or not isinstance(raw, dict):
        return PolicyAssistantSessionState.for_scope(scope_kind, scope_id)
    try:
        s = PolicyAssistantSessionState.model_validate(raw)
        if s.v != 1 or s.scope_kind != scope_kind or s.scope_id != scope_id:
            return PolicyAssistantSessionState.for_scope(scope_kind, scope_id)
        return s
    except Exception:
        return PolicyAssistantSessionState.for_scope(scope_kind, scope_id)


def _topic_menu_ambiguity_text() -> str:
    parts: List[str] = []
    for t in POLICY_ASSISTANT_TOPIC_ORDER:
        parts.append(t.value.replace("_", " "))
    return "Too many unclear follow-ups. Name one benefit to continue: " + ", ".join(parts) + "."


def _is_ambiguous_unsupported(c: PolicyAssistantClassificationResult) -> bool:
    return (
        not c.supported
        and c.refusal_code == PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED
    )


def apply_bounded_session_memory(
    message: str,
    role: Union[str, PolicyAssistantRoleScope],
    state: PolicyAssistantSessionState,
    base_classification: PolicyAssistantClassificationResult,
    *,
    available_topics: Optional[Any] = None,
) -> PolicyAssistantClassificationResult:
    """
    Refine classification using bounded session: pronoun follow-ups, drift refusals,
    forced topic pick after repeated ambiguity.
    """
    rs = _parse_role(role)
    norm = _normalize_message(message)

    # Pronoun / ellipsis follow-up: carry last topic + last intent class (entitlement vs comparison)
    if (
        state.had_supported_policy_turn
        and state.last_canonical_topic
        and _is_ambiguous_unsupported(base_classification)
        and _PRONOUN_FOLLOWUP.search(norm)
    ):
        try:
            topic = PolicyAssistantCanonicalTopic(state.last_canonical_topic)
        except ValueError:
            topic = None
        if topic is not None:
            intent = PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION
            if state.last_intent == PolicyAssistantIntent.POLICY_COMPARISON_QUESTION.value:
                intent = PolicyAssistantIntent.POLICY_COMPARISON_QUESTION
            elif state.last_intent == PolicyAssistantIntent.POLICY_STATUS_QUESTION.value:
                intent = PolicyAssistantIntent.POLICY_STATUS_QUESTION
            return PolicyAssistantClassificationResult(
                supported=True,
                intent=intent,
                canonical_topic=topic,
                ambiguity_reason=None,
                refusal_code=None,
                normalized_question=base_classification.normalized_question,
            )

    # Forced bounded clarification (supported topics list only)
    if (
        state.ambiguous_streak >= _MAX_AMBIGUOUS_STREAK_BEFORE_MENU
        and _is_ambiguous_unsupported(base_classification)
    ):
        return PolicyAssistantClassificationResult(
            supported=True,
            intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
            canonical_topic=None,
            ambiguity_reason=_topic_menu_ambiguity_text(),
            refusal_code=None,
            normalized_question=base_classification.normalized_question,
            guardrail_note=SESSION_TOPIC_MENU_MARKER,
        )

    # Drift: vague follow-up after a supported policy turn, no policy anchor, no topic signal
    if (
        state.had_supported_policy_turn
        and _is_ambiguous_unsupported(base_classification)
        and not _POLICY_ANCHOR.search(norm)
        and not _PRONOUN_FOLLOWUP.search(norm)
    ):
        relaxed = score_policy_assistant_topics(message, available_topics, relaxed=True)
        best = max(relaxed.values()) if relaxed else 0
        if best < 4:
            return PolicyAssistantClassificationResult(
                supported=False,
                intent=PolicyAssistantIntent.UNSUPPORTED_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT,
                normalized_question=base_classification.normalized_question,
            )

    # Employee must not use HR draft threads even after a valid policy turn (classifier may route draft)
    if rs == PolicyAssistantRoleScope.EMPLOYEE and base_classification.supported:
        if base_classification.intent == PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION:
            return PolicyAssistantClassificationResult(
                supported=False,
                intent=PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT,
                normalized_question=base_classification.normalized_question,
            )

    return base_classification


def _truncate_summary(text: str) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= _MAX_SUMMARY_LEN:
        return t
    return t[: _MAX_SUMMARY_LEN - 1] + "…"


_OUT_OF_SCOPE_RESET: Tuple[PolicyAssistantRefusalCode, ...] = (
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_GENERAL,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_TAX_IMMIGRATION_TRAVEL,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_ADVICE,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_TAX_BEYOND_POLICY,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_NEGOTIATION,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_TRAVEL_OR_LIFESTYLE,
    PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT,
)


def update_session_after_turn(
    state: PolicyAssistantSessionState,
    final_classification: PolicyAssistantClassificationResult,
    answer: PolicyAssistantAnswer,
) -> PolicyAssistantSessionState:
    """Update bounded memory from this turn's final classification + answer."""
    base = PolicyAssistantSessionState.for_scope(state.scope_kind, state.scope_id)
    s = state.model_copy(deep=True)

    if answer.answer_type == PolicyAssistantAnswerType.REFUSAL and answer.refusal:
        code = answer.refusal.refusal_code
        if code == PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT:
            s.last_canonical_topic = None
            s.last_answer_summary = ""
            s.last_intent = None
            s.last_comparison_mode = None
            s.had_supported_policy_turn = False
            s.ambiguous_streak = 0
            return s
        if code in _OUT_OF_SCOPE_RESET:
            return base
        if code == PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED:
            s.ambiguous_streak = min(20, s.ambiguous_streak + 1)
            return s
        s.last_canonical_topic = None
        s.last_answer_summary = ""
        s.last_intent = None
        s.last_comparison_mode = None
        s.had_supported_policy_turn = False
        s.ambiguous_streak = 0
        return s

    if answer.answer_type == PolicyAssistantAnswerType.CLARIFICATION_NEEDED:
        if (final_classification.guardrail_note or "") == SESSION_TOPIC_MENU_MARKER:
            s.ambiguous_streak = 0
            return s
        s.ambiguous_streak = min(20, s.ambiguous_streak + 1)
        return s

    # Substantive success path
    s.had_supported_policy_turn = True
    s.ambiguous_streak = 0
    if final_classification.canonical_topic:
        s.last_canonical_topic = final_classification.canonical_topic.value
    s.last_intent = (
        final_classification.intent.value if final_classification.intent is not None else None
    )
    s.last_answer_summary = _truncate_summary(answer.answer_text or "")
    s.last_comparison_mode = answer.comparison_readiness.value
    if final_classification.intent == PolicyAssistantIntent.POLICY_COMPARISON_QUESTION:
        s.last_comparison_mode = "comparison_intent"
    return s


def classify_with_bounded_session(
    message: str,
    role: Union[str, PolicyAssistantRoleScope],
    state: PolicyAssistantSessionState,
    *,
    available_topics: Optional[Any] = None,
) -> PolicyAssistantClassificationResult:
    """Classify with guardrails, then apply bounded session refinements."""
    base = classify_policy_message_with_guardrails(message, role, available_topics)
    return apply_bounded_session_memory(message, role, state, base, available_topics=available_topics)
