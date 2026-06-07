"""
AI decision audit log — EU AI Act Art. 14 (human oversight).

Every HR action on an AI-generated recommendation (accept / override / reject)
is recorded here, paired with the original AI output. This is the storage
contract behind the `AIRecommendationCard` frontend component (AI-002).

Endpoints:
  POST  /api/ai/decisions      — HR records a decision on an AI recommendation
  GET   /api/ai/decisions      — HR lists decisions (own-company), with filters

Both routes require HR or Admin. Override and reject must include a non-empty
reason; the DB allows null reason for `accept`.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import require_admin_or_hr
from ...database import db
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTOR_HUMAN,
    insert_audit_log,
)

router = APIRouter(prefix="/api/ai/decisions", tags=["ai_decisions"])
logger = logging.getLogger(__name__)

VALID_DECISIONS = ("accept", "override", "reject")
REASON_REQUIRED_DECISIONS = ("override", "reject")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AIDecisionCreate(BaseModel):
    feature: str = Field(..., min_length=1, max_length=100)
    recommendation_id: str = Field(..., min_length=1, max_length=200)
    ai_output: Dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(..., pattern=r"^(accept|override|reject)$")
    reason: Optional[str] = Field(None, max_length=4000)


class AIDecisionRead(BaseModel):
    id: str
    created_at: str
    updated_at: str
    actor_id: Optional[str]
    company_id: Optional[str]
    feature: str
    recommendation_id: str
    ai_output: Dict[str, Any]
    decision: str
    reason: Optional[str]
    outcome: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _caller_company_id(user: Dict[str, Any]) -> Optional[str]:
    # AIQ-861: legacy text HR ids (e.g. ``seed-hr-testingapril``) aren't
    # UUID-castable, so ``get_profile_record`` returns ``None`` and the ``users``
    # row carries no company — which made this EU AI Act audit surface 403 with
    # "No company linked" for HR who resolve fine everywhere else. Fall back to
    # ``db.get_hr_company_id`` (the hr_users-aware resolver, same path as
    # command-center / exceptions / AIQ-862). Returns the caller's OWN company
    # only, so tenant scoping is preserved.
    uid = user.get("id")
    profile = db.get_profile_record(uid)
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id and uid:
        company_id = db.get_hr_company_id(uid)
    return str(company_id) if company_id else None


def _row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if v is None:
            continue
        if isinstance(v, uuid.UUID):
            d[k] = str(v)
        elif hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return d


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AIDecisionRead,
    status_code=201,
)
def create_ai_decision(
    body: AIDecisionCreate,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Record an HR admin's accept / override / reject on an AI recommendation."""
    if body.decision in REASON_REQUIRED_DECISIONS and not (body.reason and body.reason.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Reason is required for decision '{body.decision}'.",
        )

    actor_id = user["id"]
    company_id = _caller_company_id(user)
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        # AI-002 fix: combine INSERT + readback into one statement via RETURNING *.
        # The previous "INSERT then SELECT * WHERE id = :id" failed because :id
        # was bound as TEXT and Postgres has no implicit text=uuid comparison
        # operator → "operator does not exist: text = uuid" → 500 + rollback.
        # Casting actor_id defensively as well in case user["id"] arrives as text.
        row = conn.execute(
            text(
                """
                INSERT INTO ai_decisions (
                    id, created_at, updated_at, actor_id, company_id,
                    feature, recommendation_id, ai_output, decision, reason
                ) VALUES (
                    CAST(:id AS uuid), :now, :now, CAST(:actor AS uuid), :company,
                    :feature, :rec_id, CAST(:ai_output AS jsonb), :decision, :reason
                )
                RETURNING *
                """
            ),
            {
                "id": new_id,
                "now": now,
                "actor": actor_id,
                "company": company_id,
                "feature": body.feature,
                "rec_id": body.recommendation_id,
                "ai_output": _json_dumps(body.ai_output),
                "decision": body.decision,
                "reason": (body.reason or "").strip() or None,
            },
        ).mappings().first()

        try:
            insert_audit_log(
                conn,
                entity_type="ai_decisions",
                entity_id=new_id,
                action_type=ACTION_INSERT,
                old_value=None,
                new_value={
                    "feature": body.feature,
                    "recommendation_id": body.recommendation_id,
                    "decision": body.decision,
                    "company_id": company_id,
                },
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
        except Exception:
            logger.exception("audit_log write failed ai_decisions id=%s", new_id)

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to read back ai_decisions row")
    return _row_to_dict(row)


@router.get(
    "",
    response_model=List[AIDecisionRead],
)
def list_ai_decisions(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    feature: Optional[str] = Query(None, max_length=100),
    decision: Optional[str] = Query(None, pattern=r"^(accept|override|reject)$"),
    limit: int = Query(100, ge=1, le=500),
) -> List[Dict[str, Any]]:
    """List AI decisions for the caller's company, newest first."""
    company_id = _caller_company_id(user)
    if not company_id and not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — AI decisions are tenant-scoped.",
        )

    where_clauses: List[str] = []
    params: Dict[str, Any] = {"limit": limit}

    # Admins without a company see everything; HR is scoped to their company.
    if not user.get("is_admin") or company_id:
        where_clauses.append("company_id = :company")
        params["company"] = company_id

    if feature:
        where_clauses.append("feature = :feature")
        params["feature"] = feature
    if decision:
        where_clauses.append("decision = :decision")
        params["decision"] = decision

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = f"""
        SELECT * FROM ai_decisions
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :limit
    """
    with db.engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# JSON serialisation helper — kept local to avoid pulling json at module top
# ---------------------------------------------------------------------------


def _json_dumps(value: Any) -> str:
    import json
    return json.dumps(value or {}, default=str, ensure_ascii=False)
