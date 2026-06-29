"""
feedback.py — product "Share feedback" widget submissions.

The frontend FeedbackWidget used to write directly to the Supabase `feedback`
table via PostgREST, which requires a live Supabase Auth session. ReloPass
employees authenticate with a ReloPass session token and usually have no Supabase
session, so those inserts ran as `anon` (no INSERT grant) and silently failed
("Failed to send"). This endpoint accepts the submission with the ReloPass session
and writes via the service-role DB connection (bypassing RLS), setting user_id
explicitly (auth.uid() is NULL on the service-role connection). The Admin Feedback
tab reads the same `public.feedback` table, so submissions now reach triage.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_CATEGORIES = {"bug", "idea", "other"}
_MAX_MESSAGE = 2000
_MAX_SCREENSHOT = 5_000_000  # ~5MB of base64; drop oversized rather than 500


class FeedbackBody(BaseModel):
    category: str
    message: str
    page_url: Optional[str] = None
    report_id: Optional[str] = None
    screenshot_data: Optional[str] = None


@router.post("", status_code=201)
def submit_feedback(
    body: FeedbackBody,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Record a product-feedback submission (bug / idea / other)."""
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    category = body.category if body.category in _CATEGORIES else "other"
    report_id = body.report_id or f"{category[:3].upper()}-{uuid.uuid4().hex[:8]}"
    # auth.uid() is NULL on the service-role connection, so set user_id ourselves.
    user_id = current_user.get("auth_uuid") or current_user.get("id")
    screenshot = body.screenshot_data
    if screenshot is not None and len(screenshot) > _MAX_SCREENSHOT:
        screenshot = None  # too large to persist; keep the text feedback

    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO feedback "
                "(user_id, page_url, category, message, report_id, screenshot_data) "
                "VALUES (:uid, :page, :cat, :msg, :rid, :shot)"
                # id / status / created_at use their column defaults.
            ),
            {
                "uid": str(user_id) if user_id else None,
                "page": body.page_url or "",
                "cat": category,
                "msg": message[:_MAX_MESSAGE],
                "rid": report_id,
                "shot": screenshot,
            },
        )

    return {"ok": True, "report_id": report_id}
