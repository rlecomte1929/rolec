"""Admin material-change review queue API (P2-02d / AIQ-692).

Admin-only endpoints for the human-in-the-loop gate before users are notified of
a source rule change:

  GET  /api/admin/source-change-reviews                 — list pending reviews
  POST /api/admin/source-change-reviews/{id}/approve    — notify affected cases
  POST /api/admin/source-change-reviews/{id}/reject     — log, notify no one

Thin wiring over source_change_review_service; the service holds the logic and is
unit-tested independently. Registered in BOTH backend/main.py and
backend/app/main.py per the CLAUDE.md dual-mount rule (Render serves
backend.main:app).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth_deps import require_admin
from ..db import engine
from ..services.source_change_review_service import (
    approve_review,
    list_pending_reviews,
    reject_review,
)

router = APIRouter(
    prefix="/api/admin/source-change-reviews", tags=["admin-source-change-review"]
)


class RejectBody(BaseModel):
    note: Optional[str] = None


def _reviewer_id(user: Dict[str, Any]) -> str:
    return str(user.get("id") or user.get("email") or "admin")


@router.get("")
def get_pending_reviews(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    with engine.connect() as conn:
        items = list_pending_reviews(conn, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@router.post("/{review_id}/approve")
def post_approve(
    review_id: str,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            return approve_review(conn, review_id, reviewed_by=_reviewer_id(user))
    except ValueError as exc:
        # Not found / not pending → 409 (the review moved out from under the admin).
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{review_id}/reject")
def post_reject(
    review_id: str,
    body: Optional[RejectBody] = None,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    note = body.note if body else None
    try:
        with engine.begin() as conn:
            return reject_review(conn, review_id, reviewed_by=_reviewer_id(user), note=note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
