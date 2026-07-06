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
from ..services.feedback_triage import classify
from ..services.feedback_task_engineer import engineer_task
from ..services import notion_work_queue

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
    fs.status, fs.owner, fs.resolution, fs.dispatch_context,
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
    # 1. Load existing triage severity/area (may not exist yet — a never-triaged
    #    item can still be dispatched; the row is created below).
    row = db.execute(
        text(
            "SELECT severity, area FROM feedback_status "
            "WHERE stream = :stream AND source_id = :source_id"
        ),
        {"stream": stream, "source_id": item_id},
    ).fetchone()
    severity, area = (row[0], row[1]) if row is not None else (None, None)

    # 2. HITL gate: high-risk tickets require explicit human confirmation.
    is_high_risk = severity == "critical" or area == "isolation"
    if is_high_risk and not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="high-risk ticket requires explicit confirm",
        )

    # 3. Dispatch: generate ref, upsert feedback_status (create the ticket if it
    #    doesn't exist yet so dispatch never 404s), audit.
    #    Dispatch state lives in dispatch_status — NOT in status. status has a CHECK
    #    (new/reviewed/acted_on/closed); writing 'dispatched' there violates it (500).
    #    On insert use the valid default 'new'; on conflict leave the triage status
    #    untouched and only flip dispatch_status/dispatch_ref.
    dispatch_ref = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    db.execute(
        text(
            "INSERT INTO feedback_status "
            "(stream, source_id, status, dispatch_ref, dispatch_status, updated_at) "
            "VALUES (:stream, :source_id, 'new', :dispatch_ref, 'dispatched', :now) "
            "ON CONFLICT (stream, source_id) DO UPDATE SET "
            "    dispatch_ref = excluded.dispatch_ref, "
            "    dispatch_status = 'dispatched', "
            "    updated_at = excluded.updated_at"
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


# ── Dispatch → AI Work Queue (context → engineered task → Notion) ─────────────


class ContextBody(BaseModel):
    context: str = ""


@router.put("/feedback/{stream}/{item_id}/context")
def set_dispatch_context(
    stream: str,
    item_id: str,
    body: ContextBody,
    db: Session = Depends(_get_db),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Save the admin's per-item dispatch context (upserts feedback_status)."""
    now = datetime.utcnow().isoformat()
    db.execute(
        text(
            "INSERT INTO feedback_status (stream, source_id, status, dispatch_context, updated_at) "
            "VALUES (:s, :id, 'new', :ctx, :now) "
            "ON CONFLICT (stream, source_id) DO UPDATE SET "
            "    dispatch_context = excluded.dispatch_context, updated_at = excluded.updated_at"
        ),
        {"s": stream, "id": item_id, "ctx": body.context, "now": now},
    )
    return {"ok": True, "context": body.context}


class PreviewBody(BaseModel):
    text: Optional[str] = None
    category: str = "bug"


def _load_product_fields(db: Session, item_id: str) -> Dict[str, Any]:
    """Enrich a product-stream item from public.feedback (page_url/screenshot/reporter/report_id)."""
    row = db.execute(
        text(
            "SELECT message, category, page_url, "
            "(CASE WHEN screenshot_data IS NOT NULL THEN 1 ELSE 0 END), reporter_name, report_id "
            "FROM feedback WHERE CAST(id AS TEXT) = :id"
        ),
        {"id": item_id},
    ).fetchone()
    if not row:
        return {}
    return {
        "message": row[0] or "",
        "category": row[1] or "bug",
        "page_url": row[2],
        "has_screenshot": bool(row[3]),
        "reporter_name": row[4],
        "report_id": row[5],
    }


@router.post("/feedback/{stream}/{item_id}/dispatch/preview")
def dispatch_preview(
    stream: str,
    item_id: str,
    body: PreviewBody,
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Generate (no side effects) an engineered AI Work Queue task for review.
    Context is REQUIRED (400 when empty). Sync route — engineer_task uses the
    proven synchronous LLM path.

    Deliberately does NOT use Depends(_get_db): reads happen in a short-lived
    session that is CLOSED before the ~15s LLM call. Holding an idle pooled
    connection through the LLM call gets it dropped by the Supabase pooler → the
    trailing commit then fails with "SSL connection has been closed" (500).
    """
    _db = SessionLocal()
    try:
        fs = _db.execute(
            text(
                "SELECT dispatch_context, severity, area FROM feedback_status "
                "WHERE stream = :s AND source_id = :id"
            ),
            {"s": stream, "id": item_id},
        ).fetchone()
        pf = _load_product_fields(_db, item_id) if stream == "product" else {}
    finally:
        _db.close()

    dispatch_context = (fs[0] if fs else None) or ""
    if not dispatch_context.strip():
        raise HTTPException(status_code=400, detail="Add context on this item before dispatching.")
    severity = fs[1] if fs else None
    area = fs[2] if fs else None

    text_val = body.text or ""
    category = body.category or "bug"
    page_url = None
    has_screenshot = False
    reporter_name = None
    if pf:
        text_val = text_val or pf["message"]
        category = category or pf["category"]
        page_url = pf["page_url"]
        has_screenshot = pf["has_screenshot"]
        reporter_name = pf["reporter_name"]

    if not severity or not area:
        cls = classify(text_val, category)
        severity = severity or cls["severity"]
        area = area or cls["area"]

    try:
        task = engineer_task(
            text=text_val,
            category=category,
            page_url=page_url,
            severity=severity,
            area=area,
            has_screenshot=has_screenshot,
            reporter_name=reporter_name,
            admin_context=dispatch_context,
        )
    except Exception as exc:  # noqa: BLE001 — surface LLM failure clearly, never hang/500 opaquely
        log.warning("dispatch_preview engineer_task failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Could not engineer the task: {exc}") from exc
    return {"task": task}


class CreateTaskBody(BaseModel):
    task: Dict[str, Any]
    confirm: bool = True


@router.post("/feedback/{stream}/{item_id}/dispatch/create")
def dispatch_create(
    stream: str,
    item_id: str,
    body: CreateTaskBody,
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Create the AI Work Queue Notion page from the (admin-reviewed) task, mark the
    item dispatched with the Notion URL as dispatch_ref, and audit."""
    task = body.task or {}
    if not task.get("title"):
        raise HTTPException(status_code=400, detail="Task title is required.")

    report_id = item_id
    message = page_url = ""
    reporter_name = None
    if stream == "product":
        pf = _load_product_fields(db, item_id)
        if pf:
            report_id = pf["report_id"] or item_id
            message = pf["message"]
            page_url = pf["page_url"] or ""
            reporter_name = pf["reporter_name"]

    failure_evidence = (
        f"Reported via the feedback widget (stream={stream}). "
        f"Page: {page_url or '?'} · Reporter: {reporter_name or '?'} · Ref: {report_id}.\n\n"
        f"Original message:\n{message or '(see admin console)'}"
    )
    context_links = f"https://relopass.com/admin/feedback  (report_id={report_id})"

    try:
        url = notion_work_queue.create_work_queue_task(
            task, failure_evidence=failure_evidence, context_links=context_links
        )
    except notion_work_queue.NotionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except notion_work_queue.NotionApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    now = datetime.utcnow().isoformat()
    db.execute(
        text(
            "INSERT INTO feedback_status (stream, source_id, status, dispatch_ref, dispatch_status, updated_at) "
            "VALUES (:s, :id, 'new', :ref, 'dispatched', :now) "
            "ON CONFLICT (stream, source_id) DO UPDATE SET "
            "    dispatch_ref = excluded.dispatch_ref, dispatch_status = 'dispatched', "
            "    updated_at = excluded.updated_at"
        ),
        {"s": stream, "id": item_id, "ref": url, "now": now},
    )
    record_admin_event(
        db,
        actor_id=str(user.get("id") or user.get("user_id") or "unknown"),
        event="ticket_dispatched",
        entity="feedback_status",
        entity_id=item_id,
        detail={"stream": stream, "notion_url": url, "title": task.get("title")},
    )
    return {"dispatched": True, "url": url, "dispatch_ref": url}
