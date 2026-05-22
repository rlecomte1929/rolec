"""
[P5-5] Policy assistant feedback API + HR review queue.

The feedback loop is the data flywheel engine. **Hard contract**: feedback
records are SIGNALS — they never write to policy_chunks or policy_values.
Negative ratings create / update HR review queue items; HR is the only
path that turns a queue item into a policy edit.

Endpoints
─────────
POST /api/policy/feedback         — record a thumbs up/down (any auth user)
GET  /api/policy/review-queue     — list HR review items (HR/admin only)
PATCH /api/policy/review-queue/{id} — HR triages an item
                                   (status=in_review/resolved/dismissed)

Dedup logic
───────────
For negative feedback only, we group by (company_id, question_hash,
sorted(chunk_ids)) and upsert into `policy_review_queue`:
  - first occurrence → INSERT with feedback_count=1, priority='normal'
  - subsequent       → UPDATE feedback_count++, last_seen_at=now()
  - feedback_count crossing 3 → priority='high'

Positive ratings only insert into `policy_feedback` (the raw signal table)
— they never touch the review queue.

Privacy
───────
The endpoint NEVER receives the raw question text. The client passes a
SHA-256 `question_hash` (lowercased + whitespace-stripped) so we keep
zero plaintext queries server-side. We do accept an optional
`response_summary` (a short HR-visible snippet) and an optional `comment`
from the employee, but those are HR-visible only via the review queue,
not exposed back to anyone else.

Standalone router — same pattern as P2-4 / P1-6 / P1-4 / P1-5.

Tests live in `backend/tests/test_policy_feedback.py`.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db


router = APIRouter(prefix="/api/policy", tags=["policy-feedback"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect helper
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def _is_postgres() -> bool:
    try:
        return db.engine.dialect.name == "postgresql"
    except Exception:
        return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _require_company(user: Dict[str, Any]) -> Dict[str, Any]:
    """Any authenticated user can POST feedback for their own company."""
    cid = user.get("company_id")
    if not cid:
        raise HTTPException(status_code=403, detail="No company_id on profile")
    return {
        "id": user.get("id") or user.get("sub"),
        "company_id": str(cid),
        "role": (user.get("role") or "").lower(),
    }


def _require_hr_or_admin(user: Dict[str, Any]) -> Dict[str, Any]:
    actor = _require_company(user)
    if actor["role"] not in ("hr", "admin"):
        raise HTTPException(status_code=403, detail="HR or admin role required")
    return actor


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------

class FeedbackPayload(BaseModel):
    """Body of POST /api/policy/feedback.

    `question_hash` is computed client-side (SHA-256 of lowercased,
    whitespace-stripped question). We never accept the raw question text.
    """
    session_id: str = Field(..., min_length=1, max_length=128)
    question_hash: str = Field(..., min_length=8, max_length=128)
    chunk_ids: List[str] = Field(default_factory=list)
    rating: Literal["positive", "negative"]
    comment: Optional[str] = Field(None, max_length=2000)
    # Short HR-visible snippet (NOT the full answer). Only stored on the
    # review_queue row, never echoed back.
    response_summary: Optional[str] = Field(None, max_length=600)


class FeedbackResponse(BaseModel):
    feedback_id: str
    review_queue_id: Optional[str] = None
    feedback_count: Optional[int] = None
    priority: Optional[str] = None


class ReviewQueueItem(BaseModel):
    id: str
    company_id: str
    question_hash: str
    chunk_ids: List[str]
    response_summary: Optional[str] = None
    latest_comment: Optional[str] = None
    feedback_count: int
    priority: str
    status: str
    first_seen_at: str
    last_seen_at: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_note: Optional[str] = None


class ReviewQueuePatch(BaseModel):
    status: Optional[Literal["pending", "in_review", "resolved", "dismissed"]] = None
    resolution_note: Optional[str] = Field(None, max_length=2000)


# ---------------------------------------------------------------------------
# Internal helpers — dedup key, list serialization
# ---------------------------------------------------------------------------

def _sorted_chunk_ids(chunk_ids: List[str]) -> List[str]:
    """Stable order so the dedup key is deterministic regardless of
    citation order."""
    return sorted(set(str(c) for c in chunk_ids if c))


def _chunk_ids_key(sorted_ids: List[str]) -> str:
    """Match the Postgres generated column `array_to_string(chunk_ids, ',')`."""
    return ",".join(sorted_ids)


def _serialize_chunk_ids_for_db(sorted_ids: List[str]) -> Any:
    """Postgres: pass the list as-is so SQLAlchemy emits a UUID[] literal.
    SQLite (tests): we stuff the comma-joined string into a TEXT column
    so SELECT works the same."""
    return sorted_ids if _is_postgres() else _chunk_ids_key(sorted_ids)


def _parse_chunk_ids_from_db(value: Any) -> List[str]:
    """Inverse of _serialize_chunk_ids_for_db, dialect-aware."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        return [c for c in value.split(",") if c]
    return []


# ---------------------------------------------------------------------------
# Internal — review_queue upsert
# ---------------------------------------------------------------------------

def _upsert_review_queue(
    conn: Any,
    *,
    company_id: str,
    question_hash: str,
    chunk_ids_sorted: List[str],
    response_summary: Optional[str],
    comment: Optional[str],
) -> Dict[str, Any]:
    """Return dict with id, feedback_count, priority after upsert.

    Looks for an existing row by (company_id, question_hash, chunk_ids_key)
    and either INSERTs a new one (feedback_count=1, priority='normal') or
    UPDATEs the existing one (feedback_count++, recompute priority,
    refresh last_seen_at + latest_comment).
    """
    key = _chunk_ids_key(chunk_ids_sorted)
    existing = conn.execute(
        text(
            f"SELECT id, feedback_count, priority "
            f"FROM {_t('policy_review_queue')} "
            f"WHERE company_id = :cid "
            f"  AND question_hash = :qh "
            f"  AND chunk_ids_key = :key "
            f"LIMIT 1"
        ),
        {"cid": company_id, "qh": question_hash, "key": key},
    ).mappings().first()

    if existing:
        new_count = int(existing["feedback_count"]) + 1
        new_priority = "high" if new_count >= 3 else (existing.get("priority") or "normal")
        conn.execute(
            text(
                f"UPDATE {_t('policy_review_queue')} "
                f"SET feedback_count = :cnt, "
                f"    priority = :pri, "
                f"    last_seen_at = :now, "
                f"    latest_comment = COALESCE(:cmt, latest_comment), "
                f"    response_summary = COALESCE(response_summary, :resp) "
                f"WHERE id = :id"
            ),
            {
                "cnt": new_count,
                "pri": new_priority,
                "now": _now_iso(),
                "cmt": comment,
                "resp": response_summary,
                "id": str(existing["id"]),
            },
        )
        return {
            "id": str(existing["id"]),
            "feedback_count": new_count,
            "priority": new_priority,
        }

    new_id = str(uuid.uuid4())
    conn.execute(
        text(
            f"INSERT INTO {_t('policy_review_queue')} "
            f"  (id, company_id, question_hash, chunk_ids, response_summary, "
            f"   latest_comment, feedback_count, priority, status, "
            f"   first_seen_at, last_seen_at) "
            f"VALUES (:id, :cid, :qh, :chunks, :resp, :cmt, 1, 'normal', "
            f"        'pending', :now, :now)"
        ),
        {
            "id": new_id,
            "cid": company_id,
            "qh": question_hash,
            "chunks": _serialize_chunk_ids_for_db(chunk_ids_sorted),
            "resp": response_summary,
            "cmt": comment,
            "now": _now_iso(),
        },
    )
    return {"id": new_id, "feedback_count": 1, "priority": "normal"}


# ---------------------------------------------------------------------------
# POST /api/policy/feedback
# ---------------------------------------------------------------------------

@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(
    payload: FeedbackPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> FeedbackResponse:
    """Record a thumbs-up/down. Negative → upsert into review_queue."""
    actor = _require_company(user)
    sorted_chunks = _sorted_chunk_ids(payload.chunk_ids)
    feedback_id = str(uuid.uuid4())

    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {_t('policy_feedback')} "
                    f"  (id, company_id, session_id, question_hash, chunk_ids, "
                    f"   rating, comment, created_at) "
                    f"VALUES (:id, :cid, :sid, :qh, :chunks, :rating, :cmt, :now)"
                ),
                {
                    "id": feedback_id,
                    "cid": actor["company_id"],
                    "sid": payload.session_id,
                    "qh": payload.question_hash,
                    "chunks": _serialize_chunk_ids_for_db(sorted_chunks),
                    "rating": payload.rating,
                    "cmt": payload.comment,
                    "now": _now_iso(),
                },
            )

            if payload.rating == "negative":
                queue_row = _upsert_review_queue(
                    conn,
                    company_id=actor["company_id"],
                    question_hash=payload.question_hash,
                    chunk_ids_sorted=sorted_chunks,
                    response_summary=payload.response_summary,
                    comment=payload.comment,
                )
            else:
                queue_row = None
    except Exception:
        logger.exception("policy_feedback: write failed")
        raise HTTPException(status_code=500, detail="Failed to record feedback")

    if queue_row:
        return FeedbackResponse(
            feedback_id=feedback_id,
            review_queue_id=queue_row["id"],
            feedback_count=queue_row["feedback_count"],
            priority=queue_row["priority"],
        )
    return FeedbackResponse(feedback_id=feedback_id)


# ---------------------------------------------------------------------------
# GET /api/policy/review-queue
# ---------------------------------------------------------------------------

@router.get("/review-queue", response_model=List[ReviewQueueItem])
def list_review_queue(
    status: Optional[Literal["pending", "in_review", "resolved", "dismissed"]] = Query(
        "pending", description="Filter by status; pass an empty string to list all"
    ),
    priority: Optional[Literal["normal", "high"]] = Query(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[ReviewQueueItem]:
    """Return review queue items for the caller's company.

    Default ordering puts `priority='high'` first, then most-recently-seen
    descending (matches the HR triage flow — surface what's hottest).
    """
    actor = _require_hr_or_admin(user)
    where_parts = ["company_id = :cid"]
    params: Dict[str, Any] = {"cid": actor["company_id"]}
    if status:
        where_parts.append("status = :status")
        params["status"] = status
    if priority:
        where_parts.append("priority = :priority")
        params["priority"] = priority

    where_sql = " AND ".join(where_parts)

    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, company_id, question_hash, chunk_ids, "
                    f"       response_summary, latest_comment, feedback_count, "
                    f"       priority, status, first_seen_at, last_seen_at, "
                    f"       resolved_by, resolved_at, resolution_note "
                    f"FROM {_t('policy_review_queue')} "
                    f"WHERE {where_sql} "
                    f"ORDER BY CASE WHEN priority = 'high' THEN 0 ELSE 1 END, "
                    f"         last_seen_at DESC"
                ),
                params,
            ).mappings().fetchall()
    except Exception:
        logger.exception("list_review_queue failed")
        raise HTTPException(status_code=500, detail="Failed to load review queue")

    return [
        ReviewQueueItem(
            id=str(r["id"]),
            company_id=str(r["company_id"]),
            question_hash=str(r["question_hash"]),
            chunk_ids=_parse_chunk_ids_from_db(r.get("chunk_ids")),
            response_summary=r.get("response_summary"),
            latest_comment=r.get("latest_comment"),
            feedback_count=int(r["feedback_count"]),
            priority=str(r["priority"]),
            status=str(r["status"]),
            first_seen_at=str(r["first_seen_at"]),
            last_seen_at=str(r["last_seen_at"]),
            resolved_by=str(r["resolved_by"]) if r.get("resolved_by") else None,
            resolved_at=str(r["resolved_at"]) if r.get("resolved_at") else None,
            resolution_note=r.get("resolution_note"),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# PATCH /api/policy/review-queue/{id}
# ---------------------------------------------------------------------------

@router.patch("/review-queue/{queue_id}", response_model=ReviewQueueItem)
def patch_review_queue(
    queue_id: str,
    payload: ReviewQueuePatch,
    user: Dict[str, Any] = Depends(get_current_user),
) -> ReviewQueueItem:
    """HR triages an item — set status (and optionally resolution_note)."""
    actor = _require_hr_or_admin(user)

    try:
        with db.engine.begin() as conn:
            existing = conn.execute(
                text(
                    f"SELECT id, company_id FROM {_t('policy_review_queue')} "
                    f"WHERE id = :id"
                ),
                {"id": queue_id},
            ).mappings().first()
            if not existing:
                raise HTTPException(status_code=404, detail="Queue item not found")
            if str(existing["company_id"]) != actor["company_id"]:
                raise HTTPException(status_code=403, detail="Cross-company access denied")

            sets: List[str] = []
            params: Dict[str, Any] = {"id": queue_id}
            if payload.status is not None:
                sets.append("status = :status")
                params["status"] = payload.status
                if payload.status in ("resolved", "dismissed"):
                    sets.append("resolved_by = :rby")
                    sets.append("resolved_at = :rat")
                    params["rby"] = actor["id"]
                    params["rat"] = _now_iso()
            if payload.resolution_note is not None:
                sets.append("resolution_note = :note")
                params["note"] = payload.resolution_note

            if not sets:
                raise HTTPException(status_code=400, detail="Empty patch payload")

            conn.execute(
                text(
                    f"UPDATE {_t('policy_review_queue')} "
                    f"SET {', '.join(sets)} "
                    f"WHERE id = :id"
                ),
                params,
            )

            row = conn.execute(
                text(
                    f"SELECT id, company_id, question_hash, chunk_ids, "
                    f"       response_summary, latest_comment, feedback_count, "
                    f"       priority, status, first_seen_at, last_seen_at, "
                    f"       resolved_by, resolved_at, resolution_note "
                    f"FROM {_t('policy_review_queue')} WHERE id = :id"
                ),
                {"id": queue_id},
            ).mappings().first()
    except HTTPException:
        raise
    except Exception:
        logger.exception("patch_review_queue failed id=%s", queue_id)
        raise HTTPException(status_code=500, detail="Failed to update queue item")

    return ReviewQueueItem(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        question_hash=str(row["question_hash"]),
        chunk_ids=_parse_chunk_ids_from_db(row.get("chunk_ids")),
        response_summary=row.get("response_summary"),
        latest_comment=row.get("latest_comment"),
        feedback_count=int(row["feedback_count"]),
        priority=str(row["priority"]),
        status=str(row["status"]),
        first_seen_at=str(row["first_seen_at"]),
        last_seen_at=str(row["last_seen_at"]),
        resolved_by=str(row["resolved_by"]) if row.get("resolved_by") else None,
        resolved_at=str(row["resolved_at"]) if row.get("resolved_at") else None,
        resolution_note=row.get("resolution_note"),
    )
