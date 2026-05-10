"""
Admin Review Queue API - Admin-only endpoints for queue management.
List, assign, claim, status, resolve, defer, reopen.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from ...database import db
from ...services.review_queue_service import (
    assign_queue_item,
    backfill_queue_from_signals,
    change_queue_item_status,
    claim_queue_item,
    defer_queue_item,
    get_review_queue_activity,
    get_review_queue_item,
    get_review_queue_stats,
    list_admin_users_for_assignment,
    list_review_queue_items,
    reopen_queue_item,
    resolve_queue_item,
    unassign_queue_item,
    update_queue_item_notes,
)


def _require_admin(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    role = (user.get("role") or "").upper()
    if role == "ADMIN":
        return user
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() == "ADMIN":
        return user
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return user
    raise HTTPException(status_code=403, detail="Admin only")


router = APIRouter(prefix="/review-queue", tags=["admin-review-queue"])


class AssignBody(BaseModel):
    assignee_user_id: str


class StatusBody(BaseModel):
    status: str
    note: Optional[str] = None


class DeferBody(BaseModel):
    due_at: Optional[str] = None
    note: Optional[str] = None


class ResolveBody(BaseModel):
    resolution_summary: Optional[str] = None


class ReopenBody(BaseModel):
    note: Optional[str] = None


class NotesBody(BaseModel):
    notes: str


class BulkAssignBody(BaseModel):
    item_ids: List[str]
    assignee_user_id: str


class BulkStatusBody(BaseModel):
    item_ids: List[str]
    status: str
    note: Optional[str] = None


# --- List and detail ---
@router.get("")
def get_queue(
    status: Optional[str] = Query(None),
    priority_band: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    city_name: Optional[str] = Query(None),
    queue_item_type: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    unassigned_only: bool = Query(False),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("priority", regex="^(priority|created|due|age)$"),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_review_queue_items(
        status=status,
        priority_band=priority_band,
        assignee_id=assignee_id,
        country_code=country_code,
        city_name=city_name,
        queue_item_type=queue_item_type,
        overdue_only=overdue_only,
        unassigned_only=unassigned_only,
        search=search,
        limit=limit,
        offset=offset,
        sort=sort,
    )


@router.get("/stats")
def get_stats(user: Dict[str, Any] = Depends(_require_admin)):
    return get_review_queue_stats()


@router.get("/assignees")
def get_assignees(
    limit: int = Query(50, le=100),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return {"items": list_admin_users_for_assignment(limit=limit)}


@router.get("/{item_id}")
def get_item(item_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    item = get_review_queue_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return item


@router.get("/{item_id}/activity")
def get_activity(
    item_id: str,
    limit: int = Query(50, le=100),
    user: Dict[str, Any] = Depends(_require_admin),
):
    item = get_review_queue_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return {"items": get_review_queue_activity(item_id, limit=limit)}


# --- Actions ---
@router.post("/{item_id}/assign")
def assign_item(
    item_id: str,
    body: AssignBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = assign_queue_item(item_id, body.assignee_user_id, user.get("id", ""))
    if not result:
        raise HTTPException(status_code=404, detail="Queue item not found or cannot assign")
    return result


@router.post("/{item_id}/claim")
def claim_item(item_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    result = claim_queue_item(item_id, user.get("id", ""))
    if not result:
        raise HTTPException(status_code=404, detail="Queue item not found or cannot claim")
    return result


@router.post("/{item_id}/unassign")
def unassign_item(item_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    result = unassign_queue_item(item_id, user.get("id", ""))
    if not result:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return result


@router.post("/{item_id}/status")
def set_status(
    item_id: str,
    body: StatusBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = change_queue_item_status(
        item_id, body.status, user.get("id", ""), note=body.note
    )
    if not result:
        raise HTTPException(status_code=400, detail="Invalid status transition or item not found")
    return result


@router.post("/{item_id}/defer")
def defer_item(
    item_id: str,
    body: DeferBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = defer_queue_item(
        item_id, body.due_at, user.get("id", ""), note=body.note
    )
    if not result:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return result


@router.post("/{item_id}/resolve")
def resolve_item(
    item_id: str,
    body: ResolveBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = resolve_queue_item(
        item_id, user.get("id", ""), resolution_summary=body.resolution_summary
    )
    if not result:
        raise HTTPException(status_code=400, detail="Cannot resolve in current status")
    return result


@router.post("/{item_id}/reopen")
def reopen_item(
    item_id: str,
    body: ReopenBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = reopen_queue_item(item_id, user.get("id", ""), note=body.note)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot reopen")
    return result


@router.patch("/{item_id}/notes")
def update_notes(
    item_id: str,
    body: NotesBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = update_queue_item_notes(item_id, body.notes, user.get("id", ""))
    if not result:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return result


# --- Bulk ---
@router.post("/bulk-assign")
def bulk_assign(
    body: BulkAssignBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    updated = []
    for iid in body.item_ids:
        r = assign_queue_item(iid, body.assignee_user_id, user.get("id", ""))
        if r:
            updated.append(r.get("id"))
    return {"updated_count": len(updated), "updated_ids": updated}


@router.post("/bulk-status")
def bulk_status(
    body: BulkStatusBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    updated = []
    for iid in body.item_ids:
        r = change_queue_item_status(iid, body.status, user.get("id", ""), note=body.note)
        if r:
            updated.append(r.get("id"))
    return {"updated_count": len(updated), "updated_ids": updated}


# --- Backfill ---
@router.post("/backfill")
def backfill(user: Dict[str, Any] = Depends(_require_admin)):
    return backfill_queue_from_signals()
