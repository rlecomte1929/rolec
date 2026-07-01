"""Admin unified feedback console — Task 6.

GET  /api/admin/feedback?stream=&status=&since=  → normalized rows across all streams
PATCH /api/admin/feedback/{stream}/{id}           → upsert feedback_status + audit

ML tables (feedback / ai_human_feedback / policy_answer_helpfulness) are NEVER mutated.
All mutations go to feedback_status only.

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md rule).
"""
from __future__ import annotations

import logging
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

# The three stream sub-queries are UNION ALL'd together, then LEFT JOIN'd to
# feedback_status to pick up triage state.  CAST(x AS TEXT) keeps the query
# compatible with both SQLite (tests) and Postgres (prod).

_UNION_SQL = """
SELECT
    CAST(f.id        AS TEXT) AS id,
    'product'                 AS stream,
    COALESCE(f.report_id, CAST(f.id AS TEXT)) AS source_ref,
    f.message                 AS text,
    f.category                AS verdict,
    CAST(f.user_id   AS TEXT) AS user_id,
    CAST(NULL AS TEXT)        AS company_id,
    f.created_at
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
    h.created_at
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
    p.created_at
FROM policy_answer_helpfulness p
"""

_OUTER_SQL = """
SELECT
    base.id, base.stream, base.source_ref, base.text, base.verdict,
    base.user_id, base.company_id, base.created_at,
    fs.status, fs.owner, fs.resolution
FROM (
    {union}
) AS base
LEFT JOIN feedback_status fs
       ON fs.stream    = base.stream
      AND fs.source_id = base.id
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

    sql = _OUTER_SQL.format(union=_UNION_SQL, filters="\n".join(filters))
    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/feedback")
def list_feedback(
    stream: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    db: Session = Depends(_get_db),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Return unified feedback rows from all streams, LEFT JOIN'd to triage state."""
    rows = _fetch_rows(db, stream=stream, status=status, since=since)
    return {"items": rows, "count": len(rows)}


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
