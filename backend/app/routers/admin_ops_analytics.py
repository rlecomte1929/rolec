"""
Admin Ops Analytics API - SLA, queue, reviewer, destination metrics.
Admin-only.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...database import db
from ...services.ops_analytics_service import (
    get_destination_ops_metrics,
    get_notification_ops_metrics,
    get_ops_bottlenecks,
    get_queue_backlog,
    get_queue_breaches,
    get_reviewer_workload,
    get_sla_overview,
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


router = APIRouter(prefix="/ops", tags=["admin-ops-analytics"])


@router.get("/sla/overview")
def sla_overview(
    country_code: Optional[str] = Query(None),
    days: int = Query(30, le=90),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return get_sla_overview(country_code=country_code, days=days)


@router.get("/queue/backlog")
def queue_backlog(
    country_code: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return get_queue_backlog(country_code=country_code)


@router.get("/queue/breaches")
def queue_breaches(
    country_code: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return get_queue_breaches(country_code=country_code, limit=limit)


@router.get("/reviewers/workload")
def reviewer_workload(user: Dict[str, Any] = Depends(_require_admin)):
    return get_reviewer_workload()


@router.get("/destinations")
def destinations(user: Dict[str, Any] = Depends(_require_admin)):
    return get_destination_ops_metrics()


@router.get("/notifications")
def notification_metrics(
    days: int = Query(7, le=90),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return get_notification_ops_metrics(days=days)


@router.get("/bottlenecks")
def bottlenecks(user: Dict[str, Any] = Depends(_require_admin)):
    return get_ops_bottlenecks()
