"""
HR Coordination — provider task management.

GET    /api/hr/cases/{case_id}/providers   — list providers assigned to a case
POST   /api/hr/cases/{case_id}/tasks       — assign a task to a provider
PATCH  /api/hr/tasks/{task_id}             — update a provider task
DELETE /api/hr/tasks/{task_id}             — cancel (soft-delete) a provider task
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.events_tracker import track as track_event
from ..services.outcome_recorder import record_outcome
from ..services.supplier_link_dispatch import (
    dispatch_supplier_links,
    resolve_rfq_targets,
)

router = APIRouter(prefix="/api/hr", tags=["hr-coordination"])

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AssignTaskBody(BaseModel):
    provider_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None


class UpdateTaskBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    # Optional outcome fields — only recorded when status → 'completed'
    quality_score: Optional[float] = None          # 1.0–5.0
    speed_score: Optional[float] = None            # 1.0–5.0
    communication_score: Optional[float] = None    # 1.0–5.0
    completed_on_time: Optional[bool] = None
    budget_variance_pct: Optional[float] = None    # (actual-budget)/budget×100
    hr_feedback: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /api/hr/cases/{case_id}/providers
# ---------------------------------------------------------------------------

@router.get("/cases/{case_id}/providers")
def get_case_providers(
    case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    Return all providers assigned to a case (scoped to org), each with their
    tasks array and aggregated task_counts.
    """
    # AIQ-1704: provider_tasks.case_id holds the canonical case id (assign_task
    # validates it against relocation_cases/cases), so resolve a (possibly
    # assignment) path id before reading — else the providers list is silently
    # empty on the HR case-detail URL. Fail closed on an unknown id; org scoping
    # below is unchanged (a cross-org case still returns no rows).
    ids = db.resolve_case_ids(case_id)
    if ids is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    case_id = ids.canonical_case_id
    with db.engine.begin() as conn:
        tasks = conn.execute(
            text(
                """
                SELECT id, case_id, provider_id, org_id, title, description,
                       status, due_date, created_at, updated_at
                FROM provider_tasks
                WHERE case_id = :case_id AND org_id = :org_id
                ORDER BY created_at ASC
                """
            ),
            {"case_id": case_id, "org_id": org_id},
        ).mappings().all()

    tasks = [dict(t) for t in tasks]

    # Normalise timestamps
    for t in tasks:
        for col in ("created_at", "updated_at", "due_date"):
            v = t.get(col)
            if hasattr(v, "isoformat"):
                t[col] = v.isoformat()

    provider_ids = list({t["provider_id"] for t in tasks})

    if not provider_ids:
        return {"providers": []}

    placeholders = ", ".join(f":pid_{i}" for i in range(len(provider_ids)))
    pid_params = {f"pid_{i}": pid for i, pid in enumerate(provider_ids)}

    with db.engine.begin() as conn:
        providers = conn.execute(
            text(
                f"""
                SELECT id, name, type, status, org_id
                FROM providers
                WHERE id IN ({placeholders}) AND org_id = :org_id
                """
            ),
            {**pid_params, "org_id": org_id},
        ).mappings().all()

    providers = [dict(p) for p in providers]

    tasks_by_provider: Dict[str, List] = {}
    for task in tasks:
        tasks_by_provider.setdefault(task["provider_id"], []).append(task)

    result = []
    for provider in providers:
        pid = provider["id"]
        provider_tasks = tasks_by_provider.get(pid, [])
        counts: Dict[str, int] = {
            "pending": 0, "in_progress": 0, "completed": 0, "cancelled": 0
        }
        for t in provider_tasks:
            s = t.get("status", "pending")
            if s in counts:
                counts[s] += 1
        result.append(
            {
                "id": provider["id"],
                "name": provider["name"],
                "type": provider.get("type"),
                "status": provider.get("status"),
                "tasks": provider_tasks,
                "task_counts": counts,
            }
        )

    return {"providers": result}


# ---------------------------------------------------------------------------
# GET /api/hr/cases/{case_id}/rfqs
# ---------------------------------------------------------------------------

@router.get("/cases/{case_id}/rfqs")
def get_case_rfqs(
    case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """[AIQ-1669] List the canonical RFQs an EMPLOYEE submitted for a case, read from
    `rfqs` (+ `rfq_items` + `rfq_recipients`) — the tables the employee actually writes,
    which no HR surface read before (the HR-initiated `rfq_requests` model was retired in
    AIQ-1681..1683 and its table archived to `rfq_requests_legacy`). Company-scoped: 404 (not 403) on a case
    outside the org so we don't leak case existence across tenants. Read-only — dispatch
    and supplier-token minting are AIQ-1670.
    """
    # Tenant scope — same UNION check assign_task uses (a case may live in either table).
    with db.engine.begin() as conn:
        case_ok = conn.execute(
            text(
                "SELECT 1 FROM relocation_cases WHERE CAST(id AS TEXT) = :cid AND CAST(company_id AS TEXT) = :org "
                "UNION SELECT 1 FROM cases WHERE CAST(id AS TEXT) = :cid AND CAST(company_id AS TEXT) = :org LIMIT 1"
            ),
            {"cid": case_id, "org": org_id},
        ).first()
    if not case_ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    with db.engine.begin() as conn:
        rfq_rows = conn.execute(
            text(
                "SELECT id, rfq_ref, case_id, status, created_at "
                "FROM rfqs WHERE CAST(case_id AS TEXT) = :cid ORDER BY created_at DESC"
            ),
            {"cid": case_id},
        ).mappings().all()

    rfqs = [dict(r) for r in rfq_rows]
    if not rfqs:
        return {"rfqs": []}

    rfq_ids = [str(r["id"]) for r in rfqs]
    placeholders = ", ".join(f":rid_{i}" for i in range(len(rfq_ids)))
    id_params = {f"rid_{i}": rid for i, rid in enumerate(rfq_ids)}

    with db.engine.begin() as conn:
        item_rows = conn.execute(
            text(f"SELECT rfq_id, service_key FROM rfq_items WHERE CAST(rfq_id AS TEXT) IN ({placeholders})"),
            id_params,
        ).mappings().all()
        # LEFT JOIN suppliers for the display name — vendor_id holds suppliers.id since
        # AIQ-1520; null-safe so a missing supplier row never 500s the HR read.
        recipient_rows = conn.execute(
            text(
                f"SELECT rr.rfq_id, rr.vendor_id, rr.status, rr.last_activity_at, s.name AS supplier_name "
                f"FROM rfq_recipients rr "
                f"LEFT JOIN suppliers s ON CAST(s.id AS TEXT) = CAST(rr.vendor_id AS TEXT) "
                f"WHERE CAST(rr.rfq_id AS TEXT) IN ({placeholders})"
            ),
            id_params,
        ).mappings().all()

    items_by_rfq: Dict[str, List[str]] = {}
    for it in item_rows:
        items_by_rfq.setdefault(str(it["rfq_id"]), []).append(it["service_key"])

    recipients_by_rfq: Dict[str, List[Dict[str, Any]]] = {}
    for rc in recipient_rows:
        activity = rc.get("last_activity_at")
        recipients_by_rfq.setdefault(str(rc["rfq_id"]), []).append(
            {
                "supplier_id": rc.get("vendor_id"),
                "supplier_name": rc.get("supplier_name"),
                "status": rc.get("status"),
                "last_activity_at": activity.isoformat() if hasattr(activity, "isoformat") else activity,
            }
        )

    result = []
    for r in rfqs:
        rid = str(r["id"])
        created = r.get("created_at")
        result.append(
            {
                "id": rid,
                "rfq_ref": r.get("rfq_ref"),
                "case_id": r.get("case_id"),
                "status": r.get("status"),
                "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
                "service_keys": items_by_rfq.get(rid, []),
                "recipients": recipients_by_rfq.get(rid, []),
            }
        )

    return {"rfqs": result}


# ---------------------------------------------------------------------------
# POST /api/hr/cases/{case_id}/rfqs/{rfq_id}/dispatch
# ---------------------------------------------------------------------------

class DispatchRfqBody(BaseModel):
    # Minting the link (token_hash) is harmless; emailing a real supplier is not, so sending
    # is OPT-IN and default OFF (and no-ops entirely without RESEND_API_KEY). See
    # supplier_link_dispatch. HR triggers this deliberately — never auto on employee submit.
    send_email: bool = False


@router.post("/cases/{case_id}/rfqs/{rfq_id}/dispatch")
def dispatch_case_rfq(
    case_id: str,
    rfq_id: str,
    body: DispatchRfqBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """[AIQ-1670] HR-gated dispatch of an employee-submitted RFQ: mint a supplier token for
    every recipient and (opt-in) email them, by REUSING the M1/M2/M3-audited
    `dispatch_supplier_links`. This is the HR action per the HR-payer model — dispatch never
    happens automatically on employee submit.

    Company-scoped, unlike the raw `POST /api/hr/rfqs/{rfq_id}/supplier-links`: the case must
    belong to the HR's org AND the RFQ must belong to that case, so an HR from another company
    cannot dispatch someone else's RFQ (404, no existence leak).
    """
    # Tenant scope — the case must belong to the HR's org.
    with db.engine.begin() as conn:
        case_ok = conn.execute(
            text(
                "SELECT 1 FROM relocation_cases WHERE CAST(id AS TEXT) = :cid AND CAST(company_id AS TEXT) = :org "
                "UNION SELECT 1 FROM cases WHERE CAST(id AS TEXT) = :cid AND CAST(company_id AS TEXT) = :org LIMIT 1"
            ),
            {"cid": case_id, "org": org_id},
        ).first()
    if not case_ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # …and the RFQ must belong to THAT case (else a valid-for-org case_id could be paired with
    # any rfq_id to dispatch a foreign request).
    with db.engine.begin() as conn:
        rfq_ok = conn.execute(
            text("SELECT 1 FROM rfqs WHERE CAST(id AS TEXT) = :rid AND CAST(case_id AS TEXT) = :cid LIMIT 1"),
            {"rid": rfq_id, "cid": case_id},
        ).first()
    if not rfq_ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found for this case")

    # Reuse the audited path: resolve every recipient, then mint tokens (+ opt-in email).
    targets = resolve_rfq_targets(rfq_id)
    results = dispatch_supplier_links(
        rfq_id=rfq_id, targets=targets, send_email=body.send_email,
        actor_email=hr_user.get("email"),
    )

    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="rfq",
                entity_id=rfq_id,
                action_type=ACTION_UPDATE,
                actor_type=ACTOR_HUMAN,
                actor_id=hr_user.get("id"),
                new_value={"event": "rfq_dispatched", "case_id": case_id,
                           "recipients": len(targets), "send_email": body.send_email},
            )
    except Exception:
        log.exception("audit: dispatch_case_rfq rfq=%s", rfq_id)

    track_event(
        "rfq.dispatched",
        entity_type="rfq",
        entity_id=rfq_id,
        user_id=hr_user.get("id"),
        company_id=org_id,
        properties={"case_id": case_id, "recipients": len(targets), "send_email": body.send_email},
    )

    return {"ok": True, "rfq_id": rfq_id, "dispatched": len(targets), "results": results}


# ---------------------------------------------------------------------------
# POST /api/hr/cases/{case_id}/tasks
# ---------------------------------------------------------------------------

@router.post("/cases/{case_id}/tasks", status_code=status.HTTP_201_CREATED)
def assign_task(
    case_id: str,
    body: AssignTaskBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    Create a new provider_task with status='pending'.
    Verifies the target provider belongs to this org.
    """
    # Tenant scope: the case must belong to the HR's org, else an HR from another
    # company could create tasks on it (cross-tenant write). 404 (not 403) so we
    # don't leak case existence across tenants.
    with db.engine.begin() as conn:
        _case_ok = conn.execute(
            text(
                "SELECT 1 FROM relocation_cases WHERE CAST(id AS TEXT) = :cid AND CAST(company_id AS TEXT) = :org "
                "UNION SELECT 1 FROM cases WHERE CAST(id AS TEXT) = :cid AND CAST(company_id AS TEXT) = :org LIMIT 1"
            ),
            {"cid": case_id, "org": org_id},
        ).first()
    if not _case_ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
        )
    with db.engine.begin() as conn:
        provider = conn.execute(
            text(
                "SELECT id FROM providers WHERE id = :pid AND org_id = :org_id LIMIT 1"
            ),
            {"pid": body.provider_id, "org_id": org_id},
        ).mappings().first()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found or does not belong to your organisation.",
        )

    now = datetime.utcnow().isoformat()
    task_id = str(uuid.uuid4())

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO provider_tasks
                    (id, case_id, provider_id, org_id, title, description,
                     status, due_date, created_at, updated_at)
                VALUES
                    (:id, :case_id, :provider_id, :org_id, :title, :description,
                     'pending', :due_date, :now, :now)
                """
            ),
            {
                "id": task_id,
                "case_id": case_id,
                "provider_id": body.provider_id,
                "org_id": org_id,
                "title": body.title,
                "description": body.description,
                "due_date": body.due_date,
                "now": now,
            },
        )
        try:
            insert_audit_log(
                conn,
                entity_type="provider_task",
                entity_id=task_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_HUMAN,
                actor_id=hr_user.get("id"),
                new_value={"event": "provider_task_assigned", "case_id": case_id,
                           "provider_id": body.provider_id},
            )
        except Exception:
            log.exception("audit: assign_task task=%s", task_id)

    track_event(
        "assignment.supplier_assigned",
        entity_type="provider_task",
        entity_id=task_id,
        user_id=hr_user.get("id"),
        company_id=org_id,
        properties={"case_id": case_id, "provider_id": body.provider_id, "title": body.title},
    )

    return {
        "task": {
            "id": task_id,
            "case_id": case_id,
            "provider_id": body.provider_id,
            "org_id": org_id,
            "title": body.title,
            "description": body.description,
            "status": "pending",
            "due_date": body.due_date,
            "created_at": now,
            "updated_at": now,
        }
    }


# ---------------------------------------------------------------------------
# PATCH /api/hr/tasks/{task_id}
# ---------------------------------------------------------------------------

VALID_TASK_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    body: UpdateTaskBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Update any subset of title, description, due_date, status on a task."""
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT id FROM provider_tasks WHERE id = :tid AND org_id = :org_id LIMIT 1"
            ),
            {"tid": task_id, "org_id": org_id},
        ).mappings().first()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or does not belong to your organisation.",
        )

    set_clauses = []
    params: Dict[str, Any] = {"tid": task_id, "org_id": org_id}

    if body.title is not None:
        set_clauses.append("title = :title")
        params["title"] = body.title
    if body.description is not None:
        set_clauses.append("description = :description")
        params["description"] = body.description
    if body.due_date is not None:
        set_clauses.append("due_date = :due_date")
        params["due_date"] = body.due_date
    if body.status is not None:
        if body.status not in VALID_TASK_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{body.status}'. Must be one of: {', '.join(sorted(VALID_TASK_STATUSES))}.",
            )
        set_clauses.append("status = :status")
        params["status"] = body.status

    if not set_clauses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update.",
        )

    set_clauses.append("updated_at = :updated_at")
    params["updated_at"] = datetime.utcnow().isoformat()

    set_sql = ", ".join(set_clauses)

    with db.engine.begin() as conn:
        conn.execute(
            text(
                f"UPDATE provider_tasks SET {set_sql} WHERE id = :tid AND org_id = :org_id"
            ),
            params,
        )
        updated = conn.execute(
            text(
                """
                SELECT id, case_id, provider_id, org_id, title, description,
                       status, due_date, created_at, updated_at
                FROM provider_tasks WHERE id = :tid
                """
            ),
            {"tid": task_id},
        ).mappings().first()
        if updated:
            try:
                insert_audit_log(
                    conn,
                    entity_type="provider_task",
                    entity_id=task_id,
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=hr_user.get("id"),
                    new_value={"event": "provider_task_updated", "status": body.status},
                )
            except Exception:
                log.exception("audit: update_task task=%s", task_id)

    row = dict(updated) if updated else {}
    for col in ("created_at", "updated_at", "due_date"):
        v = row.get(col)
        if hasattr(v, "isoformat"):
            row[col] = v.isoformat()

    # Emit lifecycle event when status changes
    if body.status is not None:
        _STATUS_TO_EVENT = {
            "completed":  "assignment.completed",
            "cancelled":  "assignment.cancelled",
            "in_progress": "assignment.in_progress",
        }
        evt = _STATUS_TO_EVENT.get(body.status)
        if evt:
            track_event(
                evt,
                entity_type="provider_task",
                entity_id=task_id,
                user_id=hr_user.get("id"),
                company_id=org_id,
                properties={"new_status": body.status, "case_id": row.get("case_id")},
            )

        # Record outcome when a task is marked completed (MATCHING-5B)
        # Scores are optional — the outcome row is still created without them
        # so we always capture completion facts even without quality ratings.
        if body.status == "completed":
            provider_id = row.get("provider_id")
            if provider_id:
                record_outcome(
                    assignment_id=task_id,
                    supplier_id=provider_id,
                    rated_by=hr_user.get("id"),
                    quality_score=body.quality_score,
                    speed_score=body.speed_score,
                    communication_score=body.communication_score,
                    completed_on_time=body.completed_on_time,
                    budget_variance_pct=body.budget_variance_pct,
                    hr_feedback=body.hr_feedback,
                    source_table="provider_tasks",
                )

    return {"task": row}


# ---------------------------------------------------------------------------
# DELETE /api/hr/tasks/{task_id}
# ---------------------------------------------------------------------------

@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def cancel_task(
    task_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> None:
    """Soft-delete: sets task status to 'cancelled'. Returns 204 No Content."""
    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT id FROM provider_tasks WHERE id = :tid AND org_id = :org_id LIMIT 1"
            ),
            {"tid": task_id, "org_id": org_id},
        ).mappings().first()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or does not belong to your organisation.",
        )

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE provider_tasks
                SET status = 'cancelled', updated_at = :now
                WHERE id = :tid AND org_id = :org_id
                """
            ),
            {"tid": task_id, "org_id": org_id, "now": datetime.utcnow().isoformat()},
        )
        try:
            insert_audit_log(
                conn,
                entity_type="provider_task",
                entity_id=task_id,
                action_type=ACTION_UPDATE,
                actor_type=ACTOR_HUMAN,
                actor_id=hr_user.get("id"),
                new_value={"event": "provider_task_cancelled"},
            )
        except Exception:
            log.exception("audit: cancel_task task=%s", task_id)

    track_event(
        "assignment.cancelled",
        entity_type="provider_task",
        entity_id=task_id,
        user_id=hr_user.get("id"),
        company_id=org_id,
        properties={"reason_code": "hr_cancelled"},
    )
