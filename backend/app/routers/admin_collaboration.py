"""
Admin Collaboration API - Internal threads and comments.
Admin-only. Attached to queue items, notifications, staged candidates, live resources/events.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from ...database import db
from ...services.collaboration_service import (
    close_thread,
    create_comment,
    delete_comment,
    edit_comment,
    get_collaboration_unread_count,
    get_or_create_thread,
    get_thread_by_id,
    get_thread_for_target,
    get_thread_summary_for_target,
    get_thread_summaries_batch,
    list_comments,
    mark_thread_read,
    reopen_thread,
    resolve_thread,
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


router = APIRouter(prefix="/collaboration", tags=["admin-collaboration"])


class CreateCommentBody(BaseModel):
    body: str
    parent_comment_id: Optional[str] = None


class EditCommentBody(BaseModel):
    body: str


class BatchSummaryRequest(BaseModel):
    targets: List[Dict[str, str]]  # [{target_type, target_id}]


@router.get("/threads/by-target")
def get_thread(
    target_type: str = Query(...),
    target_id: str = Query(...),
    user: Dict[str, Any] = Depends(_require_admin),
):
    t = get_thread_for_target(target_type, target_id, user.get("id", ""))
    if not t:
        return {"thread": None}
    return {"thread": t}


@router.post("/threads/by-target")
def get_or_create(
    target_type: str = Query(...),
    target_id: str = Query(...),
    title: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    t = get_or_create_thread(target_type, target_id, user.get("id", ""), title=title)
    if not t:
        raise HTTPException(status_code=403, detail="Cannot access or create thread")
    return {"thread": t}


@router.post("/threads/summaries")
def batch_summaries(
    body: BatchSummaryRequest,
    user: Dict[str, Any] = Depends(_require_admin),
):
    summaries = get_thread_summaries_batch(body.targets, user.get("id", ""))
    return {"summaries": summaries}


@router.get("/threads/summary")
def get_summary(
    target_type: str = Query(...),
    target_id: str = Query(...),
    user: Dict[str, Any] = Depends(_require_admin),
):
    s = get_thread_summary_for_target(target_type, target_id, user.get("id", ""))
    if not s:
        return {"summary": None}
    return {"summary": s}


@router.get("/threads/{thread_id}")
def get_one(thread_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    t = get_thread_by_id(thread_id, user.get("id", ""))
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread": t}


@router.get("/threads/{thread_id}/comments")
def get_comments(thread_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    comments = list_comments(thread_id, user.get("id", ""))
    return {"comments": comments}


@router.post("/threads/{thread_id}/comments")
def post_comment(
    thread_id: str,
    body: CreateCommentBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    c = create_comment(thread_id, body.body, user.get("id", ""), parent_comment_id=body.parent_comment_id)
    if not c:
        raise HTTPException(status_code=400, detail="Cannot create comment")
    return {"comment": c}


@router.patch("/comments/{comment_id}")
def patch_comment(
    comment_id: str,
    body: EditCommentBody,
    user: Dict[str, Any] = Depends(_require_admin),
):
    c = edit_comment(comment_id, body.body, user.get("id", ""))
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found or cannot edit")
    return {"comment": c}


@router.delete("/comments/{comment_id}")
def del_comment(comment_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    ok = delete_comment(comment_id, user.get("id", ""))
    if not ok:
        raise HTTPException(status_code=404, detail="Comment not found or cannot delete")
    return {"ok": True}


@router.post("/threads/{thread_id}/resolve")
def resolve(
    thread_id: str,
    note: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    t = resolve_thread(thread_id, user.get("id", ""), note=note)
    if not t:
        raise HTTPException(status_code=400, detail="Cannot resolve")
    return {"thread": t}


@router.post("/threads/{thread_id}/reopen")
def reopen(thread_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    t = reopen_thread(thread_id, user.get("id", ""))
    if not t:
        raise HTTPException(status_code=400, detail="Cannot reopen")
    return {"thread": t}


@router.post("/threads/{thread_id}/close")
def close(thread_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    t = close_thread(thread_id, user.get("id", ""))
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread": t}


@router.get("/notifications/unread-count")
def unread_count(user: Dict[str, Any] = Depends(_require_admin)):
    count = get_collaboration_unread_count(user.get("id", ""))
    return {"count": count}


@router.post("/threads/{thread_id}/read")
def mark_read(
    thread_id: str,
    last_comment_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    ok = mark_thread_read(thread_id, user.get("id", ""), last_comment_id=last_comment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}
