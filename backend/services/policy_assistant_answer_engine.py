"""
Deterministic policy assistant answer generation from resolved effective policy slices.

No LLM reasoning: templates only, grounded on ``ResolvedPolicyContext`` built upstream
from DB / HR review payloads.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from .policy_assistant_classifier import PolicyAssistantClassificationResult
from .policy_assistant_contract import (
    POLICY_ASSISTANT_TOPIC_ORDER,
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantComparisonReadiness,
    PolicyAssistantConditionItem,
    PolicyAssistantEvidenceItem,
    PolicyAssistantFollowUpOption,
    PolicyAssistantIntent,
    PolicyAssistantPolicyStatus,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)
from .policy_assistant_refusal_service import (
    build_policy_refusal_answer,
    follow_ups_from_refusal,
    policy_assistant_refusal_for_code,
)


class PolicyAssistantResolvedTopic(BaseModel):
    """Effective topic row after resolution (caller supplies published-only for employees)."""

    model_config = ConfigDict(extra="forbid")

    included: bool = True
    explicitly_excluded: bool = Field(False, description="True if an exclusion row applies.")
    has_numeric_cap: bool = False
    cap_amount: Optional[float] = None
    cap_currency: Optional[str] = None
    cap_frequency: Optional[str] = Field(None, description="e.g. monthly, one_time, annual")
    approval_required: bool = False
    comparison_readiness: str = Field(
        "comparison_ready",
        description="Machine readiness: comparison_ready, informational_only, external_reference_partial, review_required, deterministic_non_budget",
    )
    section_ref: Optional[str] = None
    source_label: str = Field("Published policy", description="Human-facing evidence label.")
    policy_source_type: str = Field(
        "published_benefit_rule",
        description="published_benefit_rule | published_exclusion | published_matrix | draft_grouped_item | ...",
    )
    excerpt: Optional[str] = None
    benefit_reference: Optional[str] = Field(None, description="Stable id for evidence.reference.")


class ResolvedPolicyContext(BaseModel):
    """
    Pre-resolved policy for one company/case/version.

    For **employees**, populate ``topics`` only from published effective data.
    For **HR**, draft rows may appear with ``policy_source_type`` starting with ``draft_``.
    """

    model_config = ConfigDict(extra="forbid")

    has_published_benefits: bool = False
    draft_exists: bool = False
    draft_has_unpublished_changes: bool = False
    employee_visible_summary: Optional[str] = Field(
        None,
        description="One-line description of what employees currently see (published only).",
    )
    topicless_comparison_readiness: Optional[str] = Field(
        None,
        description="When the question is comparison-shaped without a topic (e.g. informational only).",
    )
    topics: Dict[str, PolicyAssistantResolvedTopic] = Field(default_factory=dict)
    hr_employee_visibility: Optional[Dict[str, Any]] = Field(
        None,
        description="HR review ``employee_visibility`` flags (published matrix, readiness).",
    )
    hr_published_topics: Dict[str, PolicyAssistantResolvedTopic] = Field(
        default_factory=dict,
        description="Published-only topic rows for HR employee-view explanations.",
    )
    hr_override_summary: Optional[str] = Field(
        None,
        description="Preformatted summary of HR rule overrides when present in loaded data.",
    )


_EMPLOYEE_PUBLISHED_PREFIXES = ("published_",)


def _parse_role(role: Union[str, PolicyAssistantRoleScope]) -> PolicyAssistantRoleScope:
    if isinstance(role, PolicyAssistantRoleScope):
        return role
    r = str(role or "").strip().lower()
    if r in ("hr", "admin"):
        return PolicyAssistantRoleScope.HR
    return PolicyAssistantRoleScope.EMPLOYEE


def _topic_title(topic: PolicyAssistantCanonicalTopic) -> str:
    return topic.value.replace("_", " ").title()


def _map_comparison_readiness(raw: Optional[str]) -> PolicyAssistantComparisonReadiness:
    if not raw:
        return PolicyAssistantComparisonReadiness.NOT_APPLICABLE
    key = str(raw).strip().lower()
    mapping = {
        "comparison_ready": PolicyAssistantComparisonReadiness.COMPARISON_READY,
        "informational_only": PolicyAssistantComparisonReadiness.INFORMATIONAL_ONLY,
        "external_reference_partial": PolicyAssistantComparisonReadiness.EXTERNAL_REFERENCE_PARTIAL,
        "review_required": PolicyAssistantComparisonReadiness.REVIEW_REQUIRED,
        "deterministic_non_budget": PolicyAssistantComparisonReadiness.DETERMINISTIC_NON_BUDGET,
        "not_applicable": PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
    }
    return mapping.get(key, PolicyAssistantComparisonReadiness.NOT_APPLICABLE)


def _format_cap(row: PolicyAssistantResolvedTopic) -> Optional[str]:
    if not row.has_numeric_cap or row.cap_amount is None:
        return None
    cur = (row.cap_currency or "").strip().upper()
    num = row.cap_amount
    try:
        if num == int(num):
            num_s = f"{int(num):,}"
        else:
            num_s = f"{num:,.2f}"
    except (TypeError, ValueError):
        num_s = str(num)
    base = f"{cur} {num_s}".strip() if cur else num_s
    if row.cap_frequency:
        freq = row.cap_frequency.replace("_", " ")
        return f"{base} ({freq})"
    return base


def _comparison_qualifier(readiness: PolicyAssistantComparisonReadiness) -> str:
    if readiness == PolicyAssistantComparisonReadiness.COMPARISON_READY:
        return ""
    if readiness == PolicyAssistantComparisonReadiness.INFORMATIONAL_ONLY:
        return (
            " ReloPass treats this topic as **informational** for cost comparison: "
            "there is no reliable numeric cap to compare in the published data."
        )
    if readiness in (
        PolicyAssistantComparisonReadiness.EXTERNAL_REFERENCE_PARTIAL,
        PolicyAssistantComparisonReadiness.REVIEW_REQUIRED,
    ):
        return (
            " ReloPass marks this topic as **not fully comparison-ready** "
            "(external reference, missing detail, or review needed). "
            "The assistant does **not** invent numeric comparisons."
        )
    if readiness == PolicyAssistantComparisonReadiness.DETERMINISTIC_NON_BUDGET:
        return " This item reflects eligibility or exclusion logic rather than a budget cap."
    return ""


def _evidence_for_topic(topic: PolicyAssistantCanonicalTopic, row: PolicyAssistantResolvedTopic) -> PolicyAssistantEvidenceItem:
    return PolicyAssistantEvidenceItem(
        kind="benefit_rule",
        label=row.source_label,
        reference=row.benefit_reference or topic.value,
        excerpt=row.excerpt,
        source="published_matrix" if row.policy_source_type.startswith("published") else "draft_review",
        section_ref=row.section_ref,
        policy_source_type=row.policy_source_type,
    )


def _follow_ups(current: Optional[PolicyAssistantCanonicalTopic]) -> List[PolicyAssistantFollowUpOption]:
    out: List[PolicyAssistantFollowUpOption] = []
    for t in POLICY_ASSISTANT_TOPIC_ORDER:
        if current is not None and t == current:
            continue
        title = _topic_title(t)
        out.append(
            PolicyAssistantFollowUpOption(
                intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
                label=f"Ask about {title}",
                query_hint=f"What does my policy say about {title.lower()}?",
            )
        )
        if len(out) >= 3:
            break
    return out


def _hr_publish_preview_suffix(
    classification: PolicyAssistantClassificationResult,
    rs: PolicyAssistantRoleScope,
    ctx: ResolvedPolicyContext,
) -> str:
    if rs != PolicyAssistantRoleScope.HR or not ctx.draft_has_unpublished_changes:
        return ""
    if classification.intent != PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION:
        return ""
    nq = (classification.normalized_question or "").lower()
    if "publish" not in nq:
        return ""
    if not re.search(r"\bemployees see\b|\bemployee view\b|\bworkers see\b", nq):
        return ""
    return (
        " After you **publish** this working version, employees will see these limits in their "
        "**published** policy view."
    )


def _maybe_prepend_guardrail_note(
    answer: PolicyAssistantAnswer,
    note: Optional[str],
) -> PolicyAssistantAnswer:
    if (
        not (note or "").strip()
        or answer.answer_type == PolicyAssistantAnswerType.REFUSAL
        or not (answer.answer_text or "").strip()
    ):
        return answer
    return answer.model_copy(
        update={"answer_text": f"{note.strip()}\n\n{answer.answer_text}".strip()}
    )


def _employee_may_use_row(row: PolicyAssistantResolvedTopic) -> bool:
    pst = row.policy_source_type or ""
    return any(pst.startswith(p) for p in _EMPLOYEE_PUBLISHED_PREFIXES)


def generate_policy_assistant_answer(
    classification: PolicyAssistantClassificationResult,
    resolved_policy_context: ResolvedPolicyContext,
    role: Union[str, PolicyAssistantRoleScope],
) -> PolicyAssistantAnswer:
    """
    Build a structured answer from classification + pre-resolved policy context.

    Caller must pass **published-only** topic rows for employees; draft rows may appear for HR.
    """
    rs = _parse_role(role)

    if not classification.supported:
        return build_policy_refusal_answer(classification, rs)

    if rs == PolicyAssistantRoleScope.EMPLOYEE and classification.intent == PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION:
        return build_policy_refusal_answer(
            classification.model_copy(
                update={
                    "supported": False,
                    "refusal_code": PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT,
                }
            ),
            rs,
        )

    if rs == PolicyAssistantRoleScope.HR and classification.intent == PolicyAssistantIntent.EMPLOYEE_VISIBILITY_QUESTION:
        ev = resolved_policy_context.hr_employee_visibility or {}
        sees = ev.get("employee_sees_published_policy_matrix")
        prs = str(ev.get("publish_readiness_status") or "").strip()
        crs = str(ev.get("comparison_readiness_status") or "").strip()
        crs_strict = ev.get("comparison_ready_strict")
        parts = [
            "Employees only see **published** policy content in their ReloPass experience—not the HR-only working draft.",
        ]
        if resolved_policy_context.employee_visible_summary:
            parts.append(str(resolved_policy_context.employee_visible_summary))
        parts.append(
            f"Published benefit matrix visible to employees today: **{'yes' if sees else 'no'}**."
        )
        if prs or crs:
            parts.append(f"(Signals: publish readiness={prs or 'n/a'}, comparison={crs or 'n/a'}, strict={crs_strict!r}).")
        body = " ".join(parts)
        if resolved_policy_context.draft_exists and resolved_policy_context.has_published_benefits:
            pol_st = PolicyAssistantPolicyStatus.DRAFT_AND_PUBLISHED
        elif resolved_policy_context.draft_exists:
            pol_st = PolicyAssistantPolicyStatus.DRAFT
        else:
            pol_st = PolicyAssistantPolicyStatus.PUBLISHED
        return PolicyAssistantAnswer(
            answer_type=PolicyAssistantAnswerType.STATUS_SUMMARY,
            canonical_topic=None,
            answer_text=body,
            policy_status=pol_st,
            comparison_readiness=PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
            evidence=[],
            conditions=[],
            approval_required=False,
            follow_up_options=_follow_ups(None),
            refusal=None,
            role_scope=rs,
            detected_intent=classification.intent,
        )

    if rs == PolicyAssistantRoleScope.HR and classification.intent == PolicyAssistantIntent.OVERRIDE_EFFECT_QUESTION:
        if resolved_policy_context.hr_override_summary:
            body = (
                "HR **overrides** change how specific benefit rules are interpreted for this **working policy version** "
                "in ReloPass.\n\n"
                f"{resolved_policy_context.hr_override_summary}"
            )
            return PolicyAssistantAnswer(
                answer_type=PolicyAssistantAnswerType.STATUS_SUMMARY,
                canonical_topic=None,
                answer_text=body.strip(),
                policy_status=PolicyAssistantPolicyStatus.DRAFT
                if resolved_policy_context.draft_exists
                else PolicyAssistantPolicyStatus.PUBLISHED,
                comparison_readiness=PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
                evidence=[],
                conditions=[],
                approval_required=False,
                follow_up_options=_follow_ups(None),
                refusal=None,
                role_scope=rs,
                detected_intent=classification.intent,
            )
        return build_policy_refusal_answer(
            PolicyAssistantClassificationResult(
                supported=False,
                intent=PolicyAssistantIntent.OVERRIDE_EFFECT_QUESTION,
                canonical_topic=None,
                refusal_code=PolicyAssistantRefusalCode.INSUFFICIENT_POLICY_DATA,
                normalized_question=classification.normalized_question,
            ),
            rs,
        )

    if classification.intent == PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION and rs == PolicyAssistantRoleScope.HR:
        ev: List[PolicyAssistantEvidenceItem] = []
        if resolved_policy_context.draft_exists:
            ev.append(
                PolicyAssistantEvidenceItem(
                    kind="normalization_draft",
                    label="Working draft (HR)",
                    reference="draft",
                    excerpt=None,
                    source="draft_review",
                    section_ref=None,
                    policy_source_type="draft_normalization",
                )
            )
        if resolved_policy_context.has_published_benefits:
            ev.append(
                PolicyAssistantEvidenceItem(
                    kind="published_version",
                    label="Published version (employees)",
                    reference="published",
                    excerpt=resolved_policy_context.employee_visible_summary,
                    source="published_matrix",
                    section_ref=None,
                    policy_source_type="published_version",
                )
            )
        parts = [
            "The **draft** you are editing in ReloPass is **not live** for employees until it is published.",
            "Employees currently see the **published** policy only.",
        ]
        if resolved_policy_context.employee_visible_summary:
            parts.append(f"What employees see today: {resolved_policy_context.employee_visible_summary}")
        if resolved_policy_context.draft_has_unpublished_changes:
            parts.append("There are **unpublished changes** in the working draft.")
        body = " ".join(parts)
        return _maybe_prepend_guardrail_note(
            PolicyAssistantAnswer(
                answer_type=PolicyAssistantAnswerType.DRAFT_PUBLISHED_SUMMARY,
                canonical_topic=None,
                answer_text=body,
                policy_status=PolicyAssistantPolicyStatus.DRAFT_AND_PUBLISHED
                if resolved_policy_context.draft_exists and resolved_policy_context.has_published_benefits
                else PolicyAssistantPolicyStatus.DRAFT
                if resolved_policy_context.draft_exists
                else PolicyAssistantPolicyStatus.PUBLISHED,
                comparison_readiness=PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
                evidence=ev,
                conditions=[],
                approval_required=False,
                follow_up_options=_follow_ups(None),
                refusal=None,
                role_scope=rs,
                detected_intent=classification.intent,
            ),
            classification.guardrail_note,
        )

    if classification.intent == PolicyAssistantIntent.POLICY_COMPARISON_QUESTION and classification.canonical_topic is None:
        raw = resolved_policy_context.topicless_comparison_readiness or "informational_only"
        cr = _map_comparison_readiness(raw)
        body = (
            "ReloPass marks this topic as **not fully comparison-ready** for automated dollar comparisons."
            if cr != PolicyAssistantComparisonReadiness.COMPARISON_READY
            else "This topic is comparison-ready where numeric caps exist in published data."
        )
        body += _comparison_qualifier(cr)
        return PolicyAssistantAnswer(
            answer_type=PolicyAssistantAnswerType.COMPARISON_SUMMARY,
            canonical_topic=None,
            answer_text=body.strip(),
            policy_status=PolicyAssistantPolicyStatus.PUBLISHED
            if resolved_policy_context.has_published_benefits
            else PolicyAssistantPolicyStatus.NO_POLICY_BOUND,
            comparison_readiness=cr,
            evidence=[],
            conditions=[],
            approval_required=False,
            follow_up_options=_follow_ups(None),
            refusal=None,
            role_scope=rs,
            detected_intent=classification.intent,
        )

    topic = classification.canonical_topic
    if topic is None:
        ref = PolicyAssistantRefusal(
            refusal_code=PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED,
            refusal_text=classification.ambiguity_reason or "Please name a specific policy topic.",
            supported_examples=[],
        )
        return PolicyAssistantAnswer(
            answer_type=PolicyAssistantAnswerType.CLARIFICATION_NEEDED,
            canonical_topic=None,
            answer_text="",
            policy_status=PolicyAssistantPolicyStatus.UNKNOWN,
            comparison_readiness=PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
            evidence=[],
            conditions=[],
            approval_required=False,
            follow_up_options=_follow_ups(None),
            refusal=ref,
            role_scope=rs,
            detected_intent=classification.intent,
        )

    row = resolved_policy_context.topics.get(topic.value)
    if row is None:
        if rs == PolicyAssistantRoleScope.EMPLOYEE and not resolved_policy_context.has_published_benefits:
            return build_policy_refusal_answer(
                PolicyAssistantClassificationResult(
                    supported=False,
                    intent=classification.intent,
                    canonical_topic=topic,
                    refusal_code=PolicyAssistantRefusalCode.NO_PUBLISHED_POLICY_EMPLOYEE,
                    normalized_question=classification.normalized_question,
                ),
                rs,
            )
        title = _topic_title(topic)
        body = f"**{title}** is **not included** in the published policy data ReloPass has for this case."
        return _maybe_prepend_guardrail_note(
            PolicyAssistantAnswer(
                answer_type=PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY,
                canonical_topic=topic,
                answer_text=body,
                policy_status=PolicyAssistantPolicyStatus.PUBLISHED,
                comparison_readiness=PolicyAssistantComparisonReadiness.NOT_APPLICABLE,
                evidence=[],
                conditions=[],
                approval_required=False,
                follow_up_options=_follow_ups(topic),
                refusal=None,
                role_scope=rs,
                detected_intent=classification.intent,
            ),
            classification.guardrail_note,
        )

    if rs == PolicyAssistantRoleScope.EMPLOYEE and not _employee_may_use_row(row):
        return build_policy_refusal_answer(
            classification.model_copy(
                update={
                    "supported": False,
                    "refusal_code": PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT,
                    "canonical_topic": topic,
                }
            ),
            rs,
        )

    cr = _map_comparison_readiness(row.comparison_readiness)
    title = _topic_title(topic)
    policy_st = (
        PolicyAssistantPolicyStatus.PUBLISHED
        if row.policy_source_type.startswith("published")
        else PolicyAssistantPolicyStatus.DRAFT
    )
    if rs == PolicyAssistantRoleScope.HR and resolved_policy_context.draft_exists and not row.policy_source_type.startswith(
        "published"
    ):
        policy_st = PolicyAssistantPolicyStatus.DRAFT

    if row.explicitly_excluded or not row.included:
        body = f"**{title}** is **not included** in the published policy for this case."
        if rs == PolicyAssistantRoleScope.HR and row.policy_source_type.startswith("draft"):
            body = f"**{title}** is marked **not included** in the **draft** data you are viewing."
        body = body + _comparison_qualifier(cr) + _hr_publish_preview_suffix(classification, rs, resolved_policy_context)
        return _maybe_prepend_guardrail_note(
            PolicyAssistantAnswer(
                answer_type=PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY,
                canonical_topic=topic,
                answer_text=body.strip(),
                policy_status=policy_st,
                comparison_readiness=cr,
                evidence=[_evidence_for_topic(topic, row)],
                conditions=[],
                approval_required=False,
                follow_up_options=_follow_ups(topic),
                refusal=None,
                role_scope=rs,
                detected_intent=classification.intent,
            ),
            classification.guardrail_note,
        )

    cap_s = _format_cap(row)
    if row.has_numeric_cap and cap_s:
        body = f"For your case, **{title}** is **included** up to **{cap_s}** in the policy data ReloPass is using."
    elif row.has_numeric_cap and not cap_s:
        body = (
            f"**{title}** is **included**, but **no complete numeric cap** "
            f"(amount and currency) is defined in the published policy data for this case."
        )
    else:
        body = (
            f"**{title}** is **included** in the policy data, but **no numeric cap is defined** "
            f"in the published policy ReloPass has for this case."
        )

    if row.approval_required:
        body += " This item **may be subject to approval** according to the policy text."

    body += _comparison_qualifier(cr)
    body += _hr_publish_preview_suffix(classification, rs, resolved_policy_context)

    conditions: List[PolicyAssistantConditionItem] = []
    if row.approval_required:
        conditions.append(
            PolicyAssistantConditionItem(
                text="Approval or exception may be required before reimbursement or booking.",
                kind="approval",
            )
        )

    atype = PolicyAssistantAnswerType.ENTITLEMENT_SUMMARY
    if classification.intent == PolicyAssistantIntent.POLICY_COMPARISON_QUESTION:
        atype = PolicyAssistantAnswerType.COMPARISON_SUMMARY

    return _maybe_prepend_guardrail_note(
        PolicyAssistantAnswer(
            answer_type=atype,
            canonical_topic=topic,
            answer_text=body.strip(),
            policy_status=policy_st,
            comparison_readiness=cr,
            evidence=[_evidence_for_topic(topic, row)],
            conditions=conditions,
            approval_required=row.approval_required,
            follow_up_options=_follow_ups(topic),
            refusal=None,
            role_scope=rs,
            detected_intent=classification.intent,
        ),
        classification.guardrail_note,
    )
