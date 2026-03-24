"""
Employee policy assistant: resolve published policy for an assignment and run classifier + answer engine.

Never loads draft or unpublished normalization — uses the same published resolution path as
``GET /api/employee/assignments/{id}/policy``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .policy_assistant_answer_engine import (
    PolicyAssistantResolvedTopic,
    ResolvedPolicyContext,
    generate_policy_assistant_answer,
)
from .policy_assistant_contract import PolicyAssistantAnswer, PolicyAssistantCanonicalTopic, PolicyAssistantRoleScope
from .policy_assistant_analytics import record_policy_assistant_turn
from .policy_assistant_session_service import (
    classify_with_bounded_session,
    parse_policy_assistant_session,
    update_session_after_turn,
)
from .policy_taxonomy import BENEFIT_TAXONOMY

# Canonical assistant topic -> benefit_key(s) in resolved_assignment_policy_benefits
TOPIC_BENEFIT_KEYS: Dict[PolicyAssistantCanonicalTopic, Tuple[str, ...]] = {
    PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING: ("temporary_housing",),
    PolicyAssistantCanonicalTopic.HOME_SEARCH: ("scouting_trip", "relocation_services"),
    PolicyAssistantCanonicalTopic.SHIPMENT: ("shipment", "movers", "household_goods", "storage"),
    PolicyAssistantCanonicalTopic.SCHOOL_SEARCH: ("schooling", "tuition", "schools"),
    PolicyAssistantCanonicalTopic.SPOUSE_SUPPORT: ("spouse_support",),
    PolicyAssistantCanonicalTopic.VISA_SUPPORT: ("immigration",),
    PolicyAssistantCanonicalTopic.WORK_PERMIT_SUPPORT: ("immigration",),
    PolicyAssistantCanonicalTopic.TAX_BRIEFING: ("tax",),
    PolicyAssistantCanonicalTopic.TAX_RETURN_SUPPORT: ("tax",),
    PolicyAssistantCanonicalTopic.HOME_LEAVE: ("home_leave",),
    PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE: (
        "settling_in_allowance",
        "mobility_premium",
        "location_allowance",
        "cola",
        "remote_premium",
    ),
    PolicyAssistantCanonicalTopic.HOST_HOUSING: ("housing",),
}


def _canonical_benefit_key(raw: str) -> str:
    k = (raw or "").strip()
    meta = BENEFIT_TAXONOMY.get(k) or {}
    mapped = meta.get("maps_to")
    if isinstance(mapped, str) and mapped:
        return mapped
    return k


def _topic_keys_expanded(keys: Tuple[str, ...]) -> Set[str]:
    out: Set[str] = set(keys)
    for k in keys:
        out.add(_canonical_benefit_key(k))
    return out


def _best_benefit_for_keys(benefits: List[Dict[str, Any]], keys: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
    expanded = _topic_keys_expanded(keys)
    rows = [
        b
        for b in benefits
        if str(b.get("benefit_key") or "") in expanded
        or _canonical_benefit_key(str(b.get("benefit_key") or "")) in expanded
    ]
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]

    def score(b: Dict[str, Any]) -> Tuple[int, float]:
        inc = 1 if b.get("included") else 0
        m = 0.0
        for v in (b.get("max_value"), b.get("standard_value"), b.get("min_value")):
            if v is not None:
                try:
                    m = max(m, float(v))
                except (TypeError, ValueError):
                    pass
        return (inc, m)

    return max(rows, key=score)


def _rule_readiness_to_engine(raw: Optional[Dict[str, Any]], *, included: bool) -> str:
    if not raw or not isinstance(raw, dict):
        if not included:
            return "not_applicable"
        return "informational_only"
    level = (raw.get("level") or "").strip().lower()
    supports_delta = bool(raw.get("supports_budget_delta"))
    if level == "full" and supports_delta:
        return "comparison_ready"
    if level == "full":
        return "deterministic_non_budget"
    if level == "partial":
        return "external_reference_partial"
    if level == "not_ready":
        return "review_required"
    return "informational_only"


def _benefit_row_to_topic(row: Dict[str, Any]) -> PolicyAssistantResolvedTopic:
    included = bool(row.get("included", True))
    max_v = row.get("max_value")
    std_v = row.get("standard_value")
    min_v = row.get("min_value")
    cap_amount = None
    for v in (max_v, std_v, min_v):
        if v is not None:
            try:
                cap_amount = float(v)
                if cap_amount > 0:
                    break
            except (TypeError, ValueError):
                continue
    has_cap = cap_amount is not None and cap_amount > 0
    currency = (row.get("currency") or "").strip() or None
    approval = bool(row.get("approval_required"))
    rc = row.get("rule_comparison_readiness")
    comparison_readiness = _rule_readiness_to_engine(rc if isinstance(rc, dict) else None, included=included)
    excerpt = (row.get("condition_summary") or row.get("description") or "").strip() or None
    return PolicyAssistantResolvedTopic(
        included=included,
        explicitly_excluded=not included,
        has_numeric_cap=has_cap,
        cap_amount=cap_amount if has_cap else None,
        cap_currency=currency,
        cap_frequency=None,
        approval_required=approval,
        comparison_readiness=comparison_readiness,
        section_ref=None,
        source_label="Published assignment policy",
        policy_source_type="published_benefit_rule",
        excerpt=excerpt,
        benefit_reference=str(row.get("benefit_key") or row.get("id") or ""),
    )


def resolved_topic_from_benefit_row(
    row: Dict[str, Any],
    *,
    policy_source_type: str = "published_benefit_rule",
    source_label: Optional[str] = None,
) -> PolicyAssistantResolvedTopic:
    """Build a resolved topic row; use non-default ``policy_source_type`` for HR working draft rules."""
    t = _benefit_row_to_topic(row)
    return t.model_copy(
        update={
            "policy_source_type": policy_source_type,
            "source_label": source_label or t.source_label,
        }
    )


def build_resolved_policy_context_from_employee_resolution(resolution: Dict[str, Any]) -> ResolvedPolicyContext:
    """
    Map employee policy resolution (from ``_resolve_published_policy_for_employee``) to answer-engine context.

    Published only; ``draft_exists`` is always False. When version-level comparison is off, benefits may be empty
    but ``has_published_benefits`` can still be True — topic rows will be missing and the engine answers accordingly.
    """
    has_policy = bool(resolution.get("has_policy"))
    benefits = resolution.get("benefits") or []
    if not isinstance(benefits, list):
        benefits = []
    exclusions = resolution.get("exclusions") or []
    if not isinstance(exclusions, list):
        exclusions = []

    cr = resolution.get("comparison_readiness") or {}
    topicless = None
    if isinstance(cr, dict):
        if not cr.get("comparison_ready"):
            if cr.get("partial_numeric_coverage"):
                topicless = "external_reference_partial"
            else:
                topicless = "review_required"

    topics: Dict[str, PolicyAssistantResolvedTopic] = {}

    for topic, keys in TOPIC_BENEFIT_KEYS.items():
        b = _best_benefit_for_keys(benefits, keys)
        if b is not None:
            topics[topic.value] = _benefit_row_to_topic(b)

    # Exclusions with benefit_key: mark topic excluded when no stronger benefit row
    for ex in exclusions:
        bk_raw = str(ex.get("benefit_key") or "").strip()
        if not bk_raw:
            continue
        bk = _canonical_benefit_key(bk_raw)
        for topic, keys in TOPIC_BENEFIT_KEYS.items():
            expanded = _topic_keys_expanded(keys)
            if bk_raw not in expanded and bk not in expanded:
                continue
            if topic.value in topics:
                continue
            desc = (ex.get("description") or "").strip() or None
            topics[topic.value] = PolicyAssistantResolvedTopic(
                included=False,
                explicitly_excluded=True,
                has_numeric_cap=False,
                comparison_readiness="not_applicable",
                source_label="Published policy exclusion",
                policy_source_type="published_exclusion",
                excerpt=desc,
                benefit_reference=bk,
            )

    policy_summary = resolution.get("policy") or {}
    employee_visible = None
    if isinstance(policy_summary, dict):
        parts = [
            policy_summary.get("title"),
            policy_summary.get("version"),
            policy_summary.get("company_name"),
        ]
        employee_visible = " — ".join(str(p) for p in parts if p)

    return ResolvedPolicyContext(
        has_published_benefits=has_policy,
        draft_exists=False,
        draft_has_unpublished_changes=False,
        employee_visible_summary=employee_visible,
        topicless_comparison_readiness=topicless,
        topics=topics,
    )


def execute_employee_policy_assistant_query(
    assignment_id: str,
    message: str,
    user: Dict[str, Any],
    request_id: Optional[str] = None,
    *,
    resolve_published_policy: Optional[
        Callable[..., Dict[str, Any]]
    ] = None,
    session: Optional[Dict[str, Any]] = None,
) -> Tuple[PolicyAssistantAnswer, Optional[str], Dict[str, Any]]:
    """
    Full pipeline: published resolution, classify + guardrails, deterministic answer.

    ``resolve_published_policy`` defaults to ``main._resolve_published_policy_for_employee`` (lazy import).
    Returns ``(answer, request_id, session_dict)``. Raises HTTPException from resolution on visibility errors.
    """
    resolver = resolve_published_policy
    if resolver is None:
        from backend.main import _resolve_published_policy_for_employee as resolver

    resolution = resolver(
        assignment_id,
        user,
        request_id,
        read_only=True,
    )
    sess = parse_policy_assistant_session(
        session,
        scope_kind="employee_assignment",
        scope_id=str(assignment_id).strip(),
    )
    classification = classify_with_bounded_session(
        message,
        PolicyAssistantRoleScope.EMPLOYEE,
        sess,
        available_topics=None,
    )
    ctx = build_resolved_policy_context_from_employee_resolution(resolution)
    answer = generate_policy_assistant_answer(
        classification,
        ctx,
        PolicyAssistantRoleScope.EMPLOYEE,
    )
    record_policy_assistant_turn(
        message=message,
        role=PolicyAssistantRoleScope.EMPLOYEE,
        classification=classification,
        answer=answer,
        ctx=ctx,
        request_id=request_id,
        employee_resolution=resolution if isinstance(resolution, dict) else None,
    )
    next_sess = update_session_after_turn(sess, classification, answer)
    return answer, request_id, next_sess.to_json_dict()


def employee_policy_assistant_query_response_dict(
    assignment_id: str,
    message: str,
    user: Dict[str, Any],
    request_id: Optional[str] = None,
    *,
    resolve_published_policy: Optional[Callable[..., Dict[str, Any]]] = None,
    session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """JSON-serializable envelope for the HTTP API."""
    answer, rid, sess_out = execute_employee_policy_assistant_query(
        assignment_id,
        message,
        user,
        request_id=request_id,
        resolve_published_policy=resolve_published_policy,
        session=session,
    )
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "request_id": rid,
        "answer": answer.model_dump(mode="json"),
        "session": sess_out,
    }
