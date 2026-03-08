"""
Admin Resources CMS API - Admin-only endpoints for managing resources, events, taxonomy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...database import db
from ...services.admin_resources import (
    approve_event,
    approve_resource,
    archive_event,
    archive_resource,
    create_event,
    create_resource,
    create_resource_category,
    create_resource_source,
    create_resource_tag,
    deactivate_resource_category,
    get_admin_dashboard_counts,
    get_admin_event_by_id,
    get_admin_resource_by_id,
    get_resource_audit_log,
    get_resource_audit_log_global,
    list_admin_events,
    list_admin_resources,
    list_resource_categories,
    list_resource_sources,
    list_resource_tags,
    publish_event,
    publish_resource,
    restore_event,
    restore_resource,
    submit_event_for_review,
    submit_resource_for_review,
    unpublish_event,
    unpublish_resource,
    update_event,
    update_resource,
    update_resource_category,
    update_resource_source,
    update_resource_tag,
)


def _require_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Admin-only dependency (avoids circular import from main)."""
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


router = APIRouter(prefix="/resources", tags=["admin-resources"])


# --- Resources list & counts (must be before /{resource_id}) ---
@router.get("")
def list_resources(
    country_code: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    audience: Optional[str] = Query(None),
    featured: Optional[bool] = Query(None),
    family_friendly: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_admin_resources(
        country_code=country_code,
        city=city,
        category_id=category_id,
        status=status,
        audience=audience,
        featured=featured,
        family_friendly=family_friendly,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/counts")
def get_counts(user: Dict[str, Any] = Depends(_require_admin)):
    return get_admin_dashboard_counts()


@router.get("/audit-log")
def get_global_audit_log(
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return get_resource_audit_log_global(entity_type=entity_type, limit=limit, offset=offset)


# --- Events (must be before /{resource_id} to avoid "events" matching resource_id) ---
@router.get("/events")
def list_events(
    country_code: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    family_friendly: Optional[bool] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_admin_events(
        country_code=country_code,
        city=city,
        event_type=event_type,
        status=status,
        family_friendly=family_friendly,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}")
def get_event(event_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    e = get_admin_event_by_id(event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


@router.post("/events")
def create_event_endpoint(payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    return create_event(payload, user["id"])


@router.put("/events/{event_id}")
def update_event_endpoint(event_id: str, payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    e = update_event(event_id, payload, user["id"])
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


@router.post("/events/{event_id}/publish")
def publish_event_endpoint(event_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    e = publish_event(event_id, user["id"])
    if not e:
        raise HTTPException(status_code=400, detail="Invalid transition or event not found")
    return e


@router.post("/events/{event_id}/archive")
def archive_event_endpoint(event_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    e = archive_event(event_id, user["id"])
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


@router.post("/events/{event_id}/submit-for-review")
def submit_event_for_review_endpoint(event_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    e = submit_event_for_review(event_id, user["id"])
    if not e:
        raise HTTPException(status_code=400, detail="Invalid transition or event not found")
    return e


@router.post("/events/{event_id}/approve")
def approve_event_endpoint(
    event_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    notes = (payload or {}).get("notes") if payload else None
    e = approve_event(event_id, user["id"], notes=notes)
    if not e:
        raise HTTPException(status_code=400, detail="Invalid transition or event not found")
    return e


@router.post("/events/{event_id}/unpublish")
def unpublish_event_endpoint(event_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    e = unpublish_event(event_id, user["id"])
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


@router.post("/events/{event_id}/restore")
def restore_event_endpoint(event_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    e = restore_event(event_id, user["id"])
    if not e:
        raise HTTPException(status_code=404, detail="Event not found or not archived")
    return e


@router.get("/events/{event_id}/audit")
def get_event_audit(event_id: str, limit: int = Query(50, le=100), user: Dict[str, Any] = Depends(_require_admin)):
    return {"entries": get_resource_audit_log("event", event_id, limit=limit)}


# --- Taxonomy (before /{resource_id}) ---
@router.get("/taxonomy/categories")
def list_categories(user: Dict[str, Any] = Depends(_require_admin)):
    return {"categories": list_resource_categories()}


@router.post("/taxonomy/categories")
def create_category_endpoint(payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    return create_resource_category(payload, user["id"])


@router.put("/taxonomy/categories/{category_id}")
def update_category_endpoint(category_id: str, payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    r = update_resource_category(category_id, payload, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Category not found")
    return r


@router.delete("/taxonomy/categories/{category_id}")
def deactivate_category_endpoint(category_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = deactivate_resource_category(category_id, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Category not found")
    return r


@router.get("/taxonomy/tags")
def list_tags(tag_group: Optional[str] = Query(None), user: Dict[str, Any] = Depends(_require_admin)):
    return {"tags": list_resource_tags(tag_group=tag_group)}


@router.post("/taxonomy/tags")
def create_tag_endpoint(payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    return create_resource_tag(payload, user["id"])


@router.put("/taxonomy/tags/{tag_id}")
def update_tag_endpoint(tag_id: str, payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    r = update_resource_tag(tag_id, payload, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Tag not found")
    return r


@router.get("/taxonomy/sources")
def list_sources(user: Dict[str, Any] = Depends(_require_admin)):
    return {"sources": list_resource_sources()}


@router.post("/taxonomy/sources")
def create_source_endpoint(payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    return create_resource_source(payload, user["id"])


@router.put("/taxonomy/sources/{source_id}")
def update_source_endpoint(source_id: str, payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    r = update_resource_source(source_id, payload, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Source not found")
    return r


# --- Single resource (last, to avoid path conflicts) ---
@router.get("/{resource_id}")
def get_resource(resource_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = get_admin_resource_by_id(resource_id)
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    return r


@router.post("")
def create_resource_endpoint(payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    return create_resource(payload, user["id"])


@router.put("/{resource_id}")
def update_resource_endpoint(resource_id: str, payload: Dict[str, Any], user: Dict[str, Any] = Depends(_require_admin)):
    r = update_resource(resource_id, payload, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    return r


@router.post("/{resource_id}/submit-for-review")
def submit_for_review_endpoint(resource_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = submit_resource_for_review(resource_id, user["id"])
    if not r:
        raise HTTPException(status_code=400, detail="Invalid transition or resource not found")
    return r


@router.post("/{resource_id}/approve")
def approve_resource_endpoint(
    resource_id: str,
    payload: Optional[Dict[str, Any]] = None,
    user: Dict[str, Any] = Depends(_require_admin),
):
    notes = (payload or {}).get("notes") if payload else None
    r = approve_resource(resource_id, user["id"], notes=notes)
    if not r:
        raise HTTPException(status_code=400, detail="Invalid transition or resource not found")
    return r


@router.post("/{resource_id}/publish")
def publish_resource_endpoint(resource_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = publish_resource(resource_id, user["id"])
    if not r:
        raise HTTPException(status_code=400, detail="Invalid transition or resource not found")
    return r


@router.post("/{resource_id}/unpublish")
def unpublish_resource_endpoint(resource_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = unpublish_resource(resource_id, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    return r


@router.post("/{resource_id}/archive")
def archive_resource_endpoint(resource_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = archive_resource(resource_id, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    return r


@router.post("/{resource_id}/restore")
def restore_resource_endpoint(resource_id: str, user: Dict[str, Any] = Depends(_require_admin)):
    r = restore_resource(resource_id, user["id"])
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found or not archived")
    return r


@router.get("/{resource_id}/audit")
def get_resource_audit(resource_id: str, limit: int = Query(50, le=100), user: Dict[str, Any] = Depends(_require_admin)):
    return {"entries": get_resource_audit_log("resource", resource_id, limit=limit)}
