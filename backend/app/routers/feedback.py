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
    # TD-9 (AIQ-1427): campaign slice stamped by the widget during a test-drive session.
    campaign: Optional[str] = None
    corridor_id: Optional[str] = None
    tester_segment: Optional[str] = None


def _resolve_auth_user_id(reporter_id: Any) -> Optional[str]:
    """Resolve the caller's id to a value safe for feedback.user_id (uuid FK → auth.users(id)).

    A Supabase-native session's id IS an auth.users uuid, so bind it. But a legacy/seed
    session can have a uuid-FORMAT id that is NOT a row in auth.users; binding that
    violates feedback_user_id_fkey and 500s the whole submit (surfaced as the widget's
    "Failed to send"). So bind the uuid only when it actually EXISTS in auth.users,
    otherwise NULL — reporter identity is still captured in reporter_email/name/role and
    feedback_status.reporter_id.
    """
    try:
        candidate = str(uuid.UUID(str(reporter_id)))
    except (ValueError, TypeError, AttributeError):
        return None
    # The FK (and the auth schema) only exist on Postgres. On SQLite (tests) there is
    # nothing to violate, so keep the historical behaviour and bind the uuid. If the
    # existence probe fails for any reason, fall back to NULL rather than block feedback.
    if db.engine.dialect.name != "postgresql":
        return candidate
    try:
        with db.engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM auth.users WHERE id = :uid LIMIT 1"),
                {"uid": candidate},
            ).first()
        return candidate if exists else None
    except Exception:
        return None


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
    # Generate the row id ourselves (instead of the DB default) so the feedback_status
    # ticket can be keyed by it — the SAME id the admin console + its triage/dispatch
    # use. This gives one canonical feedback_status key (the feedback uuid) shared by
    # the reporter endpoints (/mine, /{report_id}/status) and the admin console.
    feedback_id = str(uuid.uuid4())
    # auth.uid() is NULL on the service-role connection, so set user_id ourselves.
    # feedback.user_id is a uuid FK → auth.users(id); bind the caller's id only when it
    # is a uuid that EXISTS in auth.users (a legacy/seed session can have a uuid-format
    # id that is not an auth user — binding it violates the FK and 500s the submit).
    # Otherwise NULL; attribution stays on reporter_email/name/role + feedback_status.
    reporter_id = current_user.get("id")  # kept: feedback_status pre-fill binds it as reporter_id
    auth_user_id = _resolve_auth_user_id(reporter_id)
    screenshot = body.screenshot_data
    if screenshot is not None and len(screenshot) > _MAX_SCREENSHOT:
        screenshot = None  # too large to persist; keep the text feedback

    # Snapshot the reporter's identity from the authenticated session so the admin
    # log can show WHO reported this even when user_id is NULL (legacy/HR sessions
    # with no Supabase-native uuid). current_user comes from the users table
    # (id/username/email/role/name) via get_current_user.
    reporter_email = current_user.get("email")
    reporter_name = current_user.get("name") or current_user.get("full_name")
    reporter_role = current_user.get("role")

    cols = [
        "id", "user_id", "page_url", "category", "message", "report_id", "screenshot_data",
        "reporter_email", "reporter_name", "reporter_role",
    ]
    vals = [
        ":fid", ":uid", ":page", ":cat", ":msg", ":rid", ":shot",
        ":r_email", ":r_name", ":r_role",
    ]
    params: Dict[str, Any] = {
        "fid": feedback_id,
        "uid": auth_user_id,
        "page": body.page_url or "",
        "cat": category,
        "msg": message[:_MAX_MESSAGE],
        "rid": report_id,
        "shot": screenshot,
        "r_email": reporter_email,
        "r_name": reporter_name,
        "r_role": reporter_role,
    }
    # TD-9: stamp campaign/corridor/segment only when the widget supplied them (test-drive
    # sessions). Omitting them for normal users keeps the original INSERT + existing tests intact.
    for col, val in (
        ("campaign", body.campaign),
        ("corridor_id", body.corridor_id),
        ("tester_segment", body.tester_segment),
    ):
        if val:
            cols.append(col)
            vals.append(f":{col}")
            params[col] = val

    with db.engine.begin() as conn:
        conn.execute(
            # id / status / created_at use their column defaults.
            text(f"INSERT INTO feedback ({', '.join(cols)}) VALUES ({', '.join(vals)})"),
            params,
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
                    "source_id": feedback_id,
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
                "  ON fs.source_id = CAST(f.id AS TEXT) AND fs.stream = 'product' "
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
        # feedback_status is keyed by the feedback uuid; resolve the reporter's
        # human report_id to that id via the feedback row.
        row = conn.execute(
            text(
                "SELECT fs.status, fs.severity, fs.area, fs.dispatch_status, fs.reporter_id "
                "FROM feedback f "
                "JOIN feedback_status fs "
                "  ON fs.source_id = CAST(f.id AS TEXT) AND fs.stream = 'product' "
                "WHERE f.report_id = :rid"
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
