"""
HR Coordination — provider task management.

GET    /api/hr/cases/{case_id}/providers   — list providers assigned to a case
POST   /api/hr/cases/{case_id}/tasks       — assign a task to a provider
PATCH  /api/hr/tasks/{task_id}             — update a provider task
DELETE /api/hr/tasks/{task_id}             — cancel (soft-delete) a provider task
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db
from ..services.events_tracker import track as track_event
from ..services.outcome_recorder import record_outcome

router = APIRouter(prefix="/api/hr", tags=["hr-coordination"])


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

    track_event(
        "assignment.cancelled",
        entity_type="provider_task",
        entity_id=task_id,
        user_id=hr_user.get("id"),
        company_id=org_id,
        properties={"reason_code": "hr_cancelled"},
    )
