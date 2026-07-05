"""Admin unified feedback console — Task 6.

GET  /api/admin/feedback?stream=&status=&since=  → normalized rows across all streams
PATCH /api/admin/feedback/{stream}/{id}           → upsert feedback_status + audit
POST  /api/admin/feedback/{stream}/{id}/dispatch  → dispatch ticket to routine (BR-2)

ML tables (feedback / ai_human_feedback / policy_answer_helpfulness) are NEVER mutated.
All mutations go to feedback_status only.

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md rule).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..services.admin_audit import record_admin_event

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin-feedback"])


def _get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── SQL helpers ─────────────────────────────────────────────────────────────

# The five stream sub-queries are UNION ALL'd together, then LEFT JOIN'd to
# feedback_status to pick up triage state.  CAST(x AS TEXT) keeps the query
# compatible with both SQLite (tests) and Postgres (prod).


def _union_sql(is_sqlite: bool) -> str:
    """Build the UNION of every feedback stream.

    ``hr_feedback.created_at`` is stored as TEXT in prod while every other
    branch is ``timestamptz``. Postgres rejects a UNION that mixes ``text`` and
    ``timestamptz``, so cast it to ``timestamptz`` on Postgres. On SQLite
    ``CAST(x AS timestamptz)`` is an unknown type → NUMERIC affinity, which would
    corrupt the ISO string, so leave the column as-is there (SQLite is loosely
    typed and only used by tests).
    """
    hr_created_at = "hf.created_at" if is_sqlite else "CAST(hf.created_at AS timestamptz)"
    return f"""
SELECT
    CAST(f.id        AS TEXT) AS id,
    'product'                 AS stream,
    COALESCE(f.report_id, CAST(f.id AS TEXT)) AS source_ref,
    f.message                 AS text,
    f.category                AS verdict,
    CAST(f.user_id   AS TEXT) AS user_id,
    CAST(NULL AS TEXT)        AS company_id,
    f.created_at,
    CASE WHEN f.screenshot_data IS NOT NULL THEN 1 ELSE 0 END AS has_screenshot,
    f.reporter_name           AS reporter_name,
    f.reporter_email          AS reporter_email,
    f.reporter_role           AS reporter_role
FROM feedback f

UNION ALL

SELECT
    CAST(h.id        AS TEXT) AS id,
    'ai_answers'              AS stream,
    h.trace_session_id        AS source_ref,
    h.comment                 AS text,
    h.verdict                 AS verdict,
    h.reviewer_user_id        AS user_id,
    CAST(NULL AS TEXT)        AS company_id,
    h.created_at,
    0                         AS has_screenshot,
    CAST(NULL AS TEXT)        AS reporter_name,
    CAST(NULL AS TEXT)        AS reporter_email,
    CAST(NULL AS TEXT)        AS reporter_role
FROM ai_human_feedback h

UNION ALL

SELECT
    CAST(p.id        AS TEXT) AS id,
    'helpfulness'             AS stream,
    p.trace_session_id        AS source_ref,
    p.comment                 AS text,
    CASE WHEN p.helpful THEN 'thumbs_up' ELSE 'thumbs_down' END AS verdict,
    p.user_id                 AS user_id,
    p.company_id              AS company_id,
    p.created_at,
    0                         AS has_screenshot,
    CAST(NULL AS TEXT)        AS reporter_name,
    CAST(NULL AS TEXT)        AS reporter_email,
    CAST(NULL AS TEXT)        AS reporter_role
FROM policy_answer_helpfulness p

UNION ALL

SELECT
    CAST(hf.id       AS TEXT) AS id,
    'hr_assignment'           AS stream,
    hf.assignment_id          AS source_ref,
    hf.message                AS text,
    CAST(NULL AS TEXT)        AS verdict,
    hf.hr_user_id             AS user_id,
    CAST(NULL AS TEXT)        AS company_id,
    {hr_created_at}           AS created_at,
    0                         AS has_screenshot,
    CAST(NULL AS TEXT)        AS reporter_name,
    CAST(NULL AS TEXT)        AS reporter_email,
    CAST(NULL AS TEXT)        AS reporter_role
FROM hr_feedback hf

UNION ALL

SELECT
    CAST(cf.id       AS TEXT) AS id,
    'hr_case'                 AS stream,
    COALESCE(cf.canonical_case_id, cf.case_id) AS source_ref,
    cf.message                AS text,
    cf.section                AS verdict,
    CAST(cf.author_user_id AS TEXT) AS user_id,
    CAST(NULL AS TEXT)        AS company_id,
    cf.created_at_ts          AS created_at,
    0                         AS has_screenshot,
    CAST(NULL AS TEXT)        AS reporter_name,
    CAST(NULL AS TEXT)        AS reporter_email,
    CAST(NULL AS TEXT)        AS reporter_role
FROM case_feedback cf
"""

_OUTER_SQL = """
SELECT
    base.id, base.stream, base.source_ref, base.text, base.verdict,
    base.user_id, base.company_id, base.created_at, base.has_screenshot,
    -- Reporter identity: product rows carry a snapshot taken at submit time;
    -- every stream also resolves the raw user_id against profiles as a fallback
    -- (CAST(pr.id AS TEXT) bridges uuid-vs-text ids, and works on Postgres + SQLite).
    COALESCE(base.reporter_name,  pr.full_name) AS reporter_name,
    COALESCE(base.reporter_email, pr.email)     AS reporter_email,
    COALESCE(base.reporter_role,  pr.role)      AS reporter_role,
    fs.status, fs.owner, fs.resolution,
    CAST(fs.severity        AS TEXT) AS severity,
    CAST(fs.area            AS TEXT) AS area,
    CAST(fs.dispatch_status AS TEXT) AS dispatch_status,
    CAST(fs.dispatch_ref    AS TEXT) AS dispatch_ref
FROM (
    {union}
) AS base
LEFT JOIN feedback_status fs
       ON fs.stream    = base.stream
      AND fs.source_id = base.id
LEFT JOIN profiles pr
       ON CAST(pr.id AS TEXT) = base.user_id
WHERE 1=1
{filters}
ORDER BY base.created_at DESC
LIMIT 500
"""


def _fetch_rows(
    db: Session,
    *,
    stream: Optional[str],
    status: Optional[str],
    since: Optional[str],
    dispatched: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    filters: List[str] = []
    params: Dict[str, Any] = {}
    if stream:
        filters.append("AND base.stream = :stream")
        params["stream"] = stream
    if status:
        filters.append("AND fs.status = :status")
        params["status"] = status
    if since:
        filters.append("AND base.created_at >= :since")
        params["since"] = since
    if dispatched:
        filters.append("AND fs.dispatch_status IS NOT NULL")

    is_sqlite = db.get_bind().dialect.name == "sqlite"
    sql = _OUTER_SQL.format(union=_union_sql(is_sqlite), filters="\n".join(filters))
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/feedback")
def list_feedback(
    stream: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    dispatched: Optional[bool] = None,
    db: Session = Depends(_get_db),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Return unified feedback rows from all streams, LEFT JOIN'd to triage state."""
    rows = _fetch_rows(db, stream=stream, status=status, since=since, dispatched=dispatched)
    return {"items": rows, "count": len(rows)}


@router.get("/feedback/{stream}/{item_id}/screenshot")
def get_feedback_screenshot(
    stream: str,
    item_id: str,
    db: Session = Depends(_get_db),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Return the base64 screenshot data URL for a single feedback item, on demand.

    Only the ``product`` stream (public.feedback) carries screenshots; every other
    stream returns ``null``. Fetched lazily when the admin expands a row so the list
    endpoint never has to ship large base64 blobs for 500 rows at once.
    """
    if stream != "product":
        return {"screenshot_data": None}
    row = db.execute(
        text("SELECT screenshot_data FROM feedback WHERE CAST(id AS TEXT) = :id"),
        {"id": item_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"screenshot_data": row[0]}


class TriageUpdate(BaseModel):
    status: str
    owner: Optional[str] = None
    resolution: Optional[str] = None


_VALID_STATUSES = {"new", "reviewed", "acted_on", "closed"}


@router.patch("/feedback/{stream}/{item_id}")
def triage_feedback(
    stream: str,
    item_id: str,
    body: TriageUpdate,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Upsert triage state for a feedback item. Does NOT mutate ML source tables."""
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(_VALID_STATUSES)}",
        )

    now = datetime.utcnow().isoformat()
    db.execute(
        text(
            """
            INSERT INTO feedback_status (stream, source_id, status, owner, resolution, updated_at)
            VALUES (:stream, :source_id, :status, :owner, :resolution, :updated_at)
            ON CONFLICT (stream, source_id) DO UPDATE SET
                status     = excluded.status,
                owner      = excluded.owner,
                resolution = excluded.resolution,
                updated_at = excluded.updated_at
            """
        ),
        {
            "stream": stream,
            "source_id": item_id,
            "status": body.status,
            "owner": body.owner,
            "resolution": body.resolution,
            "updated_at": now,
        },
    )

    actor_id = str(user.get("id") or user.get("user_id") or "unknown")
    record_admin_event(
        db,
        actor_id=actor_id,
        event="feedback_triaged",
        entity="feedback_status",
        entity_id=item_id,
        detail={"stream": stream, "id": item_id, "status": body.status},
    )
    return {"stream": stream, "id": item_id, "status": body.status}


# ── Dispatch endpoint ─────────────────────────────────────────────────────────


class DispatchBody(BaseModel):
    confirm: Optional[bool] = None
    note: Optional[str] = None


@router.post("/feedback/{stream}/{item_id}/dispatch")
def dispatch_feedback_ticket(
    stream: str,
    item_id: str,
    body: DispatchBody,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Dispatch a feedback ticket to a routine.

    High-risk tickets (severity=critical OR area=isolation) require an explicit
    confirm=true in the request body — the human-in-the-loop gate.  Lower-risk
    tickets dispatch without confirmation.

    Side effects: sets dispatch_status/status='dispatched' + dispatch_ref on
    feedback_status, writes a 'ticket_dispatched' audit row.
    """
    # 1. Load ticket severity/area — 404 if no row exists.
    row = db.execute(
        text(
            "SELECT severity, area FROM feedback_status "
            "WHERE stream = :stream AND source_id = :source_id"
        ),
        {"stream": stream, "source_id": item_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    severity, area = row[0], row[1]

    # 2. HITL gate: high-risk tickets require explicit human confirmation.
    is_high_risk = severity == "critical" or area == "isolation"
    if is_high_risk and not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="high-risk ticket requires explicit confirm",
        )

    # 3. Dispatch: generate ref, update feedback_status, audit.
    dispatch_ref = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db.execute(
        text(
            "UPDATE feedback_status "
            "SET dispatch_ref = :dispatch_ref, dispatch_status = 'dispatched', "
            "    status = 'dispatched', updated_at = :now "
            "WHERE stream = :stream AND source_id = :source_id"
        ),
        {
            "dispatch_ref": dispatch_ref,
            "now": now,
            "stream": stream,
            "source_id": item_id,
        },
    )

    actor_id = str(user.get("id") or user.get("user_id") or "unknown")
    record_admin_event(
        db,
        actor_id=actor_id,
        event="ticket_dispatched",
        entity="feedback_status",
        entity_id=item_id,
        detail={
            "stream": stream,
            "severity": severity,
            "area": area,
            "dispatch_ref": dispatch_ref,
            "note": body.note,
        },
    )

    return {"dispatched": True, "dispatch_ref": dispatch_ref, "status": "dispatched"}
