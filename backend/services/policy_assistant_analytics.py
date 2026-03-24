"""
Policy Assistant analytics — bounded, non-content events via analytics_service.emit_event.

Does not log raw user questions or policy text. Uses enums, buckets, and request_id correlation only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .analytics_service import emit_event
from .policy_assistant_answer_engine import ResolvedPolicyContext
from .policy_assistant_classifier import PolicyAssistantClassificationResult
from .policy_assistant_contract import (
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantRoleScope,
)

log = logging.getLogger(__name__)

# Event names (query analytics_events.event_name)
EVENT_ASSISTANT_QUESTION_ASKED = "assistant_question_asked"
EVENT_ASSISTANT_QUESTION_SUPPORTED = "assistant_question_supported"
EVENT_ASSISTANT_QUESTION_UNSUPPORTED = "assistant_question_unsupported"
EVENT_ASSISTANT_ANSWER_GENERATED = "assistant_answer_generated"
EVENT_ASSISTANT_ANSWER_TOPIC = "assistant_answer_topic"
EVENT_ASSISTANT_ANSWER_READINESS = "assistant_answer_readiness"
EVENT_ASSISTANT_FOLLOW_UP_CLICKED = "assistant_follow_up_clicked"
EVENT_ASSISTANT_REFUSAL_SHOWN = "assistant_refusal_shown"


def _role_str(role: PolicyAssistantRoleScope) -> str:
    return "HR" if role == PolicyAssistantRoleScope.HR else "employee"


def _message_length_bucket(message: str) -> str:
    n = len((message or "").strip())
    if n <= 48:
        return "short"
    if n <= 200:
        return "medium"
    return "long"


def _employee_policy_readiness_bucket(
    resolution: Optional[Dict[str, Any]],
    ctx: ResolvedPolicyContext,
) -> str:
    if not ctx.has_published_benefits:
        return "no_published"
    cr = (resolution or {}).get("comparison_readiness") if isinstance(resolution, dict) else None
    if isinstance(cr, dict):
        if cr.get("comparison_ready"):
            if cr.get("partial_numeric_coverage"):
                return "published_partial_numeric"
            return "published_comparison_ready"
        return "published_comparison_not_ready"
    if ctx.topicless_comparison_readiness == "external_reference_partial":
        return "published_partial_matrix"
    if ctx.topicless_comparison_readiness == "review_required":
        return "published_review_required"
    return "published_unknown_readiness"


def _hr_policy_workspace_bucket(ctx: ResolvedPolicyContext) -> str:
    if not ctx.has_published_benefits and not ctx.draft_exists:
        return "no_workspace_data"
    if ctx.draft_has_unpublished_changes and ctx.has_published_benefits:
        return "draft_with_published"
    if ctx.draft_exists and not ctx.has_published_benefits:
        return "draft_only"
    if ctx.has_published_benefits:
        return "published_focus"
    return "other"


def _emit(name: str, **kwargs: Any) -> None:
    try:
        emit_event(name, **kwargs)
    except Exception as exc:
        log.debug("policy_assistant_analytics emit failed (non-fatal): %s", exc)


def record_policy_assistant_turn(
    *,
    message: str,
    role: PolicyAssistantRoleScope,
    classification: PolicyAssistantClassificationResult,
    answer: PolicyAssistantAnswer,
    ctx: ResolvedPolicyContext,
    request_id: Optional[str],
    employee_resolution: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit one turn's analytics. Safe to call on every query; failures are swallowed by emit_event chain.
    Omits user_id and assignment/policy ids from payload to limit PII (request_id + role only).
    """
    rs = _role_str(role)
    policy_bucket = (
        _employee_policy_readiness_bucket(employee_resolution, ctx)
        if role == PolicyAssistantRoleScope.EMPLOYEE
        else _hr_policy_workspace_bucket(ctx)
    )

    _emit(
        EVENT_ASSISTANT_QUESTION_ASKED,
        request_id=request_id,
        user_role=rs,
        extra={
            "message_length_bucket": _message_length_bucket(message),
            "policy_readiness_bucket": policy_bucket,
            "scope": "employee" if role == PolicyAssistantRoleScope.EMPLOYEE else "hr_policy",
        },
    )

    if classification.supported:
        _emit(
            EVENT_ASSISTANT_QUESTION_SUPPORTED,
            request_id=request_id,
            user_role=rs,
            extra={
                "detected_intent": classification.intent.value if classification.intent else None,
                "policy_readiness_bucket": policy_bucket,
            },
        )
    else:
        _emit(
            EVENT_ASSISTANT_QUESTION_UNSUPPORTED,
            request_id=request_id,
            user_role=rs,
            extra={
                "refusal_code": classification.refusal_code.value if classification.refusal_code else None,
                "policy_readiness_bucket": policy_bucket,
            },
        )

    _emit(
        EVENT_ASSISTANT_ANSWER_GENERATED,
        request_id=request_id,
        user_role=rs,
        extra={
            "answer_type": answer.answer_type.value,
            "policy_readiness_bucket": policy_bucket,
            "comparison_readiness": answer.comparison_readiness.value,
        },
    )

    topic_val = answer.canonical_topic.value if answer.canonical_topic else None
    if topic_val:
        _emit(
            EVENT_ASSISTANT_ANSWER_TOPIC,
            request_id=request_id,
            user_role=rs,
            extra={
                "canonical_topic": topic_val,
                "policy_readiness_bucket": policy_bucket,
            },
        )

    _emit(
        EVENT_ASSISTANT_ANSWER_READINESS,
        request_id=request_id,
        user_role=rs,
        extra={
            "comparison_readiness": answer.comparison_readiness.value,
            "policy_readiness_bucket": policy_bucket,
            "answer_type": answer.answer_type.value,
        },
    )

    if answer.answer_type == PolicyAssistantAnswerType.REFUSAL and answer.refusal:
        _emit(
            EVENT_ASSISTANT_REFUSAL_SHOWN,
            request_id=request_id,
            user_role=rs,
            extra={
                "refusal_code": answer.refusal.refusal_code.value,
                "policy_readiness_bucket": policy_bucket,
            },
        )


def emit_assistant_follow_up_clicked(
    *,
    role: PolicyAssistantRoleScope,
    request_id: Optional[str],
    follow_up_intent: Optional[str] = None,
    follow_up_index: Optional[int] = None,
    canonical_topic: Optional[str] = None,
) -> None:
    """Client-triggered: user chose a suggested follow-up (no free-text)."""
    _emit(
        EVENT_ASSISTANT_FOLLOW_UP_CLICKED,
        request_id=request_id,
        user_role=_role_str(role),
        extra={
            "follow_up_intent": (follow_up_intent or "")[:80] or None,
            "follow_up_index": follow_up_index,
            "canonical_topic": (canonical_topic or "")[:64] or None,
        },
    )
