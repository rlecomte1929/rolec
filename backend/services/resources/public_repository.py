"""
Public repository: queries ONLY published_country_resources and published_country_events.
Never reads from base tables. Used for HR/Employee/Admin read-only consumption.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _get_supabase():
    from ...supabase_client import get_supabase_admin_client
    return get_supabase_admin_client()


# --- Published resources (view) ---
def find_published_resources(
    country_code: str,
    city: Optional[str] = None,
    category_key: Optional[str] = None,
    category_id: Optional[str] = None,
    audience_type: Optional[str] = None,
    child_age_min: Optional[int] = None,
    child_age_max: Optional[int] = None,
    budget_tier: Optional[str] = None,
    language: Optional[str] = None,
    tags: Optional[List[str]] = None,
    family_friendly: Optional[bool] = None,
    featured: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Query published_country_resources view. No governance fields exposed."""
    try:
        supabase = _get_supabase()
        q = (
            supabase.table("published_country_resources")
            .select("*")
            .eq("country_code", country_code.upper())
        )
        r = q.execute()
        rows = r.data or []
        if city:
            rows = [
                r for r in rows
                if (r.get("city_name") or "").lower() == city.lower() or not r.get("city_name")
            ]

        if category_id:
            rows = [r for r in rows if r.get("category_id") == category_id]
        elif category_key:
            cat_q = supabase.table("resource_categories").select("id").eq("key", category_key).eq("is_active", True).limit(1).execute()
            if cat_q.data:
                cid = cat_q.data[0]["id"]
                rows = [r for r in rows if r.get("category_id") == cid]

        if audience_type:
            rows = [r for r in rows if r.get("audience_type") in (audience_type, "all")]
        if budget_tier:
            rows = [r for r in rows if r.get("budget_tier") == budget_tier]
        if language:
            rows = [r for r in rows if (r.get("language_code") or "").lower() == language.lower() or not r.get("language_code")]
        if family_friendly is True:
            rows = [r for r in rows if r.get("is_family_friendly")]
        if featured is True:
            rows = [r for r in rows if r.get("is_featured")]
        if child_age_min is not None:
            rows = [r for r in rows if r.get("max_child_age") is None or (r.get("max_child_age") or 0) >= child_age_min]
        if child_age_max is not None:
            rows = [r for r in rows if r.get("min_child_age") is None or (r.get("min_child_age") or 99) <= child_age_max]
        if search:
            s = search.lower()
            rows = [r for r in rows if s in (r.get("title") or "").lower() or s in (r.get("summary") or "").lower()]
        if tags:
            tag_ids_q = supabase.table("resource_tags").select("id").in_("key", tags).execute()
            tag_ids = [t["id"] for t in (tag_ids_q.data or [])]
            if tag_ids:
                rt_q = supabase.table("country_resource_tags").select("resource_id").in_("tag_id", tag_ids).execute()
                keep_ids = {x["resource_id"] for x in (rt_q.data or [])}
                rows = [r for r in rows if r.get("id") in keep_ids]

        offset = (page - 1) * limit
        return rows[offset : offset + limit]
    except Exception:
        return []


def find_published_resources_by_ids(ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch published resources by id list."""
    if not ids:
        return []
    try:
        supabase = _get_supabase()
        r = supabase.table("published_country_resources").select("*").in_("id", ids).execute()
        return r.data or []
    except Exception:
        return []


# --- Published events (view) ---
def find_published_events(
    country_code: str,
    city: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    is_free: Optional[bool] = None,
    family_friendly: Optional[bool] = None,
    language: Optional[str] = None,
    tags: Optional[List[str]] = None,
    weekend_only: bool = False,
    upcoming_only: bool = True,
    page: int = 1,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Query published_country_events view."""
    try:
        supabase = _get_supabase()
        now = datetime.now(timezone.utc)
        from_ts = date_from or now
        to_ts = date_to or (now + timedelta(days=90))
        q = (
            supabase.table("published_country_events")
            .select("*")
            .eq("country_code", country_code.upper())
            .gte("start_datetime", from_ts.isoformat())
            .lte("start_datetime", to_ts.isoformat())
            .order("start_datetime", desc=False)
        )
        if city:
            q = q.eq("city_name", city)
        if event_type:
            q = q.eq("event_type", event_type)
        if is_free is True:
            q = q.eq("is_free", True)
        if family_friendly is True:
            q = q.eq("is_family_friendly", True)
        r = q.execute()
        rows = r.data or []

        if language:
            rows = [e for e in rows if (e.get("language_code") or "").lower() == language.lower() or not e.get("language_code")]
        if tags:
            tag_ids_q = supabase.table("resource_tags").select("id").in_("key", tags).execute()
            tag_ids = [t["id"] for t in (tag_ids_q.data or [])]
            if tag_ids:
                et_q = supabase.table("country_event_tags").select("event_id").in_("tag_id", tag_ids).execute()
                keep_ids = {x["event_id"] for x in (et_q.data or [])}
                rows = [e for e in rows if e.get("id") in keep_ids]
        if weekend_only:
            rows = [e for e in rows if _is_weekend(e.get("start_datetime"))]
        if upcoming_only:
            rows = [e for e in rows if e.get("start_datetime") >= now.isoformat()]

        offset = (page - 1) * limit
        return rows[offset : offset + limit]
    except Exception:
        return []


def _is_weekend(dt_str: Optional[str]) -> bool:
    if not dt_str:
        return False
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.weekday() >= 5  # Sat=5, Sun=6
    except Exception:
        return False


# --- Safe taxonomy (categories/tags) ---
def find_active_categories() -> List[Dict[str, Any]]:
    """Active categories for public display."""
    try:
        r = _get_supabase().table("resource_categories").select("id", "key", "label", "description", "icon_name", "sort_order").eq("is_active", True).order("sort_order").execute()
        return r.data or []
    except Exception:
        return []


def find_tags(tag_group: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        q = _get_supabase().table("resource_tags").select("id", "key", "label", "tag_group")
        if tag_group:
            q = q.eq("tag_group", tag_group)
        r = q.order("key").execute()
        return r.data or []
    except Exception:
        return []
