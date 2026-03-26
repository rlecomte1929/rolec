"""
HR policy assistant: load policy review payload (draft + Layer 2) and run classifier + answer engine.

Uses the same aggregate as ``GET /api/hr/policy-review``; never answers outside bounded policy data.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from .employee_policy_assistant_service import (
    TOPIC_BENEFIT_KEYS,
    _best_benefit_for_keys,
    resolved_topic_from_benefit_row,
)
from .policy_assistant_answer_engine import (
    PolicyAssistantResolvedTopic,
    ResolvedPolicyContext,
    generate_policy_assistant_answer,
)
from .policy_assistant_contract import (
    PolicyAssistantAnswer,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantRoleScope,
)
from .policy_assistant_analytics import record_policy_assistant_turn
from .policy_assistant_session_service import (
    classify_with_bounded_session,
    parse_policy_assistant_session,
    update_session_after_turn,
)
from .policy_comparison_readiness import _parse_metadata
from .policy_rule_comparison_readiness import evaluate_rule_comparison_readiness


def _synthetic_benefit_from_layer2_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    meta = _parse_metadata(rule)
    bk = (
        (rule.get("benefit_key") or rule.get("benefit_category") or rule.get("domain") or "")
        .strip()
        .lower()
    )
    try:
        av = rule.get("amount_value")
        max_v = float(av) if av is not None else None
    except (TypeError, ValueError):
        max_v = None
    try:
        rc = evaluate_rule_comparison_readiness(dict(rule), rule_kind="benefit_rule")
    except Exception:
        rc = None
    included = True
    if meta.get("allowed") is False:
        included = False
    raw_txt = (rule.get("raw_text") or rule.get("description") or "")[:500]
    return {
        "benefit_key": bk or "unknown",
        "included": included,
        "max_value": max_v,
        "standard_value": meta.get("standard_value"),
        "min_value": meta.get("min_value"),
        "currency": rule.get("currency") or meta.get("currency"),
        "approval_required": bool(meta.get("approval_required")),
        "rule_comparison_readiness": rc,
        "condition_summary": raw_txt,
        "id": rule.get("id"),
    }


def _topic_from_grouped_item(item: Dict[str, Any]) -> Optional[PolicyAssistantCanonicalTopic]:
    ck = (item.get("canonical_key") or "").strip().replace("-", "_")
    if ck and ck != "__draft_unresolved__":
        try:
            return PolicyAssistantCanonicalTopic(ck)
        except ValueError:
            pass
    sk = (item.get("service_key") or "").strip().lower()
    alias: Dict[str, PolicyAssistantCanonicalTopic] = {
        "shipment": PolicyAssistantCanonicalTopic.SHIPMENT,
        "household_goods": PolicyAssistantCanonicalTopic.SHIPMENT,
        "movers": PolicyAssistantCanonicalTopic.SHIPMENT,
        "temporary_housing": PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
        "housing": PolicyAssistantCanonicalTopic.HOST_HOUSING,
        "schooling": PolicyAssistantCanonicalTopic.SCHOOL_SEARCH,
        "schools": PolicyAssistantCanonicalTopic.SCHOOL_SEARCH,
        "immigration": PolicyAssistantCanonicalTopic.VISA_SUPPORT,
        "tax": PolicyAssistantCanonicalTopic.TAX_BRIEFING,
        "home_leave": PolicyAssistantCanonicalTopic.HOME_LEAVE,
        "spouse_support": PolicyAssistantCanonicalTopic.SPOUSE_SUPPORT,
        "relocation_allowance": PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE,
        "settling_in_allowance": PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE,
    }
    return alias.get(sk)


def _topic_row_from_grouped_item(item: Dict[str, Any], *, draft: bool) -> Optional[Tuple[str, PolicyAssistantResolvedTopic]]:
    topic = _topic_from_grouped_item(item)
    if topic is None:
        return None
    bd = item.get("business_display") or {}
    summary = (bd.get("summary") or item.get("title") or item.get("business_display_title") or "")[:800]
    excerpt = summary.strip() or None
    row = PolicyAssistantResolvedTopic(
        included=True,
        explicitly_excluded=False,
        has_numeric_cap=False,
        comparison_readiness="informational_only",
        source_label="Grouped review (HR)",
        policy_source_type="draft_grouped_item" if draft else "published_benefit_rule",
        excerpt=excerpt,
        benefit_reference=str(item.get("canonical_key") or item.get("id") or ""),
    )
    return topic.value, row


def _format_hr_override_summary(overrides: List[Dict[str, Any]]) -> Optional[str]:
    if not overrides:
        return None
    chunks: List[str] = []
    for o in overrides[:10]:
        rid = o.get("benefit_rule_id") or o.get("policy_benefit_rule_id") or o.get("id") or "?"
        note = (o.get("notes") or o.get("reason") or o.get("summary") or "")[:160]
        chunks.append(f"Override on benefit rule **{rid}**" + (f": {note}" if note else "."))
    return " ".join(chunks)


def build_hr_resolved_policy_context_from_review_payload(
    payload: Dict[str, Any],
    *,
    published_benefit_rules: Optional[List[Dict[str, Any]]] = None,
    has_published_version: bool = False,
    policy_title_line: Optional[str] = None,
) -> ResolvedPolicyContext:
    """
    Build ``ResolvedPolicyContext`` from ``build_hr_policy_review_payload`` output plus optional published rules.

    When the working policy version differs from the published version (or nothing is published yet),
    working Layer-2 rows are treated as **draft** for the assistant.
    """
    review = payload.get("review") or {}
    working_vid = (review.get("policy_version_id") or "").strip()
    published_vid = (review.get("published_version_id") or "").strip()
    published_rules = list(published_benefit_rules or [])
    ev = payload.get("employee_visibility") or {}
    readiness = payload.get("readiness") or {}
    cr = readiness.get("comparison_readiness") or {}
    topicless: Optional[str] = None
    if isinstance(cr, dict) and not cr.get("comparison_ready"):
        topicless = "external_reference_partial" if cr.get("partial_numeric_coverage") else "review_required"

    draft_has_changes = bool(working_vid) and (
        not has_published_version or (bool(published_vid) and working_vid != published_vid)
    )

    synthetics = [
        _synthetic_benefit_from_layer2_rule(dict(r))
        for r in (payload.get("layer2_publishable") or {}).get("benefit_rules") or []
    ]
    pst_working = "draft_benefit_rule" if draft_has_changes else "published_benefit_rule"
    label_working = "Working policy version (HR)" if draft_has_changes else "Published policy version"
    topics: Dict[str, PolicyAssistantResolvedTopic] = {}
    for topic, keys in TOPIC_BENEFIT_KEYS.items():
        b = _best_benefit_for_keys(synthetics, keys)
        if b is not None:
            topics[topic.value] = resolved_topic_from_benefit_row(
                b,
                policy_source_type=pst_working,
                source_label=label_working,
            )

    if not topics:
        grouped = payload.get("grouped_policy_items") or []
        for item in grouped:
            if not isinstance(item, dict):
                continue
            pair = _topic_row_from_grouped_item(item, draft=bool(draft_has_changes))
            if pair is None:
                continue
            k, row = pair
            if k not in topics:
                topics[k] = row

    hr_pub: Dict[str, PolicyAssistantResolvedTopic] = {}
    pub_synth = [_synthetic_benefit_from_layer2_rule(dict(r)) for r in published_rules]
    for topic, keys in TOPIC_BENEFIT_KEYS.items():
        b = _best_benefit_for_keys(pub_synth, keys)
        if b is not None:
            hr_pub[topic.value] = resolved_topic_from_benefit_row(
                b,
                policy_source_type="published_benefit_rule",
                source_label="Published version (employees)",
            )

    ovs = payload.get("hr_overrides") or []
    hr_override_summary = _format_hr_override_summary(list(ovs) if isinstance(ovs, list) else [])

    employee_visible = policy_title_line
    if not employee_visible and has_published_version:
        employee_visible = "Published policy is active for employees in ReloPass."
    elif not employee_visible:
        employee_visible = "No published version yet; employees have no published matrix from this policy."

    return ResolvedPolicyContext(
        has_published_benefits=bool(has_published_version or ev.get("employee_sees_published_policy_matrix")),
        draft_exists=bool(working_vid),
        draft_has_unpublished_changes=bool(draft_has_changes),
        employee_visible_summary=employee_visible,
        topicless_comparison_readiness=topicless,
        topics=topics,
        hr_employee_visibility=dict(ev) if isinstance(ev, dict) else None,
        hr_published_topics=hr_pub,
        hr_override_summary=hr_override_summary,
    )


def build_hr_resolved_policy_context(
    db: Any,
    policy_id: str,
    document_id: Optional[str],
    request_id: Optional[str] = None,
) -> ResolvedPolicyContext:
    from .policy_hr_review_service import build_hr_policy_review_payload

    pid = (policy_id or "").strip()
    did = str(document_id).strip() if document_id else None
    payload = build_hr_policy_review_payload(
        db,
        document_id=did,
        policy_id=pid,
        request_id=request_id,
    )
    published = db.get_published_policy_version(pid) if pid else None
    pub_rules: List[Dict[str, Any]] = []
    if published and published.get("id"):
        pub_rules = list(db.list_policy_benefit_rules(str(published["id"])) or [])
    policy = db.get_company_policy(pid) or {}
    title = (policy.get("title") or policy.get("name") or "")[:200]
    ver_num = (published or {}).get("version_number")
    policy_line = f"{title} (published v{ver_num})" if title and ver_num else (title or None)

    review = payload.setdefault("review", {})
    if published and published.get("id"):
        review["published_version_id"] = str(published["id"])

    return build_hr_resolved_policy_context_from_review_payload(
        payload,
        published_benefit_rules=pub_rules,
        has_published_version=bool(published),
        policy_title_line=policy_line,
    )


def execute_hr_policy_assistant_query(
    message: str,
    user: Dict[str, Any],
    policy_id: str,
    document_id: Optional[str] = None,
    request_id: Optional[str] = None,
    *,
    resolve_context: Optional[Callable[..., ResolvedPolicyContext]] = None,
    session: Optional[Dict[str, Any]] = None,
) -> Tuple[PolicyAssistantAnswer, Optional[str], Dict[str, Any]]:
    """
    Classify (HR role + guardrails), resolve policy context, return structured answer.

    ``resolve_context`` defaults to ``build_hr_resolved_policy_context(db, ...)``; inject for tests.
    """
    from backend.database import db as app_db

    if resolve_context is not None:
        ctx = resolve_context(None, policy_id, document_id, request_id)
    else:
        ctx = build_hr_resolved_policy_context(
            app_db, policy_id, document_id, request_id=request_id
        )
    pid = (policy_id or "").strip()
    sess = parse_policy_assistant_session(
        session,
        scope_kind="hr_policy",
        scope_id=pid,
    )
    classification = classify_with_bounded_session(
        message,
        PolicyAssistantRoleScope.HR,
        sess,
        available_topics=None,
    )
    answer = generate_policy_assistant_answer(classification, ctx, PolicyAssistantRoleScope.HR)
    record_policy_assistant_turn(
        message=message,
        role=PolicyAssistantRoleScope.HR,
        classification=classification,
        answer=answer,
        ctx=ctx,
        request_id=request_id,
        employee_resolution=None,
    )
    try:
        from .policy_assistant_answer_audit_service import record_hr_policy_assistant_answer_audit

        pol = app_db.get_company_policy(pid) if pid else None
        cid = (pol or {}).get("company_id")
        if cid:
            record_hr_policy_assistant_answer_audit(
                app_db,
                company_id=str(cid),
                user_id=str(user.get("id") or ""),
                policy_id=pid,
                document_id=document_id,
                message=message,
                answer=answer,
                request_id=request_id,
            )
    except Exception:
        pass
    next_sess = update_session_after_turn(sess, classification, answer)
    return answer, request_id, next_sess.to_json_dict()


def hr_policy_assistant_query_response_dict(
    message: str,
    user: Dict[str, Any],
    policy_id: str,
    document_id: Optional[str] = None,
    request_id: Optional[str] = None,
    *,
    resolve_context: Optional[Callable[..., ResolvedPolicyContext]] = None,
    session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    answer, rid, sess_out = execute_hr_policy_assistant_query(
        message,
        user,
        policy_id,
        document_id=document_id,
        request_id=request_id,
        resolve_context=resolve_context,
        session=session,
    )
    return {
        "ok": True,
        "policy_id": policy_id,
        "document_id": document_id,
        "request_id": rid,
        "answer": answer.model_dump(mode="json"),
        "session": sess_out,
    }
