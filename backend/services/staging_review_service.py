"""
Staging review service - Admin-only.
List, inspect, approve, merge, reject staged resource/event candidates.
No auto-publish; creates draft/approved non-public records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .supabase_client import get_supabase_admin_client
from .admin_resources import create_resource, create_event, update_resource, update_event


def _get_supabase():
    return get_supabase_admin_client()


_STAGING_STATUSES = frozenset({
    "new", "needs_review", "approved_new", "approved_merged",
    "rejected", "duplicate", "ignored", "error",
    "approved_for_import", "deduped",  # legacy
})


def _log_staging_audit(
    entity_type: str,
    entity_id: str,
    action_type: str,
    user_id: str,
    target_live_id: Optional[str] = None,
    merge_mode: Optional[str] = None,
    review_reason: Optional[str] = None,
    change_summary: Optional[str] = None,
) -> None:
    try:
        _get_supabase().table("staging_review_audit_log").insert({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action_type": action_type,
            "performed_by_user_id": user_id,
            "target_live_id": target_live_id,
            "merge_mode": merge_mode,
            "review_reason": review_reason,
            "change_summary": change_summary,
        }).execute()
    except Exception:
        pass


def _load_category_map() -> Dict[str, str]:
    r = _get_supabase().table("resource_categories").select("id, key").execute()
    return {row["key"]: row["id"] for row in (r.data or [])}


def _load_source_map() -> Tuple[Dict[str, str], Dict[str, str]]:
    r = _get_supabase().table("resource_sources").select("id, source_name, url").execute()
    by_name, by_url = {}, {}
    for row in (r.data or []):
        by_name[row["source_name"]] = row["id"]
        if row.get("url"):
            by_url[row["url"]] = row["id"]
    return by_name, by_url


def _resolve_source_id(source_name: Optional[str], source_url: Optional[str]) -> Optional[str]:
    by_name, by_url = _load_source_map()
    if source_url and source_url in by_url:
        return by_url[source_url]
    if source_name and source_name in by_name:
        return by_name[source_name]
    return None


def _normalize_title(s: str) -> str:
    return " ".join((s or "").lower().split())[:200]


# --- Dashboard / counts ---
def get_staging_dashboard_counts() -> Dict[str, Any]:
    supabase = _get_supabase()
    r_res = supabase.table("staged_resource_candidates").select("status", count="exact").execute()
    r_ev = supabase.table("staged_event_candidates").select("status", count="exact").execute()

    def _counts(data: List[Dict]) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for row in (data or []):
            s = row.get("status", "new")
            c[s] = c.get(s, 0) + 1
        return c

    res_counts = _counts(r_res.data or [])
    ev_counts = _counts(r_ev.data or [])

    new_res = res_counts.get("new", 0) + res_counts.get("needs_review", 0)
    new_ev = ev_counts.get("new", 0) + ev_counts.get("needs_review", 0)

    runs = supabase.table("crawl_runs").select(
        "id, started_at, status, documents_fetched, resources_staged, events_staged"
    ).order("started_at", desc=True).limit(5).execute()

    return {
        "resource_candidates_new": new_res,
        "resource_candidates_by_status": res_counts,
        "event_candidates_new": new_ev,
        "event_candidates_by_status": ev_counts,
        "recent_crawl_runs": runs.data or [],
    }


# --- Resource candidates ---
def list_staged_resource_candidates(
    status: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    category_key: Optional[str] = None,
    resource_type: Optional[str] = None,
    trust_tier: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    supabase = _get_supabase()
    q = supabase.table("staged_resource_candidates").select("*", count="exact")
    if status:
        q = q.eq("status", status)
    if country_code:
        q = q.eq("country_code", country_code.upper())
    if city_name:
        q = q.eq("city_name", city_name)
    if category_key:
        q = q.eq("category_key", category_key)
    if resource_type:
        q = q.eq("resource_type", resource_type)
    if trust_tier:
        q = q.eq("trust_tier", trust_tier)
    if search:
        q = q.ilike("title", f"%{search}%")
    q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
    r = q.execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_staged_resource_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("staged_resource_candidates").select("*").eq("id", candidate_id).limit(1).execute()
    return (r.data or [None])[0]


def get_resource_candidate_matches(candidate_id: str) -> List[Dict[str, Any]]:
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        return []
    supabase = _get_supabase()
    norm_title = _normalize_title(c.get("title", ""))
    country = (c.get("country_code") or "").upper()
    city = c.get("city_name") or ""
    cat_key = c.get("category_key")

    cat_map = _load_category_map()
    cat_id = cat_map.get(cat_key) if cat_key else None

    q = supabase.table("country_resources").select("id, title, country_code, city_name, category_id, status, summary").eq("country_code", country).eq("city_name", city).eq("is_active", True).limit(20)
    if cat_id:
        q = q.eq("category_id", cat_id)
    r = q.execute()

    matches = []
    for row in (r.data or []):
        sim = 0.0
        reasons = []
        if _normalize_title(row.get("title", "")) == norm_title:
            sim = 1.0
            reasons.append("Exact title match")
        elif norm_title and _normalize_title(row.get("title", "")).startswith(norm_title[:30]):
            sim = 0.8
            reasons.append("Similar title")
        else:
            sim = 0.5
            reasons.append("Same country/city/category")
        matches.append({
            "id": row["id"],
            "title": row.get("title"),
            "country_code": row.get("country_code"),
            "city_name": row.get("city_name"),
            "status": row.get("status"),
            "summary": (row.get("summary") or "")[:200],
            "similarity_score": sim,
            "match_reasons": reasons,
        })
    matches.sort(key=lambda x: -x["similarity_score"])
    return matches[:10]


def approve_resource_candidate_as_new(candidate_id: str, user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    if c.get("status") in ("approved_new", "approved_merged"):
        return {"error": "Already approved", "promoted_live_resource_id": c.get("promoted_live_resource_id")}

    cat_map = _load_category_map()
    cat_key = c.get("category_key") or "admin_essentials"
    category_id = cat_map.get(cat_key)
    if not category_id:
        return {"error": f"Category '{cat_key}' not found"}

    source_id = _resolve_source_id(c.get("source_name"), c.get("source_url"))

    payload = {
        "country_code": (c.get("country_code") or "NO").upper(),
        "country_name": c.get("country_name"),
        "city_name": c.get("city_name") or "",
        "category_id": category_id,
        "title": (c.get("title") or "").strip() or "Untitled",
        "summary": c.get("summary") or "",
        "body": c.get("body"),
        "content_json": c.get("content_json") or {},
        "resource_type": c.get("resource_type") or "guide",
        "audience_type": c.get("audience_type") or "all",
        "external_url": c.get("source_url"),
        "source_id": source_id,
        "trust_tier": c.get("trust_tier"),
    }
    tags = c.get("tags") or []
    if isinstance(tags, list):
        tag_r = _get_supabase().table("resource_tags").select("id, key").execute()
        tag_map = {r["key"]: r["id"] for r in (tag_r.data or [])}
        payload["tag_ids"] = [tag_map[k] for k in tags if isinstance(k, str) and k in tag_map]
    else:
        payload["tag_ids"] = []

    created = create_resource(payload, user_id)
    live_id = created.get("id")

    _get_supabase().table("staged_resource_candidates").update({
        "status": "approved_new",
        "review_reason": reason,
        "promoted_live_resource_id": live_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()

    _log_staging_audit(
        "staged_resource",
        candidate_id,
        "approve_new",
        user_id,
        target_live_id=live_id,
        review_reason=reason,
        change_summary=f"Created live resource {live_id}",
    )
    return {"success": True, "live_resource_id": live_id}


def merge_resource_candidate_into_live(
    candidate_id: str,
    target_resource_id: str,
    user_id: str,
    merge_mode: str = "overwrite_selected_fields",
    fields_to_merge: Optional[List[str]] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    from .admin_resources import get_admin_resource_by_id
    target = get_admin_resource_by_id(target_resource_id)
    if not target:
        return {"error": "Target resource not found"}

    # Map live field names to staged candidate field names
    live_to_staged = {
        "summary": "summary",
        "body": "body",
        "content_json": "content_json",
        "title": "title",
        "external_url": "source_url",
    }
    fields = fields_to_merge or ["summary", "body", "external_url", "content_json"]
    payload = {}
    for live_field in fields:
        staged_key = live_to_staged.get(live_field, live_field)
        val = c.get(staged_key)
        if val is not None:
            payload[live_field] = val

    if not payload:
        return {"error": "No fields to merge"}

    update_resource(target_resource_id, payload, user_id)

    _get_supabase().table("staged_resource_candidates").update({
        "status": "approved_merged",
        "review_reason": reason,
        "promoted_live_resource_id": target_resource_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()

    _log_staging_audit(
        "staged_resource",
        candidate_id,
        "merge",
        user_id,
        target_live_id=target_resource_id,
        merge_mode=merge_mode,
        review_reason=reason,
        change_summary=f"Merged into {target_resource_id}",
    )
    return {"success": True, "target_resource_id": target_resource_id}


def reject_resource_candidate(candidate_id: str, user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    _get_supabase().table("staged_resource_candidates").update({
        "status": "rejected",
        "review_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit("staged_resource", candidate_id, "reject", user_id, review_reason=reason)
    return {"success": True}


def mark_resource_candidate_duplicate(
    candidate_id: str,
    user_id: str,
    duplicate_of_candidate_id: Optional[str] = None,
    duplicate_of_live_resource_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    if not duplicate_of_candidate_id and not duplicate_of_live_resource_id:
        return {"error": "Must specify duplicate_of_candidate_id or duplicate_of_live_resource_id"}
    _get_supabase().table("staged_resource_candidates").update({
        "status": "duplicate",
        "duplicate_of_candidate_id": duplicate_of_candidate_id,
        "duplicate_of_live_resource_id": duplicate_of_live_resource_id,
        "review_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit(
        "staged_resource",
        candidate_id,
        "mark_duplicate",
        user_id,
        target_live_id=duplicate_of_live_resource_id,
        review_reason=reason,
    )
    return {"success": True}


def ignore_resource_candidate(candidate_id: str, user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    _get_supabase().table("staged_resource_candidates").update({
        "status": "ignored",
        "review_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit("staged_resource", candidate_id, "ignore", user_id, review_reason=reason)
    return {"success": True}


def restore_resource_candidate_to_review(candidate_id: str, user_id: str) -> Dict[str, Any]:
    c = get_staged_resource_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    if c.get("status") in ("approved_new", "approved_merged"):
        return {"error": "Cannot restore approved candidate"}
    _get_supabase().table("staged_resource_candidates").update({
        "status": "needs_review",
        "review_reason": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit("staged_resource", candidate_id, "restore_review", user_id)
    return {"success": True}


# --- Event candidates ---
def list_staged_event_candidates(
    status: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    event_type: Optional[str] = None,
    trust_tier: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    supabase = _get_supabase()
    q = supabase.table("staged_event_candidates").select("*", count="exact")
    if status:
        q = q.eq("status", status)
    if country_code:
        q = q.eq("country_code", country_code.upper())
    if city_name:
        q = q.eq("city_name", city_name)
    if event_type:
        q = q.eq("event_type", event_type)
    if trust_tier:
        q = q.eq("trust_tier", trust_tier)
    if search:
        q = q.ilike("title", f"%{search}%")
    q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
    r = q.execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_staged_event_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("staged_event_candidates").select("*").eq("id", candidate_id).limit(1).execute()
    return (r.data or [None])[0]


def get_event_candidate_matches(candidate_id: str) -> List[Dict[str, Any]]:
    c = get_staged_event_candidate(candidate_id)
    if not c:
        return []
    supabase = _get_supabase()
    norm_title = _normalize_title(c.get("title", ""))
    country = (c.get("country_code") or "").upper()
    city = c.get("city_name") or ""
    start = c.get("start_datetime")

    q = supabase.table("rkg_country_events").select("id, title, country_code, city_name, start_datetime, status").eq("country_code", country).eq("city_name", city).limit(20)
    r = q.execute()

    matches = []
    for row in (r.data or []):
        sim = 0.5
        reasons = ["Same country/city"]
        if _normalize_title(row.get("title", "")) == norm_title:
            sim = 1.0
            reasons.append("Exact title match")
        if start and row.get("start_datetime"):
            if str(row["start_datetime"])[:19] == str(start)[:19]:
                sim = min(1.0, sim + 0.3)
                reasons.append("Same start datetime")
        matches.append({
            "id": row["id"],
            "title": row.get("title"),
            "city_name": row.get("city_name"),
            "start_datetime": row.get("start_datetime"),
            "status": row.get("status"),
            "similarity_score": sim,
            "match_reasons": reasons,
        })
    matches.sort(key=lambda x: -x["similarity_score"])
    return matches[:10]


def approve_event_candidate_as_new(candidate_id: str, user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    c = get_staged_event_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    if c.get("status") in ("approved_new", "approved_merged"):
        return {"error": "Already approved", "promoted_live_event_id": c.get("promoted_live_event_id")}

    source_id = _resolve_source_id(c.get("source_name"), c.get("source_url"))

    payload = {
        "country_code": (c.get("country_code") or "NO").upper(),
        "city_name": c.get("city_name") or "",
        "title": (c.get("title") or "").strip() or "Untitled Event",
        "description": c.get("description"),
        "event_type": c.get("event_type") or "community_event",
        "venue_name": c.get("venue_name"),
        "address": c.get("address"),
        "start_datetime": c.get("start_datetime"),
        "end_datetime": c.get("end_datetime"),
        "price_text": c.get("price_text"),
        "currency": c.get("currency"),
        "is_free": bool(c.get("is_free", False)),
        "is_family_friendly": bool(c.get("is_family_friendly", False)),
        "min_age": c.get("min_age"),
        "max_age": c.get("max_age"),
        "language_code": c.get("language_code"),
        "external_url": c.get("source_url"),
        "source_id": source_id,
    }
    created = create_event(payload, user_id)
    live_id = created.get("id")

    _get_supabase().table("staged_event_candidates").update({
        "status": "approved_new",
        "review_reason": reason,
        "promoted_live_event_id": live_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()

    _log_staging_audit(
        "staged_event",
        candidate_id,
        "approve_new",
        user_id,
        target_live_id=live_id,
        review_reason=reason,
        change_summary=f"Created live event {live_id}",
    )
    return {"success": True, "live_event_id": live_id}


def merge_event_candidate_into_live(
    candidate_id: str,
    target_event_id: str,
    user_id: str,
    merge_mode: str = "overwrite_selected_fields",
    fields_to_merge: Optional[List[str]] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    c = get_staged_event_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    from .admin_resources import get_admin_event_by_id
    target = get_admin_event_by_id(target_event_id)
    if not target:
        return {"error": "Target event not found"}

    live_to_staged = {"external_url": "source_url"}
    fields = fields_to_merge or ["description", "venue_name", "address", "external_url"]
    payload = {}
    for live_field in fields:
        staged_key = live_to_staged.get(live_field, live_field)
        val = c.get(staged_key)
        if val is not None:
            payload[live_field] = val

    if not payload:
        return {"error": "No fields to merge"}

    update_event(target_event_id, payload, user_id)

    _get_supabase().table("staged_event_candidates").update({
        "status": "approved_merged",
        "review_reason": reason,
        "promoted_live_event_id": target_event_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()

    _log_staging_audit(
        "staged_event",
        candidate_id,
        "merge",
        user_id,
        target_live_id=target_event_id,
        merge_mode=merge_mode,
        review_reason=reason,
        change_summary=f"Merged into {target_event_id}",
    )
    return {"success": True, "target_event_id": target_event_id}


def reject_event_candidate(candidate_id: str, user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    c = get_staged_event_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    _get_supabase().table("staged_event_candidates").update({
        "status": "rejected",
        "review_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit("staged_event", candidate_id, "reject", user_id, review_reason=reason)
    return {"success": True}


def mark_event_candidate_duplicate(
    candidate_id: str,
    user_id: str,
    duplicate_of_candidate_id: Optional[str] = None,
    duplicate_of_live_event_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    if not duplicate_of_candidate_id and not duplicate_of_live_event_id:
        return {"error": "Must specify duplicate_of_candidate_id or duplicate_of_live_event_id"}
    _get_supabase().table("staged_event_candidates").update({
        "status": "duplicate",
        "duplicate_of_candidate_id": duplicate_of_candidate_id,
        "duplicate_of_live_event_id": duplicate_of_live_event_id,
        "review_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit(
        "staged_event",
        candidate_id,
        "mark_duplicate",
        user_id,
        target_live_id=duplicate_of_live_event_id,
        review_reason=reason,
    )
    return {"success": True}


def ignore_event_candidate(candidate_id: str, user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    c = get_staged_event_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    _get_supabase().table("staged_event_candidates").update({
        "status": "ignored",
        "review_reason": reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit("staged_event", candidate_id, "ignore", user_id, review_reason=reason)
    return {"success": True}


def restore_event_candidate_to_review(candidate_id: str, user_id: str) -> Dict[str, Any]:
    c = get_staged_event_candidate(candidate_id)
    if not c:
        return {"error": "Candidate not found"}
    if c.get("status") in ("approved_new", "approved_merged"):
        return {"error": "Cannot restore approved candidate"}
    _get_supabase().table("staged_event_candidates").update({
        "status": "needs_review",
        "review_reason": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", candidate_id).execute()
    _log_staging_audit("staged_event", candidate_id, "restore_review", user_id)
    return {"success": True}
