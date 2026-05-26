"""
Admin Resources CMS - Service layer.
Handles CRUD, workflow, audit, and taxonomy for country_resources and rkg_country_events.
All mutating operations require admin role (enforced at API layer).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

_RESOURCE_STATUSES = frozenset({"draft", "in_review", "approved", "published", "archived"})
_TRANSITIONS = {
    "draft": {"in_review"},
    "in_review": {"approved", "draft"},
    "approved": {"published", "draft"},
    "published": {"archived"},
    "archived": {"draft", "approved"},
}


def _get_supabase():
    return get_supabase_admin_client()


def _log_audit(
    entity_type: str,
    entity_id: str,
    action_type: str,
    user_id: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    change_summary: Optional[str] = None,
) -> None:
    try:
        _get_supabase().table("resource_audit_log").insert({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action_type": action_type,
            "performed_by_user_id": user_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "change_summary": change_summary,
        }).execute()
    except Exception:
        pass


def _can_transition(from_status: str, to_status: str) -> bool:
    return to_status in _TRANSITIONS.get(from_status or "draft", set())


# --- Authorization helpers (used at API layer) ---
def can_manage_resources(user: Dict[str, Any]) -> bool:
    return bool(user.get("is_admin") or (user.get("role") or "").upper() == "ADMIN")


def can_publish_resources(user: Dict[str, Any]) -> bool:
    return can_manage_resources(user)


def can_view_admin_resources_console(user: Dict[str, Any]) -> bool:
    return can_manage_resources(user)


def can_view_published_resources(user: Dict[str, Any]) -> bool:
    role = (user.get("role") or "").upper()
    return role in ("ADMIN", "HR", "EMPLOYEE")


# --- Resources ---
def list_admin_resources(
    country_code: Optional[str] = None,
    city: Optional[str] = None,
    category_id: Optional[str] = None,
    status: Optional[str] = None,
    audience: Optional[str] = None,
    featured: Optional[bool] = None,
    family_friendly: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """List resources for admin CMS (all statuses)."""
    supabase = _get_supabase()
    q = supabase.table("country_resources").select("*", count="exact").eq("is_active", True)
    if country_code:
        q = q.eq("country_code", country_code.upper())
    if city:
        q = q.eq("city_name", city)
    if category_id:
        q = q.eq("category_id", category_id)
    if status:
        q = q.eq("status", status)
    if audience:
        q = q.eq("audience_type", audience)
    if featured is not None:
        q = q.eq("is_featured", featured)
    if family_friendly is not None:
        q = q.eq("is_family_friendly", family_friendly)
    if search:
        q = q.ilike("title", f"%{search}%")
    q = q.order("updated_at", desc=True).range(offset, offset + limit - 1)
    r = q.execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_admin_resource_by_id(resource_id: str) -> Optional[Dict[str, Any]]:
    """Get single resource by id (admin view, includes internal fields)."""
    supabase = _get_supabase()
    r = supabase.table("country_resources").select("*").eq("id", resource_id).limit(1).execute()
    if not r.data:
        return None
    row = r.data[0]
    tags_r = supabase.table("country_resource_tags").select("tag_id").eq("resource_id", resource_id).execute()
    row["tag_ids"] = [t["tag_id"] for t in (tags_r.data or [])]
    return row


def create_resource(payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Create a new resource (draft)."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "country_code": (payload.get("country_code") or "NO").upper(),
        "country_name": payload.get("country_name"),
        "city_name": payload.get("city_name"),
        "category_id": payload.get("category_id"),
        "title": payload.get("title", "").strip() or "Untitled",
        "summary": payload.get("summary"),
        "body": payload.get("body"),
        "content_json": payload.get("content_json") or {},
        "resource_type": payload.get("resource_type") or "guide",
        "audience_type": payload.get("audience_type") or "all",
        "min_child_age": payload.get("min_child_age"),
        "max_child_age": payload.get("max_child_age"),
        "budget_tier": payload.get("budget_tier"),
        "language_code": payload.get("language_code"),
        "is_family_friendly": bool(payload.get("is_family_friendly", False)),
        "is_featured": bool(payload.get("is_featured", False)),
        "address": payload.get("address"),
        "district": payload.get("district"),
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "price_range_text": payload.get("price_range_text"),
        "external_url": payload.get("external_url"),
        "booking_url": payload.get("booking_url"),
        "contact_info": payload.get("contact_info"),
        "opening_hours": payload.get("opening_hours"),
        "source_id": payload.get("source_id"),
        "trust_tier": payload.get("trust_tier"),
        "effective_from": payload.get("effective_from"),
        "effective_to": payload.get("effective_to"),
        "status": "draft",
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
        "internal_notes": payload.get("internal_notes"),
        "review_notes": payload.get("review_notes"),
        "version_number": 1,
        "is_visible_to_end_users": False,
    }
    r = supabase.table("country_resources").insert(row).execute()
    created = (r.data or [{}])[0]
    rid = created.get("id")
    if rid:
        tag_ids = payload.get("tag_ids") or []
        for tid in tag_ids:
            try:
                supabase.table("country_resource_tags").insert({"resource_id": rid, "tag_id": tid}).execute()
            except Exception:
                pass
        _log_audit("resource", str(rid), "create", user_id, None, "draft", f"Created: {created.get('title', '')}")
    return created


def update_resource(resource_id: str, payload: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    """Update resource. Preserves status unless workflow action. Returns updated row."""
    supabase = _get_supabase()
    existing = get_admin_resource_by_id(resource_id)
    if not existing:
        return None
    prev_status = existing.get("status", "draft")
    upd = {
        "updated_by_user_id": user_id,
        "country_code": payload.get("country_code") or existing.get("country_code"),
        "country_name": payload.get("country_name", existing.get("country_name")),
        "city_name": payload.get("city_name", existing.get("city_name")),
        "category_id": payload.get("category_id", existing.get("category_id")),
        "title": payload.get("title", existing.get("title")) or "Untitled",
        "summary": payload.get("summary", existing.get("summary")),
        "body": payload.get("body", existing.get("body")),
        "content_json": payload.get("content_json", existing.get("content_json")) or {},
        "resource_type": payload.get("resource_type", existing.get("resource_type")),
        "audience_type": payload.get("audience_type", existing.get("audience_type")),
        "min_child_age": payload.get("min_child_age", existing.get("min_child_age")),
        "max_child_age": payload.get("max_child_age", existing.get("max_child_age")),
        "budget_tier": payload.get("budget_tier", existing.get("budget_tier")),
        "language_code": payload.get("language_code", existing.get("language_code")),
        "is_family_friendly": bool(payload.get("is_family_friendly", existing.get("is_family_friendly", False))),
        "is_featured": bool(payload.get("is_featured", existing.get("is_featured", False))),
        "address": payload.get("address", existing.get("address")),
        "district": payload.get("district", existing.get("district")),
        "latitude": payload.get("latitude", existing.get("latitude")),
        "longitude": payload.get("longitude", existing.get("longitude")),
        "price_range_text": payload.get("price_range_text", existing.get("price_range_text")),
        "external_url": payload.get("external_url", existing.get("external_url")),
        "booking_url": payload.get("booking_url", existing.get("booking_url")),
        "contact_info": payload.get("contact_info", existing.get("contact_info")),
        "opening_hours": payload.get("opening_hours", existing.get("opening_hours")),
        "source_id": payload.get("source_id", existing.get("source_id")),
        "trust_tier": payload.get("trust_tier", existing.get("trust_tier")),
        "effective_from": payload.get("effective_from", existing.get("effective_from")),
        "effective_to": payload.get("effective_to", existing.get("effective_to")),
        "internal_notes": payload.get("internal_notes", existing.get("internal_notes")),
        "review_notes": payload.get("review_notes", existing.get("review_notes")),
    }
    if "country_code" in payload and payload["country_code"]:
        upd["country_code"] = str(payload["country_code"]).upper()
    supabase.table("country_resources").update(upd).eq("id", resource_id).execute()
    if "tag_ids" in payload:
        supabase.table("country_resource_tags").delete().eq("resource_id", resource_id).execute()
        for tid in (payload.get("tag_ids") or []):
            try:
                supabase.table("country_resource_tags").insert({"resource_id": resource_id, "tag_id": tid}).execute()
            except Exception:
                pass
    _log_audit("resource", resource_id, "update", user_id, prev_status, prev_status, "Content updated")
    return get_admin_resource_by_id(resource_id)


def submit_resource_for_review(resource_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    if not _can_transition(
        (get_admin_resource_by_id(resource_id) or {}).get("status"), "in_review"
    ):
        return None
    supabase = _get_supabase()
    supabase.table("country_resources").update({
        "status": "in_review",
        "updated_by_user_id": user_id,
    }).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "submit_for_review", user_id, "draft", "in_review", None)
    return get_admin_resource_by_id(resource_id)


def approve_resource(resource_id: str, user_id: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    r = get_admin_resource_by_id(resource_id)
    if not r or not _can_transition(r.get("status"), "approved"):
        return None
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    upd = {"status": "approved", "reviewed_by_user_id": user_id, "reviewed_at": now, "updated_by_user_id": user_id}
    if notes is not None:
        upd["review_notes"] = notes
    supabase.table("country_resources").update(upd).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "approve", user_id, r.get("status"), "approved", notes)
    return get_admin_resource_by_id(resource_id)


def publish_resource(resource_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    r = get_admin_resource_by_id(resource_id)
    if not r or not _can_transition(r.get("status"), "published"):
        return None
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("country_resources").update({
        "status": "published",
        "published_by_user_id": user_id,
        "published_at": now,
        "is_visible_to_end_users": True,
        "updated_by_user_id": user_id,
    }).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "publish", user_id, r.get("status"), "published", None)
    return get_admin_resource_by_id(resource_id)


def unpublish_resource(resource_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    r = get_admin_resource_by_id(resource_id)
    if not r or r.get("status") != "published":
        return None
    supabase = _get_supabase()
    supabase.table("country_resources").update({
        "is_visible_to_end_users": False,
        "updated_by_user_id": user_id,
    }).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "unpublish", user_id, "published", "published", "Visibility set to false")
    return get_admin_resource_by_id(resource_id)


def archive_resource(resource_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    r = get_admin_resource_by_id(resource_id)
    if not r:
        return None
    prev = r.get("status")
    if prev == "archived":
        return r
    if prev == "published" and not _can_transition(prev, "archived"):
        return None
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("country_resources").update({
        "status": "archived",
        "archived_at": now,
        "is_visible_to_end_users": False,
        "updated_by_user_id": user_id,
    }).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "archive", user_id, prev, "archived", None)
    return get_admin_resource_by_id(resource_id)


def restore_resource(resource_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    r = get_admin_resource_by_id(resource_id)
    if not r or r.get("status") != "archived":
        return None
    supabase = _get_supabase()
    supabase.table("country_resources").update({
        "status": "approved",
        "archived_at": None,
        "updated_by_user_id": user_id,
    }).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "restore", user_id, "archived", "approved", None)
    return get_admin_resource_by_id(resource_id)


def delete_resource(resource_id: str, user_id: str) -> bool:
    r = get_admin_resource_by_id(resource_id)
    if not r:
        return False
    supabase = _get_supabase()
    supabase.table("country_resources").update({"is_active": False, "updated_by_user_id": user_id}).eq("id", resource_id).execute()
    _log_audit("resource", resource_id, "delete", user_id, r.get("status"), None, "Soft delete")
    return True


# --- Events ---
def list_admin_events(
    country_code: Optional[str] = None,
    city: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    family_friendly: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    supabase = _get_supabase()
    q = supabase.table("rkg_country_events").select("*", count="exact")
    if country_code:
        q = q.eq("country_code", country_code.upper())
    if city:
        q = q.eq("city_name", city)
    if event_type:
        q = q.eq("event_type", event_type)
    if status:
        q = q.eq("status", status)
    if family_friendly is not None:
        q = q.eq("is_family_friendly", family_friendly)
    if date_from:
        q = q.gte("start_datetime", date_from)
    if date_to:
        q = q.lte("start_datetime", date_to)
    q = q.order("start_datetime", desc=False).range(offset, offset + limit - 1)
    r = q.execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_admin_event_by_id(event_id: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("rkg_country_events").select("*").eq("id", event_id).limit(1).execute()
    return (r.data or [None])[0]


def create_event(payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    supabase = _get_supabase()
    row = {
        "country_code": (payload.get("country_code") or "NO").upper(),
        "city_name": payload.get("city_name") or "",
        "title": payload.get("title", "").strip() or "Untitled Event",
        "description": payload.get("description"),
        "event_type": payload.get("event_type") or "cinema",
        "venue_name": payload.get("venue_name"),
        "address": payload.get("address"),
        "start_datetime": payload.get("start_datetime"),
        "end_datetime": payload.get("end_datetime"),
        "price_text": payload.get("price_text"),
        "currency": payload.get("currency"),
        "is_free": bool(payload.get("is_free", False)),
        "is_family_friendly": bool(payload.get("is_family_friendly", False)),
        "min_age": payload.get("min_age"),
        "max_age": payload.get("max_age"),
        "language_code": payload.get("language_code"),
        "external_url": payload.get("external_url"),
        "booking_url": payload.get("booking_url"),
        "source_id": payload.get("source_id"),
        "status": "draft",
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
        "internal_notes": payload.get("internal_notes"),
        "review_notes": payload.get("review_notes"),
        "is_visible_to_end_users": False,
    }
    r = supabase.table("rkg_country_events").insert(row).execute()
    created = (r.data or [{}])[0]
    eid = created.get("id")
    if eid:
        _log_audit("event", str(eid), "create", user_id, None, "draft", f"Created: {created.get('title', '')}")
    return created


def update_event(event_id: str, payload: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    existing = get_admin_event_by_id(event_id)
    if not existing:
        return None
    supabase = _get_supabase()
    upd = {k: payload.get(k, existing.get(k)) for k in (
        "country_code", "city_name", "title", "description", "event_type",
        "venue_name", "address", "start_datetime", "end_datetime",
        "price_text", "currency", "is_free", "is_family_friendly",
        "min_age", "max_age", "language_code", "external_url", "booking_url",
        "source_id", "internal_notes", "review_notes",
    )}
    if upd.get("country_code"):
        upd["country_code"] = str(upd["country_code"]).upper()
    upd["updated_by_user_id"] = user_id
    supabase.table("rkg_country_events").update(upd).eq("id", event_id).execute()
    _log_audit("event", event_id, "update", user_id, existing.get("status"), existing.get("status"), "Content updated")
    return get_admin_event_by_id(event_id)


def publish_event(event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    e = get_admin_event_by_id(event_id)
    if not e or not _can_transition(e.get("status"), "published"):
        return None
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("rkg_country_events").update({
        "status": "published",
        "published_by_user_id": user_id,
        "published_at": now,
        "is_visible_to_end_users": True,
        "updated_by_user_id": user_id,
    }).eq("id", event_id).execute()
    _log_audit("event", event_id, "publish", user_id, e.get("status"), "published", None)
    return get_admin_event_by_id(event_id)


def submit_event_for_review(event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    e = get_admin_event_by_id(event_id)
    if not e or not _can_transition(e.get("status"), "in_review"):
        return None
    supabase = _get_supabase()
    supabase.table("rkg_country_events").update({
        "status": "in_review",
        "updated_by_user_id": user_id,
    }).eq("id", event_id).execute()
    _log_audit("event", event_id, "submit_for_review", user_id, e.get("status"), "in_review", None)
    return get_admin_event_by_id(event_id)


def approve_event(event_id: str, user_id: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    e = get_admin_event_by_id(event_id)
    if not e or not _can_transition(e.get("status"), "approved"):
        return None
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    upd = {"status": "approved", "reviewed_by_user_id": user_id, "reviewed_at": now, "updated_by_user_id": user_id}
    if notes is not None:
        upd["review_notes"] = notes
    supabase.table("rkg_country_events").update(upd).eq("id", event_id).execute()
    _log_audit("event", event_id, "approve", user_id, e.get("status"), "approved", notes)
    return get_admin_event_by_id(event_id)


def archive_event(event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    e = get_admin_event_by_id(event_id)
    if not e:
        return None
    prev = e.get("status")
    if prev == "archived":
        return e
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("rkg_country_events").update({
        "status": "archived",
        "archived_at": now,
        "is_visible_to_end_users": False,
        "updated_by_user_id": user_id,
    }).eq("id", event_id).execute()
    _log_audit("event", event_id, "archive", user_id, prev, "archived", None)
    return get_admin_event_by_id(event_id)


def unpublish_event(event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    e = get_admin_event_by_id(event_id)
    if not e or e.get("status") != "published":
        return None
    supabase = _get_supabase()
    supabase.table("rkg_country_events").update({
        "is_visible_to_end_users": False,
        "updated_by_user_id": user_id,
    }).eq("id", event_id).execute()
    _log_audit("event", event_id, "unpublish", user_id, "published", "published", "Visibility set to false")
    return get_admin_event_by_id(event_id)


def restore_event(event_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    e = get_admin_event_by_id(event_id)
    if not e or e.get("status") != "archived":
        return None
    supabase = _get_supabase()
    supabase.table("rkg_country_events").update({
        "status": "approved",
        "archived_at": None,
        "updated_by_user_id": user_id,
    }).eq("id", event_id).execute()
    _log_audit("event", event_id, "restore", user_id, "archived", "approved", None)
    return get_admin_event_by_id(event_id)


# --- Taxonomy ---
def list_resource_categories() -> List[Dict[str, Any]]:
    r = _get_supabase().table("resource_categories").select("*").eq("is_active", True).order("sort_order").execute()
    return r.data or []


def create_resource_category(payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    row = {
        "key": (payload.get("key") or "").strip() or "uncategorized",
        "label": (payload.get("label") or "").strip() or "Uncategorized",
        "description": payload.get("description"),
        "icon_name": payload.get("icon_name"),
        "sort_order": int(payload.get("sort_order", 0)),
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }
    r = _get_supabase().table("resource_categories").insert(row).execute()
    return (r.data or [{}])[0]


def deactivate_resource_category(category_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("resource_categories").update({
        "is_active": False,
        "updated_by_user_id": user_id,
    }).eq("id", category_id).execute()
    return (r.data or [None])[0]


def update_resource_category(category_id: str, payload: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    upd = {"updated_by_user_id": user_id}
    for k in ("key", "label", "description", "icon_name", "sort_order"):
        if k in payload and payload[k] is not None:
            upd[k] = payload[k]
    if len(upd) <= 1:
        r = _get_supabase().table("resource_categories").select("*").eq("id", category_id).limit(1).execute()
        return (r.data or [None])[0]
    r = _get_supabase().table("resource_categories").update(upd).eq("id", category_id).execute()
    return (r.data or [None])[0]


def list_resource_tags(tag_group: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _get_supabase().table("resource_tags").select("*")
    if tag_group:
        q = q.eq("tag_group", tag_group)
    r = q.order("key").execute()
    return r.data or []


def create_resource_tag(payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    row = {
        "key": (payload.get("key") or "").strip().lower().replace(" ", "_") or "tag",
        "label": (payload.get("label") or "").strip() or "Tag",
        "tag_group": payload.get("tag_group"),
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }
    r = _get_supabase().table("resource_tags").insert(row).execute()
    return (r.data or [{}])[0]


def update_resource_tag(tag_id: str, payload: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    upd = {"updated_by_user_id": user_id}
    for k in ("key", "label", "tag_group"):
        if k in payload and payload[k] is not None:
            upd[k] = payload[k]
    if len(upd) <= 1:
        r = _get_supabase().table("resource_tags").select("*").eq("id", tag_id).limit(1).execute()
        return (r.data or [None])[0]
    r = _get_supabase().table("resource_tags").update(upd).eq("id", tag_id).execute()
    return (r.data or [None])[0]


def list_resource_sources() -> List[Dict[str, Any]]:
    r = _get_supabase().table("resource_sources").select("*").order("source_name").execute()
    return r.data or []


def create_resource_source(payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    row = {
        "source_name": (payload.get("source_name") or "").strip() or "Unknown",
        "publisher": payload.get("publisher"),
        "source_type": payload.get("source_type") or "community",
        "url": payload.get("url"),
        "retrieved_at": payload.get("retrieved_at"),
        "content_hash": payload.get("content_hash"),
        "notes": payload.get("notes"),
        "trust_tier": payload.get("trust_tier") or "T2",
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }
    r = _get_supabase().table("resource_sources").insert(row).execute()
    return (r.data or [{}])[0]


def update_resource_source(source_id: str, payload: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    upd = {"updated_by_user_id": user_id}
    for k in ("source_name", "publisher", "source_type", "url", "retrieved_at", "notes", "trust_tier"):
        if k in payload and payload[k] is not None:
            upd[k] = payload[k]
    if len(upd) <= 1:
        r = _get_supabase().table("resource_sources").select("*").eq("id", source_id).limit(1).execute()
        return (r.data or [None])[0]
    r = _get_supabase().table("resource_sources").update(upd).eq("id", source_id).execute()
    return (r.data or [None])[0]


def get_resource_audit_log(entity_type: str, entity_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    r = _get_supabase().table("resource_audit_log").select("*").eq("entity_type", entity_type).eq("entity_id", entity_id).order("created_at", desc=True).limit(limit).execute()
    return r.data or []


def get_resource_audit_log_global(
    entity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Global audit log. Optional entity_type filter."""
    q = _get_supabase().table("resource_audit_log").select("*", count="exact")
    if entity_type:
        q = q.eq("entity_type", entity_type)
    r = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_admin_dashboard_counts() -> Dict[str, int]:
    """Return counts for draft, in_review, published, archived (admin dashboard)."""
    supabase = _get_supabase()
    counts = {}
    for status in ("draft", "in_review", "published", "archived"):
        try:
            r = supabase.table("country_resources").select("id", count="exact", head=True).eq("is_active", True).eq("status", status).execute()
            counts[f"resources_{status}"] = r.count or 0
        except Exception:
            counts[f"resources_{status}"] = 0
    for status in ("draft", "in_review", "published", "archived"):
        try:
            r = supabase.table("rkg_country_events").select("id", count="exact", head=True).eq("status", status).execute()
            counts[f"events_{status}"] = r.count or 0
        except Exception:
            counts[f"events_{status}"] = 0
    return counts
