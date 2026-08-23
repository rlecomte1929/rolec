"""[AIQ-1821] The content review queue — requirement facts, with their evidence.

Backs /admin/content-review. Reads the LEGACY `requirement_facts` table, which is the one with
686 pending rows across 12 destinations and a live consumer (approve → list_approved_requirement_facts
→ compute_requirements_sufficiency → GET /api/requirements/sufficiency → the employee dossier
panel). The hyphenated `/api/admin/requirement-facts` router is a different, superseded table.

The design rule this router exists to serve: **every row carries its evidence**. A reviewer who
cannot see the quote inside its source context is rubber-stamping, so the list endpoint returns
the surrounding text, not just a boolean.

Mutations reuse `db.update_requirement_fact_status` and `db.edit_requirement_fact`, which write
the append-only `requirement_reviews` history; this router adds the `audit_logs` row on top.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ...database import db
from ...db.policies import UnattestedLawyerReviewError, UnquotedApprovalError
from ..services import lawyer_review_gate
from ..auth_deps import require_admin
from ..services.fact_evidence import (
    NO_SOURCE,
    UNVERIFIED,
    VERIFIED,
    best_source_text,
    check_evidence,
)

from ..services.audit_log_service import ACTION_UPDATE, ACTOR_HUMAN, insert_audit_log

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/content-review", tags=["content-review"])

_MAX_PAGE = 200


def _audit(entity_id: str, new_value: Dict[str, Any], actor_id: Optional[str]) -> None:
    """One audit_logs row per decision. Never raises — an audit failure must not lose a verdict."""
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="requirement_facts",
                entity_id=entity_id,
                action_type=ACTION_UPDATE,
                old_value=None,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        log.exception("audit_log write failed for requirement_fact %s", entity_id)


def _reviewer_id(user: Dict[str, Any]) -> str:
    """The reviewer's id as TEXT.

    Deliberately NOT auth_uuid: requirement_reviews.reviewer_user_id is text (migration
    20261033000000) precisely so a legacy id like "seed-hr-testingapril" cannot fail a uuid cast
    and silently roll back the approval it shares a transaction with — bug #1543's shape.
    """
    return str(user.get("id") or user.get("email") or "admin")


class DecideRequest(BaseModel):
    fact_ids: List[str] = Field(..., min_length=1)
    action: Literal["approve", "reject"]
    notes: Optional[str] = None


class EditRequest(BaseModel):
    fact_text: str = Field(..., min_length=3)
    notes: Optional[str] = None
    approve: bool = True


@router.get("/facts")
def list_facts(
    status: str = Query("pending"),
    destination: Optional[str] = Query(None, description="ISO-2 destination country"),
    evidence: Optional[Literal["verified", "unverified", "unchecked"]] = Query(None),
    q: Optional[str] = Query(None, description="Substring match on fact text"),
    limit: int = Query(50, ge=1, le=_MAX_PAGE),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """One page of the queue, each row carrying its evidence context."""
    where = ["f.status = :status"]
    params: Dict[str, Any] = {"status": status}
    if destination:
        where.append("e.destination_country = :dest")
        params["dest"] = destination.upper()
    if evidence == "verified":
        where.append("f.evidence_verified = TRUE")
    elif evidence == "unverified":
        where.append("f.evidence_verified = FALSE")
    elif evidence == "unchecked":
        where.append("f.evidence_verified IS NULL")
    if q:
        where.append("LOWER(f.fact_text) LIKE :q")
        params["q"] = f"%{q.lower()}%"
    clause = " AND ".join(where)

    with db.engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM requirement_facts f "
                 f"JOIN requirement_entities e ON e.id = f.entity_id WHERE {clause}"),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(f"""
                SELECT f.id, f.fact_text, f.fact_type, f.evidence_quote, f.source_url,
                       f.confidence, f.status, f.evidence_verified, f.evidence_offset,
                       f.reviewed_by, f.reviewed_at, f.created_at,
                       e.destination_country, e.topic_key, e.domain_area,
                       kd.content_excerpt, kd.last_verified_at,
                       -- Both source-text columns: neither is reliably the fuller
                       -- one. The enterprise.gov.ie permit pages hold 17k chars in
                       -- text_content and 308 chars of cookie banner in the excerpt,
                       -- while across the corpus the excerpt is usually the better.
                       -- best_source_text() takes the longer of the two.
                       kd.text_content,
                       -- [AIQ-2046] applies_to is where `needs_lawyer_review` lives. Without
                       -- it the reviewer saw strictly LESS provenance than the employee who
                       -- then read the row, and could not honour a flag they were never shown.
                       f.applies_to
                  FROM requirement_facts f
                  JOIN requirement_entities e ON e.id = f.entity_id
             LEFT JOIN knowledge_docs kd ON kd.id = f.source_doc_id
                 WHERE {clause}
              ORDER BY e.destination_country, e.topic_key, f.fact_text
                 LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset},
        ).fetchall()

    items = []
    for r in rows:
        check = check_evidence(r[3], best_source_text(r[15], r[17]))
        items.append({
            "id": str(r[0]),
            "fact_text": r[1],
            "fact_type": r[2],
            "evidence_quote": r[3],
            "source_url": r[4],
            "confidence": r[5],
            "status": r[6],
            # Recomputed rather than trusted from the column: the stored flag can lag an edit or
            # a re-archived source, and a stale "verified" badge is worse than none.
            "evidence_status": check.status,
            "evidence_context": check.context,
            "reviewed_by": r[9],
            "reviewed_at": str(r[10]) if r[10] else None,
            "created_at": str(r[11]) if r[11] else None,
            "destination_country": r[12],
            "topic_key": r[13],
            "domain_area": r[14],
            "source_last_verified": str(r[16]) if r[16] else None,
            # [AIQ-2046] Surfaced so the reviewer can SEE the flag they are meant to
            # honour. The gate that refuses the approval lives in db/policies.py; this
            # is what stops the refusal being a surprise.
            "needs_lawyer_review": lawyer_review_gate.carries_lawyer_review_flag(r[18]),
        })

    return {"items": items, "total": int(total), "limit": limit, "offset": offset}


@router.get("/summary")
def summary(user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """Counts for the queue header and the sidebar badge."""
    with db.engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT e.destination_country, f.status, count(*)
              FROM requirement_facts f
              JOIN requirement_entities e ON e.id = f.entity_id
          GROUP BY e.destination_country, f.status
        """)).fetchall()
        ev = conn.execute(text("""
            SELECT CASE WHEN f.evidence_verified IS NULL THEN 'unchecked'
                        WHEN f.evidence_verified THEN 'verified' ELSE 'unverified' END AS bucket,
                   count(*)
              FROM requirement_facts f
             WHERE f.status = 'pending'
          GROUP BY 1
        """)).fetchall()

    by_dest: Dict[str, Dict[str, int]] = {}
    totals: Dict[str, int] = {}
    for dest, st, n in rows:
        by_dest.setdefault(dest, {})[st] = int(n)
        totals[st] = totals.get(st, 0) + int(n)
    return {
        "by_destination": by_dest,
        "totals": totals,
        "pending_evidence": {b: int(n) for b, n in ev},
        "pending": totals.get("pending", 0),
    }


@router.post("/decide")
def decide(body: DecideRequest, user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """Approve or reject a batch. Bulk is the point — most of a queue is decidable in groups."""
    reviewer = _reviewer_id(user)
    new_status = "approved" if body.action == "approve" else "rejected"
    if body.action == "reject" and not (body.notes or "").strip():
        # Mirrors the vetting queue, which requires a reason to reject server-side. A rejection
        # with no reason is unreviewable later and teaches the extractor nothing.
        raise HTTPException(status_code=400, detail="notes are required when rejecting")

    try:
        db.update_requirement_fact_status(body.fact_ids, new_status, reviewer, body.notes)
    except (UnquotedApprovalError, UnattestedLawyerReviewError) as exc:
        # [AIQ-2124/2046] A reviewer approving a batch needs to know WHICH fact failed and
        # why — a 500 would tell them only that something broke, and the batch would look
        # applied. Both gates name their offending ids in the message.
        raise HTTPException(status_code=422, detail=str(exc))
    for fid in body.fact_ids:
        _audit(fid, {"status": new_status, "notes": body.notes}, reviewer)
    return {"ok": True, "count": len(body.fact_ids), "status": new_status}


@router.patch("/facts/{fact_id}")
def edit_fact(
    fact_id: str, body: EditRequest, user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Correct a fact's wording — the verdict approve/reject cannot express."""
    reviewer = _reviewer_id(user)
    try:
        result = db.edit_requirement_fact(
            fact_id, body.fact_text, reviewer, body.notes, approve=body.approve
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    _audit(fact_id, {"action": "edit", "fact_text": body.fact_text}, reviewer)
    return {"ok": True, **result}
