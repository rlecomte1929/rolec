"""
Admin Staging Review API - Admin-only endpoints for staging review workflow.
List, inspect, approve, merge, reject staged resource/event candidates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...database import db
from ...services.staging_review_service import (
    approve_event_candidate_as_new,
    approve_resource_candidate_as_new,
    get_event_candidate_matches,
    get_resource_candidate_matches,
    get_staged_event_candidate,
    get_staged_resource_candidate,
    get_staging_dashboard_counts,
    ignore_event_candidate,
    ignore_resource_candidate,
    list_staged_event_candidates,
    list_staged_resource_candidates,
    mark_event_candidate_duplicate,
    mark_resource_candidate_duplicate,
    merge_event_candidate_into_live,
    merge_resource_candidate_into_live,
    reject_event_candidate,
    reject_resource_candidate,
    restore_event_candidate_to_review,
    restore_resource_candidate_to_review,
)


def _require_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Admin-only dependency."""
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


router = APIRouter(prefix="/staging", tags=["admin-staging"])


# --- Dashboard ---
@router.get("/dashboard")
def get_dashboard(user: Dict[str, Any] = Depends(_require_admin)):
    return get_staging_dashboard_counts()


# --- Resource candidates ---
@router.get("/resources")
def list_resources(
    status: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    city_name: Optional[str] = Query(None),
    category_key: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    trust_tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_staged_resource_candidates(
        status=status,
        country_code=country_code,
        city_name=city_name,
        category_key=category_key,
        resource_type=resource_type,
        trust_tier=trust_tier,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/resources/{candidate_id}")
def get_resource(candidate_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c


@router.get("/resources/{candidate_id}/matches")
def get_resource_matches(candidate_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"matches": get_resource_candidate_matches(candidate_id)}


@router.post("/resources/{candidate_id}/approve-new")
def approve_resource_new(
    candidate_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    reason = (payload or {}).get("reason") if payload else None
    out = approve_resource_candidate_as_new(candidate_id, user["id"], reason=reason)
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/resources/{candidate_id}/merge")
def merge_resource(
    candidate_id: str,
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    target_resource_id = payload.get("target_resource_id")
    if not target_resource_id:
        raise HTTPException(status_code=400, detail="target_resource_id required")
    out = merge_resource_candidate_into_live(
        candidate_id,
        target_resource_id,
        user["id"],
        merge_mode=payload.get("merge_mode", "overwrite_selected_fields"),
        fields_to_merge=payload.get("fields_to_merge"),
        reason=payload.get("reason"),
    )
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/resources/{candidate_id}/reject")
def reject_resource(
    candidate_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    reason = (payload or {}).get("reason") if payload else None
    out = reject_resource_candidate(candidate_id, user["id"], reason=reason)
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/resources/{candidate_id}/mark-duplicate")
def mark_resource_duplicate(
    candidate_id: str,
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    out = mark_resource_candidate_duplicate(
        candidate_id,
        user["id"],
        duplicate_of_candidate_id=payload.get("duplicate_of_candidate_id"),
        duplicate_of_live_resource_id=payload.get("duplicate_of_live_resource_id"),
        reason=payload.get("reason"),
    )
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/resources/{candidate_id}/ignore")
def ignore_resource(
    candidate_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    reason = (payload or {}).get("reason") if payload else None
    out = ignore_resource_candidate(candidate_id, user["id"], reason=reason)
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/resources/{candidate_id}/restore-review")
def restore_resource_review(
    candidate_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    out = restore_resource_candidate_to_review(candidate_id, user["id"])
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


# --- Event candidates ---
@router.get("/events")
def list_events(
    status: Optional[str] = Query(None),
    country_code: Optional[str] = Query(None),
    city_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    trust_tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_staged_event_candidates(
        status=status,
        country_code=country_code,
        city_name=city_name,
        event_type=event_type,
        trust_tier=trust_tier,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{candidate_id}")
def get_event(candidate_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    c = get_staged_event_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c


@router.get("/events/{candidate_id}/matches")
def get_event_matches(candidate_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    c = get_staged_event_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"matches": get_event_candidate_matches(candidate_id)}


@router.post("/events/{candidate_id}/approve-new")
def approve_event_new(
    candidate_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    reason = (payload or {}).get("reason") if payload else None
    out = approve_event_candidate_as_new(candidate_id, user["id"], reason=reason)
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/events/{candidate_id}/merge")
def merge_event(
    candidate_id: str,
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    target_event_id = payload.get("target_event_id")
    if not target_event_id:
        raise HTTPException(status_code=400, detail="target_event_id required")
    out = merge_event_candidate_into_live(
        candidate_id,
        target_event_id,
        user["id"],
        merge_mode=payload.get("merge_mode", "overwrite_selected_fields"),
        fields_to_merge=payload.get("fields_to_merge"),
        reason=payload.get("reason"),
    )
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/events/{candidate_id}/reject")
def reject_event(
    candidate_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    reason = (payload or {}).get("reason") if payload else None
    out = reject_event_candidate(candidate_id, user["id"], reason=reason)
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/events/{candidate_id}/mark-duplicate")
def mark_event_duplicate(
    candidate_id: str,
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    out = mark_event_candidate_duplicate(
        candidate_id,
        user["id"],
        duplicate_of_candidate_id=payload.get("duplicate_of_candidate_id"),
        duplicate_of_live_event_id=payload.get("duplicate_of_live_event_id"),
        reason=payload.get("reason"),
    )
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/events/{candidate_id}/ignore")
def ignore_event(
    candidate_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    reason = (payload or {}).get("reason") if payload else None
    out = ignore_event_candidate(candidate_id, user["id"], reason=reason)
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.post("/events/{candidate_id}/restore-review")
def restore_event_review(
    candidate_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    out = restore_event_candidate_to_review(candidate_id, user["id"])
    if "error" in out:
        raise HTTPException(status_code=400, detail=out["error"])
    return out