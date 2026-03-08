"""
Review Queue Service: prioritization, generation, assignment, status management.
Admin-only. Integrates staged candidates, change events, stale live content.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

# Valid status transitions
_STATUS_TRANSITIONS: Dict[str, List[str]] = {
    "new": ["triaged", "assigned", "rejected", "deferred"],
    "triaged": ["assigned", "rejected", "deferred"],
    "assigned": ["in_progress", "rejected", "deferred"],
    "in_progress": ["blocked", "waiting", "resolved", "rejected", "deferred"],
    "blocked": ["in_progress", "deferred"],
    "waiting": ["in_progress", "resolved", "deferred"],
    "resolved": ["reopened"],  # we use reopen as status -> new/triaged
    "rejected": ["reopened"],
    "deferred": ["new", "triaged", "assigned"],
}

_OPEN_STATUSES = {"new", "triaged", "assigned", "in_progress", "blocked", "waiting"}

_PRIORITY_BANDS = ("critical", "high", "medium", "low")


def _get_supabase():
    return get_supabase_admin_client()


def _score_trust_tier(tier: Optional[str]) -> int:
    """T0=40, T1=30, T2=20, T3=10."""
    if not tier:
        return 15
    t = (tier or "").upper()
    if t == "T0":
        return 40
    if t == "T1":
        return 30
    if t == "T2":
        return 20
    if t == "T3":
        return 10
    return 15


def _score_content_domain(domain: Optional[str]) -> int:
    """Admin essentials, healthcare, schools higher."""
    high = {"admin_essentials", "healthcare", "schools_childcare", "safety"}
    mid = {"housing", "transport", "daily_life", "community"}
    d = (domain or "").lower()
    if d in high:
        return 25
    if d in mid:
        return 15
    return 5


def compute_priority_score(
    queue_item_type: str,
    trust_tier: Optional[str] = None,
    content_domain: Optional[str] = None,
    change_score: Optional[float] = None,
    is_stale_live: bool = False,
    is_overdue: bool = False,
    event_start_soon_days: Optional[int] = None,
    age_in_queue_hours: Optional[float] = None,
    sla_breach: bool = False,
) -> tuple[int, str, List[str]]:
    """
    Returns (score, priority_band, reasons).
    Score 0-100. Band: critical, high, medium, low.
    """
    score = 0
    reasons: List[str] = []

    # Type base
    if queue_item_type == "stale_live_resource_review":
        score += 35
        reasons.append("Published live content may be stale")
    elif queue_item_type == "stale_live_event_review":
        score += 30
        reasons.append("Live event may be outdated or expired")
    elif queue_item_type == "source_change_review":
        score += 25
        reasons.append("Official source changed")
    elif queue_item_type == "staged_resource_candidate":
        score += 15
        reasons.append("New staged resource candidate")
    elif queue_item_type == "staged_event_candidate":
        score += 12
        reasons.append("New staged event candidate")
    elif queue_item_type == "crawl_failure_review":
        score += 30
        reasons.append("Crawl failure requires attention")
    elif queue_item_type == "duplicate_resolution":
        score += 10
        reasons.append("Duplicate resolution needed")
    elif queue_item_type == "coverage_gap_review":
        score += 20
        reasons.append("Coverage gap in destination")
    else:
        score += 10

    # Trust tier
    tt_score = _score_trust_tier(trust_tier)
    score += min(tt_score // 2, 20)
    if trust_tier in ("T0", "T1"):
        reasons.append(f"High-trust source ({trust_tier})")

    # Content domain
    cd_score = _score_content_domain(content_domain)
    score += min(cd_score, 15)
    if content_domain in ("admin_essentials", "healthcare", "schools_childcare"):
        reasons.append("Family-critical or admin-essential content")

    # Change significance
    if change_score is not None and change_score >= 0.7:
        score += 15
        reasons.append("Significant content change detected")

    # Stale live
    if is_stale_live:
        score += 10
        reasons.append("Live content flagged as stale")

    # Overdue
    if is_overdue:
        score += 15
        reasons.append("Item overdue for review")

    # Event soon
    if event_start_soon_days is not None and event_start_soon_days <= 2:
        score += 20
        reasons.append(f"Event starts within {event_start_soon_days} days")

    # Aging
    if age_in_queue_hours is not None:
        if age_in_queue_hours >= 72:
            score += 15
            reasons.append("Item aged 3+ days in queue")
        elif age_in_queue_hours >= 24:
            score += 8
            reasons.append("Item aged 1+ day in queue")

    # SLA breach
    if sla_breach:
        score += 25
        reasons.append("SLA breach")

    score = min(100, score)

    if score >= 75:
        band = "critical"
    elif score >= 55:
        band = "high"
    elif score >= 30:
        band = "medium"
    else:
        band = "low"

    return score, band, reasons[:5]


def _ensure_table():
    """Ensure review_queue_items exists (for SQLite/local dev without migration)."""
    pass  # Rely on migration


def create_queue_item_from_staged_resource(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create queue item from staged resource candidate. De-duplicates."""
    supabase = _get_supabase()
    cid = candidate.get("id")
    if not cid:
        return None

    # Check existing open item
    existing = (
        supabase.table("review_queue_items")
        .select("id")
        .eq("related_staged_resource_candidate_id", cid)
        .in_("status", list(_OPEN_STATUSES))
        .limit(1)
        .execute()
    ).data
    if existing:
        return None

    score, band, reasons = compute_priority_score(
        queue_item_type="staged_resource_candidate",
        trust_tier=candidate.get("trust_tier"),
        content_domain=candidate.get("category_key"),
    )

    row = {
        "queue_item_type": "staged_resource_candidate",
        "status": "new",
        "priority_score": score,
        "priority_band": band,
        "country_code": candidate.get("country_code"),
        "city_name": candidate.get("city_name"),
        "content_domain": candidate.get("category_key"),
        "trust_tier": candidate.get("trust_tier"),
        "title": (candidate.get("title") or "Staged resource")[:500],
        "summary": (candidate.get("summary") or "")[:1000],
        "source_name": candidate.get("source_name"),
        "source_url": candidate.get("source_url"),
        "related_staged_resource_candidate_id": cid,
        "created_from_signal_type": "staged_resource",
        "created_from_signal_id": cid,
        "priority_reasons_json": json.dumps(reasons),
    }
    r = supabase.table("review_queue_items").insert(row).execute()
    created = (r.data or [{}])[0] if r.data else None
    if created:
        try:
            from .ops_notification_service import evaluate_queue_notification_rules
            evaluate_queue_notification_rules(created)
        except Exception as e:
            log.warning("Notification evaluation failed for new queue item: %s", e)
    return created


def create_queue_item_from_staged_event(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create queue item from staged event candidate."""
    supabase = _get_supabase()
    cid = candidate.get("id")
    if not cid:
        return None

    existing = (
        supabase.table("review_queue_items")
        .select("id")
        .eq("related_staged_event_candidate_id", cid)
        .in_("status", list(_OPEN_STATUSES))
        .limit(1)
        .execute()
    ).data
    if existing:
        return None

    start_str = candidate.get("start_datetime")
    days_until = None
    if start_str:
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            delta = (start - datetime.now(timezone.utc)).total_seconds() / 86400
            if 0 <= delta <= 14:
                days_until = int(delta)
        except Exception:
            pass

    score, band, reasons = compute_priority_score(
        queue_item_type="staged_event_candidate",
        trust_tier=candidate.get("trust_tier"),
        event_start_soon_days=days_until if days_until and days_until <= 7 else None,
    )

    row = {
        "queue_item_type": "staged_event_candidate",
        "status": "new",
        "priority_score": score,
        "priority_band": band,
        "country_code": candidate.get("country_code"),
        "city_name": candidate.get("city_name"),
        "title": (candidate.get("title") or "Staged event")[:500],
        "summary": (candidate.get("description") or "")[:1000],
        "source_name": candidate.get("source_name"),
        "source_url": candidate.get("source_url"),
        "related_staged_event_candidate_id": cid,
        "created_from_signal_type": "staged_event",
        "created_from_signal_id": cid,
        "priority_reasons_json": json.dumps(reasons),
        "context_json": json.dumps({"start_datetime": start_str}),
    }
    r = supabase.table("review_queue_items").insert(row).execute()
    created = (r.data or [{}])[0] if r.data else None
    if created:
        try:
            from .ops_notification_service import evaluate_queue_notification_rules
            evaluate_queue_notification_rules(created)
        except Exception as e:
            log.warning("Notification evaluation failed for new queue item: %s", e)
    return created


def create_queue_item_from_source_change(change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create queue item from significant document change."""
    supabase = _get_supabase()
    cid = change.get("id")
    if not cid or (change.get("change_type") or "").lower() not in ("significant_change", "new", "updated"):
        return None

    existing = (
        supabase.table("review_queue_items")
        .select("id")
        .eq("related_change_event_id", cid)
        .in_("status", list(_OPEN_STATUSES))
        .limit(1)
        .execute()
    ).data
    if existing:
        return None

    ch_score = change.get("change_score")
    if isinstance(ch_score, (int, float)) and ch_score < 0.5:
        return None

    score, band, reasons = compute_priority_score(
        queue_item_type="source_change_review",
        trust_tier=None,
        content_domain=None,
        change_score=float(ch_score) if ch_score is not None else 0.8,
    )

    title = (change.get("page_title") or change.get("source_url") or "Source changed")[:500]
    row = {
        "queue_item_type": "source_change_review",
        "status": "new",
        "priority_score": score,
        "priority_band": band,
        "country_code": change.get("country_code"),
        "city_name": change.get("city_name"),
        "title": title,
        "source_name": change.get("source_name"),
        "source_url": change.get("source_url"),
        "related_change_event_id": cid,
        "created_from_signal_type": "document_change",
        "created_from_signal_id": cid,
        "priority_reasons_json": json.dumps(reasons),
        "context_json": json.dumps({"change_type": change.get("change_type"), "change_score": ch_score}),
    }
    r = supabase.table("review_queue_items").insert(row).execute()
    created = (r.data or [{}])[0] if r.data else None
    if created:
        try:
            from .ops_notification_service import evaluate_queue_notification_rules
            evaluate_queue_notification_rules(created)
        except Exception as e:
            log.warning("Notification evaluation failed for new queue item: %s", e)
    return created


def create_queue_item_from_stale_live_resource(resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create queue item for stale live resource."""
    supabase = _get_supabase()
    rid = resource.get("id")
    if not rid:
        return None

    existing = (
        supabase.table("review_queue_items")
        .select("id")
        .eq("related_live_resource_id", rid)
        .in_("status", list(_OPEN_STATUSES))
        .limit(1)
        .execute()
    ).data
    if existing:
        return None

    score, band, reasons = compute_priority_score(
        queue_item_type="stale_live_resource_review",
        is_stale_live=True,
    )

    row = {
        "queue_item_type": "stale_live_resource_review",
        "status": "new",
        "priority_score": score,
        "priority_band": band,
        "country_code": resource.get("country_code"),
        "city_name": resource.get("city_name"),
        "title": (resource.get("title") or "Stale resource")[:500],
        "related_live_resource_id": rid,
        "created_from_signal_type": "stale_live_resource",
        "created_from_signal_id": str(rid),
        "priority_reasons_json": json.dumps(reasons),
        "context_json": json.dumps({"stale_reason": resource.get("stale_reason", "old_updated_at")}),
    }
    r = supabase.table("review_queue_items").insert(row).execute()
    created = (r.data or [{}])[0] if r.data else None
    if created:
        try:
            from .ops_notification_service import evaluate_queue_notification_rules
            evaluate_queue_notification_rules(created)
        except Exception as e:
            log.warning("Notification evaluation failed for new queue item: %s", e)
    return created


def create_queue_item_from_stale_live_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create queue item for stale/expired live event."""
    supabase = _get_supabase()
    eid = event.get("id")
    if not eid:
        return None

    existing = (
        supabase.table("review_queue_items")
        .select("id")
        .eq("related_live_event_id", eid)
        .in_("status", list(_OPEN_STATUSES))
        .limit(1)
        .execute()
    ).data
    if existing:
        return None

    score, band, reasons = compute_priority_score(
        queue_item_type="stale_live_event_review",
        is_stale_live=True,
    )

    row = {
        "queue_item_type": "stale_live_event_review",
        "status": "new",
        "priority_score": score,
        "priority_band": band,
        "country_code": event.get("country_code"),
        "city_name": event.get("city_name"),
        "title": (event.get("title") or "Stale event")[:500],
        "related_live_event_id": eid,
        "created_from_signal_type": "stale_live_event",
        "created_from_signal_id": str(eid),
        "priority_reasons_json": json.dumps(reasons),
        "context_json": json.dumps({"stale_reason": event.get("stale_reason", "event_expired")}),
    }
    r = supabase.table("review_queue_items").insert(row).execute()
    created = (r.data or [{}])[0] if r.data else None
    if created:
        try:
            from .ops_notification_service import evaluate_queue_notification_rules
            evaluate_queue_notification_rules(created)
        except Exception as e:
            log.warning("Notification evaluation failed for new queue item: %s", e)
    return created


def list_review_queue_items(
    status: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    priority_band: Optional[str] = None,
    assignee_id: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    queue_item_type: Optional[str] = None,
    overdue_only: bool = False,
    unassigned_only: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "priority",
) -> Dict[str, Any]:
    """List queue items with filters."""
    supabase = _get_supabase()
    q = supabase.table("review_queue_items").select("*", count="exact")

    if status:
        q = q.eq("status", status)
    elif statuses:
        q = q.in_("status", statuses)

    if priority_band:
        q = q.eq("priority_band", priority_band)
    if assignee_id:
        q = q.eq("assigned_to_user_id", assignee_id)
    if unassigned_only:
        q = q.is_("assigned_to_user_id", "null")
    if country_code:
        q = q.eq("country_code", country_code)
    if city_name:
        q = q.eq("city_name", city_name)
    if queue_item_type:
        q = q.eq("queue_item_type", queue_item_type)
    if search:
        q = q.ilike("title", f"%{search}%")

    if overdue_only:
        now = datetime.now(timezone.utc).isoformat()
        q = q.lt("due_at", now).not_.in_("status", ["resolved", "rejected", "deferred"])

    order_col = "priority_score"
    order_asc = False
    if sort == "created":
        order_col = "created_at"
    elif sort == "due":
        order_col = "due_at"
        order_asc = True
    elif sort == "age":
        order_col = "created_at"
        order_asc = True

    q = q.order(order_col, desc=not order_asc).range(offset, offset + limit - 1)
    r = q.execute()
    items = r.data or []
    total = r.count if hasattr(r, "count") and r.count is not None else len(items)

    for it in items:
        pr = it.get("priority_reasons_json")
        if isinstance(pr, str):
            try:
                it["priority_reasons"] = json.loads(pr)
            except Exception:
                it["priority_reasons"] = []
        else:
            it["priority_reasons"] = pr or []

    return {"items": items, "total": total}


def get_review_queue_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Get single queue item by id."""
    supabase = _get_supabase()
    r = (
        supabase.table("review_queue_items")
        .select("*")
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    items = r.data or []
    if not items:
        return None
    it = items[0]
    pr = it.get("priority_reasons_json")
    if isinstance(pr, str):
        try:
            it["priority_reasons"] = json.loads(pr)
        except Exception:
            it["priority_reasons"] = []
    else:
        it["priority_reasons"] = pr or []
    return it


def get_review_queue_activity(item_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get activity log for queue item."""
    supabase = _get_supabase()
    r = (
        supabase.table("review_queue_activity_log")
        .select("*")
        .eq("queue_item_id", item_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return r.data or []


def _log_activity(
    queue_item_id: str,
    action_type: str,
    actor_user_id: str,
    previous_status: Optional[str] = None,
    new_status: Optional[str] = None,
    previous_assignee_id: Optional[str] = None,
    new_assignee_id: Optional[str] = None,
    note: Optional[str] = None,
):
    supabase = _get_supabase()
    supabase.table("review_queue_activity_log").insert({
        "queue_item_id": queue_item_id,
        "action_type": action_type,
        "actor_user_id": actor_user_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "previous_assignee_id": previous_assignee_id,
        "new_assignee_id": new_assignee_id,
        "note": note,
    }).execute()


def _validate_status_transition(current: str, new: str) -> bool:
    allowed = _STATUS_TRANSITIONS.get(current, [])
    if new in allowed:
        return True
    if new == "in_progress" and current == "assigned":
        return True
    return False


def assign_queue_item(
    item_id: str,
    assignee_user_id: str,
    actor_user_id: str,
) -> Optional[Dict[str, Any]]:
    """Assign queue item to user."""
    item = get_review_queue_item(item_id)
    if not item:
        return None
    if item.get("status") not in ("new", "triaged", "assigned", "deferred"):
        log.warning("Cannot assign item %s in status %s", item_id, item.get("status"))
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    prev_assignee = item.get("assigned_to_user_id")

    supabase.table("review_queue_items").update({
        "assigned_to_user_id": assignee_user_id,
        "assigned_by_user_id": actor_user_id,
        "assigned_at": now,
        "status": "assigned",
        "updated_at": now,
    }).eq("id", item_id).execute()

    _log_activity(item_id, "assign", actor_user_id, previous_assignee_id=prev_assignee, new_assignee_id=assignee_user_id)
    return get_review_queue_item(item_id)


def claim_queue_item(item_id: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    """Claim queue item (assign to self)."""
    return assign_queue_item(item_id, actor_user_id, actor_user_id)


def unassign_queue_item(item_id: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    """Unassign queue item."""
    item = get_review_queue_item(item_id)
    if not item:
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    prev_assignee = item.get("assigned_to_user_id")

    supabase.table("review_queue_items").update({
        "assigned_to_user_id": None,
        "assigned_by_user_id": None,
        "assigned_at": None,
        "status": "triaged" if item.get("status") == "assigned" else item.get("status"),
        "updated_at": now,
    }).eq("id", item_id).execute()

    _log_activity(item_id, "unassign", actor_user_id, previous_assignee_id=prev_assignee, new_assignee_id=None)
    return get_review_queue_item(item_id)


def change_queue_item_status(
    item_id: str,
    new_status: str,
    actor_user_id: str,
    note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Change queue item status. Validates transitions."""
    item = get_review_queue_item(item_id)
    if not item:
        return None

    current = item.get("status", "new")
    if not _validate_status_transition(current, new_status):
        # Allow reopen -> new for resolved/rejected
        if new_status in ("new", "triaged") and current in ("resolved", "rejected"):
            new_status = "new"
        else:
            log.warning("Invalid status transition %s -> %s", current, new_status)
            return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    updates: Dict[str, Any] = {"status": new_status, "updated_at": now}
    if new_status == "resolved":
        updates["resolved_at"] = now
        updates["resolved_by_user_id"] = actor_user_id

    supabase.table("review_queue_items").update(updates).eq("id", item_id).execute()
    _log_activity(item_id, "status_change", actor_user_id, previous_status=current, new_status=new_status, note=note)
    return get_review_queue_item(item_id)


def defer_queue_item(
    item_id: str,
    due_at: Optional[str],
    actor_user_id: str,
    note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Defer queue item."""
    item = get_review_queue_item(item_id)
    if not item:
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    updates: Dict[str, Any] = {"status": "deferred", "due_at": due_at, "updated_at": now}
    if note:
        existing_notes = item.get("notes") or ""
        updates["notes"] = (existing_notes + "\n[Deferred] " + note).strip()
    supabase.table("review_queue_items").update(updates).eq("id", item_id).execute()

    _log_activity(item_id, "defer", actor_user_id, previous_status=item.get("status"), new_status="deferred", note=note)
    return get_review_queue_item(item_id)


def resolve_queue_item(
    item_id: str,
    actor_user_id: str,
    resolution_summary: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve queue item."""
    item = get_review_queue_item(item_id)
    if not item:
        return None
    if item.get("status") not in ("in_progress", "waiting", "blocked"):
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("review_queue_items").update({
        "status": "resolved",
        "resolution_summary": resolution_summary,
        "resolved_at": now,
        "resolved_by_user_id": actor_user_id,
        "updated_at": now,
    }).eq("id", item_id).execute()

    _log_activity(item_id, "resolve", actor_user_id, previous_status=item.get("status"), new_status="resolved", note=resolution_summary)
    return get_review_queue_item(item_id)


def reopen_queue_item(item_id: str, actor_user_id: str, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Reopen resolved/rejected/deferred item."""
    item = get_review_queue_item(item_id)
    if not item:
        return None
    if item.get("status") not in ("resolved", "rejected", "deferred"):
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("review_queue_items").update({
        "status": "new",
        "resolution_summary": None,
        "resolved_at": None,
        "resolved_by_user_id": None,
        "updated_at": now,
    }).eq("id", item_id).execute()

    _log_activity(item_id, "reopen", actor_user_id, previous_status=item.get("status"), new_status="new", note=note)
    return get_review_queue_item(item_id)


def update_queue_item_notes(item_id: str, notes: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    """Update notes on queue item."""
    item = get_review_queue_item(item_id)
    if not item:
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("review_queue_items").update({"notes": notes, "updated_at": now}).eq("id", item_id).execute()
    _log_activity(item_id, "note_added", actor_user_id, note=notes[:200])
    return get_review_queue_item(item_id)


def get_review_queue_stats() -> Dict[str, Any]:
    """Get queue statistics for dashboard."""
    supabase = _get_supabase()
    open_statuses = list(_OPEN_STATUSES)

    items = (
        supabase.table("review_queue_items")
        .select("id, status, priority_band, queue_item_type, assigned_to_user_id, due_at")
        .in_("status", open_statuses)
        .execute()
    ).data or []

    now = datetime.now(timezone.utc)
    overdue_count = sum(
        1 for it in items
        if it.get("due_at") and it.get("status") not in ("resolved", "rejected", "deferred")
        and datetime.fromisoformat((it["due_at"] or "").replace("Z", "+00:00")) < now
    )

    by_status: Dict[str, int] = {}
    for it in items:
        s = it.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    by_band: Dict[str, int] = {}
    for it in items:
        b = it.get("priority_band", "medium")
        by_band[b] = by_band.get(b, 0) + 1

    by_type: Dict[str, int] = {}
    for it in items:
        t = it.get("queue_item_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    unassigned = sum(1 for it in items if not it.get("assigned_to_user_id"))
    in_progress = by_status.get("in_progress", 0)

    return {
        "open_items_count": len(items),
        "unassigned_count": unassigned,
        "in_progress_count": in_progress,
        "overdue_count": overdue_count,
        "by_status": by_status,
        "by_priority_band": by_band,
        "by_queue_item_type": by_type,
    }


def backfill_queue_from_signals() -> Dict[str, Any]:
    """Create queue items from existing staged candidates, changes, and stale content."""
    created = 0
    supabase = _get_supabase()

    # Staged resources
    res = (
        supabase.table("staged_resource_candidates")
        .select("*")
        .in_("status", ["new", "needs_review"])
        .limit(200)
        .execute()
    ).data or []
    for c in res:
        if create_queue_item_from_staged_resource(c):
            created += 1

    # Staged events
    ev = (
        supabase.table("staged_event_candidates")
        .select("*")
        .in_("status", ["new", "needs_review"])
        .limit(200)
        .execute()
    ).data or []
    for c in ev:
        if create_queue_item_from_staged_event(c):
            created += 1

    # Significant changes (last 14 days)
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    ch = (
        supabase.table("document_change_events")
        .select("*")
        .in_("change_type", ["significant_change", "new", "updated"])
        .gte("detected_at", since)
        .limit(100)
        .execute()
    ).data or []
    for c in ch:
        if create_queue_item_from_source_change(c):
            created += 1

    # Stale live resources
    from .freshness_service import get_stale_live_resources
    for r in get_stale_live_resources(limit=50):
        if create_queue_item_from_stale_live_resource(r):
            created += 1

    # Stale live events
    from .freshness_service import get_stale_live_events
    for e in get_stale_live_events(limit=50):
        if create_queue_item_from_stale_live_event(e):
            created += 1

    return {"created": created}


def list_admin_users_for_assignment(limit: int = 50) -> List[Dict[str, Any]]:
    """List users who can be assigned (admins). Uses profiles if available."""
    try:
        from ..database import db
        profiles = db.list_profiles(None) or []
        admins = [p for p in profiles if (p.get("role") or "").upper() == "ADMIN"]
        return [{"id": p.get("id"), "email": p.get("email"), "full_name": p.get("full_name")} for p in admins[:limit]]
    except Exception:
        return []
