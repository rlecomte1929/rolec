"""
feedback.py — product "Share feedback" widget submissions + reporter status.

The frontend FeedbackWidget used to write directly to the Supabase `feedback`
table via PostgREST, which requires a live Supabase Auth session. ReloPass
employees authenticate with a ReloPass session token and usually have no Supabase
session, so those inserts ran as `anon` (no INSERT grant) and silently failed
("Failed to send"). This endpoint accepts the submission with the ReloPass session
and writes via the service-role DB connection (bypassing RLS), setting user_id
explicitly (auth.uid() is NULL on the service-role connection). The Admin Feedback
tab reads the same `public.feedback` table, so submissions now reach triage.

D-BugRoutine Slice-1 additions:
  - submit_feedback now BEST-EFFORT upserts a feedback_status ticket keyed on
    (stream='product', source_id=report_id) with severity/area from the triage
    classifier and reporter_id set to the submitting user.
  - GET /api/feedback/{report_id}/status lets the reporter check their ticket.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_current_user
from ..services.feedback_triage import classify_best
from ...database import db

log = logging.getLogger(__name__)

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
    # feedback.user_id is a uuid column: bind ONLY a resolved Supabase uuid (or
    # NULL) — never the legacy text id, which fails the uuid cast and 500s.
    # _resolve_auth_uuid already returns a real uuid or None (safe degrade); the
    # legacy text id stays on the text feedback_status.reporter_id for attribution.
    auth_uuid = current_user.get("auth_uuid")
    reporter_id = current_user.get("id")
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
                "uid": str(auth_uuid) if auth_uuid else None,
                "page": body.page_url or "",
                "cat": category,
                "msg": message[:_MAX_MESSAGE],
                "rid": report_id,
                "shot": screenshot,
            },
        )

    # ── Best-effort: seed a feedback_status ticket for this submission ────────
    # Wrapped in try/except so that any failure (table absent, constraint, etc.)
    # never propagates to the caller.  This is a secondary concern.
    try:
        labels = classify_best(message, category)
        now = datetime.utcnow().isoformat()
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO feedback_status "
                    "(stream, source_id, status, severity, area, reporter_id, updated_at) "
                    "VALUES ('product', :source_id, 'new', :severity, :area, :reporter_id, :updated_at) "
                    "ON CONFLICT (stream, source_id) DO NOTHING"
                ),
                {
                    "source_id": report_id,
                    "severity": labels["severity"],
                    "area": labels["area"],
                    "reporter_id": str(reporter_id) if reporter_id else None,
                    "updated_at": now,
                },
            )
    except Exception:  # noqa: BLE001
        log.warning(
            "feedback_status pre-fill failed (best-effort, suppressed) report_id=%s",
            report_id,
        )

    return {"ok": True, "report_id": report_id}


@router.get("/mine")
def list_my_feedback(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the calling user's own feedback submissions with ticket status.

    Reporter-scoped: only rows whose ``feedback.user_id`` matches the caller
    are returned.  Uses a LEFT JOIN on ``feedback_status`` so reports without
    a triage ticket still appear (status/severity/area/dispatch_status = null).

    Returns at most 50 items ordered newest-first.
    """
    caller_id = str(
        current_user.get("auth_uuid") or current_user.get("id") or ""
    )

    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT f.report_id, f.category, f.message, "
                "fs.status, fs.severity, fs.area, fs.dispatch_status, f.created_at "
                "FROM feedback f "
                "LEFT JOIN feedback_status fs "
                "  ON fs.source_id = f.report_id AND fs.stream = 'product' "
                "WHERE f.user_id = :caller "
                "ORDER BY f.created_at DESC "
                "LIMIT 50"
            ),
            {"caller": caller_id},
        ).fetchall()

    return {
        "reports": [
            {
                "report_id": row[0],
                "category": row[1],
                "message_excerpt": (row[2] or "")[:120],
                "status": row[3],
                "severity": row[4],
                "area": row[5],
                "dispatch_status": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]
    }


@router.get("/{report_id}/status")
def get_feedback_status(
    report_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return triage status for the reporter's own submission.

    Scoped: only returns the ticket when the caller's user id matches
    the ``reporter_id`` recorded at submit time.  Returns 404 otherwise
    (whether the ticket doesn't exist or belongs to someone else) to
    avoid information leakage.
    """
    caller_id = str(
        current_user.get("auth_uuid") or current_user.get("id") or ""
    )

    with db.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT status, severity, area, dispatch_status, reporter_id "
                "FROM feedback_status "
                "WHERE stream = 'product' AND source_id = :rid"
            ),
            {"rid": report_id},
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Not found")

    # Scope check: reporter_id must match the caller (treat None as mismatch).
    if row[4] != caller_id:
        raise HTTPException(status_code=404, detail="Not found")

    return {
        "report_id": report_id,
        "status": row[0],
        "severity": row[1],
        "area": row[2],
        "dispatch_status": row[3],
    }
