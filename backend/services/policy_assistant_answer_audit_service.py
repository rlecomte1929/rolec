"""
Persist full policy assistant answer audits (document/snapshot traceability when available).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..database import Database
from .policy_assistant_contract import (
    PolicyAssistantAnswer,
    PolicyAssistantAnswerType,
    PolicyAssistantComparisonReadiness,
)


def _evidence_status_from_hr_answer(answer: PolicyAssistantAnswer) -> str:
    if answer.answer_type == PolicyAssistantAnswerType.REFUSAL:
        return "out_of_scope"
    if answer.answer_type == PolicyAssistantAnswerType.CLARIFICATION_NEEDED:
        return "insufficient_case_data"
    if answer.comparison_readiness in (
        PolicyAssistantComparisonReadiness.REVIEW_REQUIRED,
        PolicyAssistantComparisonReadiness.EXTERNAL_REFERENCE_PARTIAL,
    ):
        return "ambiguous"
    if answer.comparison_readiness == PolicyAssistantComparisonReadiness.INFORMATIONAL_ONLY:
        return "chunk_supported_only"
    return "direct_fact_match"


def record_hr_policy_assistant_answer_audit(
    db: Database,
    *,
    company_id: str,
    user_id: str,
    policy_id: str,
    document_id: Optional[str],
    message: str,
    answer: PolicyAssistantAnswer,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[str]:
    if not db.policy_hardening_tables_available():
        return None
    snapshot_id: Optional[str] = None
    if document_id:
        doc = db.get_policy_document(document_id)
        if doc:
            cid = str(doc.get("company_id") or "")
            snap = db.get_active_policy_knowledge_snapshot_for_company(cid)
            if snap:
                snapshot_id = str(snap.get("id"))
    ev = _evidence_status_from_hr_answer(answer)
    fact_ids: List[str] = []
    chunk_ids: List[str] = []
    for e in answer.evidence or []:
        d = e.model_dump() if hasattr(e, "model_dump") else {}
        kind = str(d.get("kind") or "").lower()
        ref = d.get("reference")
        if not ref:
            continue
        rs = str(ref)
        if "fact" in kind or "policy_fact" in kind:
            fact_ids.append(rs[:200])
        elif "chunk" in kind:
            chunk_ids.append(rs[:200])
        else:
            chunk_ids.append(rs[:200])

    amb_flags: List[str] = []
    if answer.comparison_readiness == PolicyAssistantComparisonReadiness.REVIEW_REQUIRED:
        amb_flags.append("review_required_readiness")

    return db.insert_policy_assistant_answer_audit(
        company_id=company_id,
        asked_by_user_id=user_id,
        question_text=message[:8000],
        answer_text=(answer.answer_text or "")[:8000],
        evidence_status=ev,
        policy_document_id=document_id,
        snapshot_id=snapshot_id,
        question_session_id=session_id,
        normalized_question_topic=answer.canonical_topic.value if answer.canonical_topic else None,
        fact_ids=fact_ids,
        chunk_ids=chunk_ids,
        applicability_decision_json={
            "policy_id": policy_id,
            "request_id": request_id,
            "answer_type": answer.answer_type.value if answer.answer_type else None,
            "comparison_readiness": answer.comparison_readiness.value if answer.comparison_readiness else None,
        },
        ambiguity_flags_json=amb_flags,
    )
