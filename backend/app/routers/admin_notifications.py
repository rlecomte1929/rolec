"""
Admin Ops Notifications API - Admin-only notification and escalation feed.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...database import db
from ...services.ops_notification_service import (
    acknowledge_notification,
    get_notification_events,
    get_notification_feed,
    get_notification_by_id,
    get_ops_notification_stats,
    list_ops_notifications,
    reopen_notification,
    resolve_notification,
    suppress_notification,
    recompute_time_based_notifications,
    sync_resolved_notifications,
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


router = APIRouter(prefix="/notifications", tags=["admin-notifications"])


@router.get("")
def get_list(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    notification_type: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    escalation_only: bool = Query(False),
    open_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_ops_notifications(
        status=status,
        severity=severity,
        notification_type=notification_type,
        country_code=country_code,
        escalation_only=escalation_only,
        open_only=open_only,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
def get_stats(user: Dict[str, Any] = Depends(_require_admin)):
    return get_ops_notification_stats()


@router.get("/feed")
def get_feed(
    limit: int = Query(20, le=50),
    critical_first: bool = Query(True),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return {"items": get_notification_feed(limit=limit, critical_first=critical_first)}


@router.get("/{notification_id}")
def get_one(notification_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    n = get_notification_by_id(notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    return n


@router.get("/{notification_id}/events")
def get_events(
    notification_id: str,
    limit: int = Query(50, le=100),
    user: Dict[str, Any] = Depends(_require_admin),
):
    n = get_notification_by_id(notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"items": get_notification_events(notification_id, limit=limit)}


@router.post("/{notification_id}/acknowledge")
def acknowledge(notification_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    result = acknowledge_notification(notification_id, user.get("id", ""))
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found or cannot acknowledge")
    return result


@router.post("/{notification_id}/resolve")
def resolve(
    notification_id: str,
    reason: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = resolve_notification(notification_id, user.get("id", ""), reason=reason)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found or cannot resolve")
    return result


@router.post("/{notification_id}/suppress")
def suppress(
    notification_id: str,
    until: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = suppress_notification(notification_id, user.get("id", ""), until=until)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.post("/{notification_id}/reopen")
def reopen(
    notification_id: str,
    reason: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    result = reopen_notification(notification_id, user.get("id", ""), reason=reason)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot reopen")
    return result


@router.post("/recompute")
def recompute(user: Dict[str, Any] = Depends(_require_admin)):
    return recompute_time_based_notifications()


@router.post("/sync")
def sync(user: Dict[str, Any] = Depends(_require_admin)):
    return sync_resolved_notifications()
