"""
Ops Notification Service: create, update, lifecycle, rules evaluation.
Admin-only. Integrates with review queue, freshness, crawl, change detection.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client
from .ops_notification_config import (
    BLOCKED_TOO_LONG_HOURS,
    CRITICAL_UNASSIGNED_HOURS,
    CRITICAL_UNRESOLVED_HOURS,
    HIGH_UNASSIGNED_HOURS,
    REOPEN_ESCALATION_COUNT,
    RETRIGGER_COOLDOWN_SECONDS,
)

log = logging.getLogger(__name__)

_SEVERITIES = ("info", "warning", "high", "critical")
_STATUSES = ("open", "acknowledged", "resolved", "suppressed")


def _get_supabase():
    return get_supabase_admin_client()


def _log_event(notification_id: str, event_type: str, actor_user_id: Optional[str] = None, details: Optional[Dict] = None):
    supabase = _get_supabase()
    supabase.table("ops_notification_events").insert({
        "notification_id": notification_id,
        "event_type": event_type,
        "actor_user_id": actor_user_id,
        "details_json": json.dumps(details or {}),
    }).execute()


def _build_dedupe_key(
    notification_type: str,
    *,
    queue_item_id: Optional[str] = None,
    source_name: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    live_resource_id: Optional[str] = None,
    live_event_id: Optional[str] = None,
    schedule_id: Optional[str] = None,
) -> str:
    parts = [notification_type]
    if queue_item_id:
        parts.append(f"q:{queue_item_id}")
    if source_name:
        parts.append(f"s:{source_name}")
    if country_code:
        parts.append(f"c:{country_code}")
    if city_name:
        parts.append(f"city:{city_name}")
    if live_resource_id:
        parts.append(f"r:{live_resource_id}")
    if live_event_id:
        parts.append(f"e:{live_event_id}")
    if schedule_id:
        parts.append(f"sch:{schedule_id}")
    return "|".join(parts)


def create_or_update_notification(
    notification_type: str,
    severity: str,
    title: str,
    message: str,
    dedupe_key: str,
    *,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    content_domain: Optional[str] = None,
    trust_tier: Optional[str] = None,
    related_queue_item_id: Optional[str] = None,
    related_change_event_id: Optional[str] = None,
    related_crawl_job_run_id: Optional[str] = None,
    related_schedule_id: Optional[str] = None,
    related_source_name: Optional[str] = None,
    related_live_resource_id: Optional[str] = None,
    related_live_event_id: Optional[str] = None,
    related_staged_candidate_type: Optional[str] = None,
    related_staged_candidate_id: Optional[str] = None,
    escalation_level: Optional[int] = None,
    priority_score: Optional[int] = None,
    payload: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create new notification or retrigger existing. Dedupes by dedupe_key."""
    if severity not in _SEVERITIES:
        severity = "warning"

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # Find existing open/acknowledged with same dedupe_key
    existing = (
        supabase.table("ops_notifications")
        .select("*")
        .eq("dedupe_key", dedupe_key)
        .in_("status", ["open", "acknowledged"])
        .limit(1)
        .execute()
    ).data

    if existing:
        row = existing[0]
        nid = row["id"]
        last_retriggered = row.get("last_retriggered_at")
        if last_retriggered:
            last_ts = datetime.fromisoformat((last_retriggered or "").replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - last_ts).total_seconds() < RETRIGGER_COOLDOWN_SECONDS:
                return row  # Cooldown - skip retrigger
        retrigger_count = (row.get("retrigger_count") or 0) + 1
        supabase.table("ops_notifications").update({
            "last_retriggered_at": now,
            "retrigger_count": retrigger_count,
            "severity": severity,
            "title": title,
            "message": message,
            "updated_at": now,
            "triggered_at": now,
        }).eq("id", nid).execute()
        _log_event(nid, "retriggered", details={"retrigger_count": retrigger_count})
        return get_notification_by_id(nid) or row
    else:
        row = {
            "notification_type": notification_type,
            "severity": severity,
            "status": "open",
            "title": title,
            "message": message,
            "dedupe_key": dedupe_key,
            "country_code": country_code,
            "city_name": city_name,
            "content_domain": content_domain,
            "trust_tier": trust_tier,
            "related_queue_item_id": related_queue_item_id,
            "related_change_event_id": related_change_event_id,
            "related_crawl_job_run_id": related_crawl_job_run_id,
            "related_schedule_id": related_schedule_id,
            "related_source_name": related_source_name,
            "related_live_resource_id": related_live_resource_id,
            "related_live_event_id": related_live_event_id,
            "related_staged_candidate_type": related_staged_candidate_type,
            "related_staged_candidate_id": related_staged_candidate_id,
            "escalation_level": escalation_level,
            "priority_score": priority_score,
            "payload_json": json.dumps(payload or {}),
        }
        r = supabase.table("ops_notifications").insert(row).execute()
        n = (r.data or [{}])[0]
        if n.get("id"):
            _log_event(n["id"], "created")
        return n


def get_notification_by_id(nid: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("ops_notifications").select("*").eq("id", nid).limit(1).execute()
    items = r.data or []
    return items[0] if items else None


def acknowledge_notification(nid: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    n = get_notification_by_id(nid)
    if not n or n.get("status") not in ("open",):
        return None
    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    supabase.table("ops_notifications").update({
        "status": "acknowledged",
        "acknowledged_at": now,
        "acknowledged_by_user_id": actor_user_id,
        "updated_at": now,
    }).eq("id", nid).execute()
    _log_event(nid, "acknowledged", actor_user_id)
    return get_notification_by_id(nid)


def resolve_notification(nid: str, actor_user_id: str, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    n = get_notification_by_id(nid)
    if not n or n.get("status") in ("resolved",):
        return None
    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    updates: Dict[str, Any] = {
        "status": "resolved",
        "resolved_at": now,
        "resolved_by_user_id": actor_user_id,
        "updated_at": now,
    }
    if reason:
        payload = json.loads(n.get("payload_json") or "{}")
        payload["resolution_reason"] = reason
        updates["payload_json"] = json.dumps(payload)
    supabase.table("ops_notifications").update(updates).eq("id", nid).execute()
    _log_event(nid, "resolved", actor_user_id, {"reason": reason})
    return get_notification_by_id(nid)


def suppress_notification(nid: str, actor_user_id: str, until: Optional[str] = None) -> Optional[Dict[str, Any]]:
    n = get_notification_by_id(nid)
    if not n:
        return None
    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    supabase.table("ops_notifications").update({
        "status": "suppressed",
        "suppressed_until": until,
        "updated_at": now,
    }).eq("id", nid).execute()
    _log_event(nid, "suppressed", actor_user_id, {"until": until})
    return get_notification_by_id(nid)


def reopen_notification(nid: str, actor_user_id: str, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    n = get_notification_by_id(nid)
    if not n or n.get("status") not in ("resolved", "suppressed"):
        return None
    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    supabase.table("ops_notifications").update({
        "status": "open",
        "resolved_at": None,
        "resolved_by_user_id": None,
        "suppressed_until": None,
        "acknowledged_at": None,
        "acknowledged_by_user_id": None,
        "updated_at": now,
        "triggered_at": now,
    }).eq("id", nid).execute()
    _log_event(nid, "reopened", actor_user_id, {"reason": reason})
    return get_notification_by_id(nid)


def list_ops_notifications(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    notification_type: Optional[str] = None,
    country_code: Optional[str] = None,
    escalation_only: bool = False,
    open_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    supabase = _get_supabase()
    q = supabase.table("ops_notifications").select("*", count="exact")
    if status:
        q = q.eq("status", status)
    if severity:
        q = q.eq("severity", severity)
    if notification_type:
        q = q.eq("notification_type", notification_type)
    if country_code:
        q = q.eq("country_code", country_code)
    if escalation_only:
        q = q.in_("severity", ["high", "critical"])
    if open_only:
        q = q.in_("status", ["open", "acknowledged"])
    q = q.order("triggered_at", desc=True).range(offset, offset + limit - 1)
    r = q.execute()
    items = r.data or []
    total = r.count if hasattr(r, "count") and r.count is not None else len(items)
    return {"items": items, "total": total}


def get_ops_notification_stats() -> Dict[str, Any]:
    supabase = _get_supabase()
    all_n = (
        supabase.table("ops_notifications")
        .select("id, status, severity")
        .in_("status", ["open", "acknowledged"])
        .execute()
    ).data or []
    open_count = len(all_n)
    critical = sum(1 for n in all_n if n.get("severity") == "critical")
    high = sum(1 for n in all_n if n.get("severity") == "high")
    return {"open_count": open_count, "critical_count": critical, "high_count": high}


def get_notification_feed(limit: int = 20, critical_first: bool = True) -> List[Dict[str, Any]]:
    supabase = _get_supabase()
    q = (
        supabase.table("ops_notifications")
        .select("*")
        .in_("status", ["open", "acknowledged"])
        .order("triggered_at", desc=True)
        .limit(limit * 2 if critical_first else limit)
    )
    items = q.execute().data or []
    if critical_first and items:
        order_map = {"critical": 0, "high": 1, "warning": 2, "info": 3}
        items = sorted(items, key=lambda x: (order_map.get(x.get("severity", ""), 4), -(x.get("triggered_at") or "")))
        items = items[:limit]
    return items


def get_notification_events(nid: str, limit: int = 50) -> List[Dict[str, Any]]:
    supabase = _get_supabase()
    r = (
        supabase.table("ops_notification_events")
        .select("*")
        .eq("notification_id", nid)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return r.data or []


# --- Rules evaluation ---
def evaluate_queue_notification_rules(queue_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate notification rules for a queue item. Returns list of created/updated notifications."""
    created = []
    now = datetime.now(timezone.utc)
    item_id = queue_item.get("id")
    status = queue_item.get("status", "")
    priority_band = queue_item.get("priority_band", "medium")
    created_at_str = queue_item.get("created_at")
    assigned_to = queue_item.get("assigned_to_user_id")
    sla_target = queue_item.get("sla_target_at")
    trust_tier = queue_item.get("trust_tier")
    country_code = queue_item.get("country_code")
    city_name = queue_item.get("city_name")
    title = (queue_item.get("title") or "Queue item")[:100]

    if not item_id:
        return created

    created_at = None
    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except Exception:
            pass

    # Critical item created
    if priority_band == "critical":
        dedupe = _build_dedupe_key("queue_item_created_critical", queue_item_id=item_id)
        n = create_or_update_notification(
            "queue_item_created_critical",
            "high",
            f"Critical queue item: {title}",
            f"Critical-priority queue item requires attention. Trust tier: {trust_tier or 'unknown'}, destination: {country_code or 'unknown'}",
            dedupe,
            country_code=country_code,
            city_name=city_name,
            trust_tier=trust_tier,
            related_queue_item_id=item_id,
            priority_score=queue_item.get("priority_score"),
        )
        if n:
            created.append(n)

    # Unassigned critical/high for too long
    if status in ("new", "triaged") and not assigned_to and created_at:
        hours_unassigned = (now - created_at).total_seconds() / 3600
        if priority_band == "critical" and hours_unassigned >= CRITICAL_UNASSIGNED_HOURS:
            dedupe = _build_dedupe_key("queue_item_unassigned_overdue", queue_item_id=item_id)
            n = create_or_update_notification(
                "queue_item_unassigned_overdue",
                "critical",
                f"Critical item unassigned {int(hours_unassigned)}h: {title}",
                f"Critical queue item has been unassigned for {int(hours_unassigned)} hours. T0/T1 sources require prompt assignment.",
                dedupe,
                country_code=country_code,
                trust_tier=trust_tier,
                related_queue_item_id=item_id,
                payload={"hours_unassigned": hours_unassigned, "threshold": CRITICAL_UNASSIGNED_HOURS},
            )
            if n:
                created.append(n)
        elif priority_band == "high" and hours_unassigned >= HIGH_UNASSIGNED_HOURS:
            dedupe = _build_dedupe_key("queue_item_unassigned_overdue", queue_item_id=item_id)
            n = create_or_update_notification(
                "queue_item_unassigned_overdue",
                "high",
                f"High-priority item unassigned {int(hours_unassigned)}h: {title}",
                f"High-priority queue item has been unassigned for {int(hours_unassigned)} hours.",
                dedupe,
                country_code=country_code,
                related_queue_item_id=item_id,
                payload={"hours_unassigned": hours_unassigned, "threshold": HIGH_UNASSIGNED_HOURS},
            )
            if n:
                created.append(n)

    # SLA breach
    if sla_target and status not in ("resolved", "rejected", "deferred"):
        try:
            sla_dt = datetime.fromisoformat(sla_target.replace("Z", "+00:00"))
            if now > sla_dt:
                dedupe = _build_dedupe_key("queue_item_sla_breach", queue_item_id=item_id)
                sev = "critical" if priority_band in ("critical", "high") and trust_tier in ("T0", "T1") else "high"
                n = create_or_update_notification(
                    "queue_item_sla_breach",
                    sev,
                    f"SLA breach: {title}",
                    f"Queue item has breached SLA. Trust tier: {trust_tier or 'unknown'}.",
                    dedupe,
                    country_code=country_code,
                    trust_tier=trust_tier,
                    related_queue_item_id=item_id,
                    payload={"sla_target": sla_target},
                )
                if n:
                    created.append(n)
        except Exception:
            pass

    # Blocked too long
    if status == "blocked" and created_at:
        hours = (now - created_at).total_seconds() / 3600
        if hours >= BLOCKED_TOO_LONG_HOURS:
            dedupe = _build_dedupe_key("queue_item_blocked_too_long", queue_item_id=item_id)
            n = create_or_update_notification(
                "queue_item_blocked_too_long",
                "high",
                f"Blocked item {int(hours)}h: {title}",
                f"Queue item has been blocked for {int(hours)} hours and may need management intervention.",
                dedupe,
                country_code=country_code,
                related_queue_item_id=item_id,
                payload={"hours_blocked": hours, "threshold": BLOCKED_TOO_LONG_HOURS},
            )
            if n:
                created.append(n)

    return created


def evaluate_stale_signal_notification(stale_resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create notification for critical stale live resource."""
    rid = stale_resource.get("id")
    if not rid:
        return None
    title = (stale_resource.get("title") or "Stale resource")[:80]
    country = stale_resource.get("country_code")
    dedupe = _build_dedupe_key("stale_live_resource_critical", live_resource_id=str(rid))
    return create_or_update_notification(
        "stale_live_resource_critical",
        "high",
        f"Stale live content: {title}",
        f"Published resource may be outdated. Country: {country or 'unknown'}.",
        dedupe,
        country_code=country,
        city_name=stale_resource.get("city_name"),
        related_live_resource_id=rid,
        payload={"stale_reason": stale_resource.get("stale_reason", "old_updated_at")},
    )


def evaluate_crawl_failure_notification(
    source_name: str,
    failure_count: int,
    job_run_id: Optional[str] = None,
    schedule_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create notification for repeated crawl failure."""
    if failure_count < 2:
        return None
    dedupe = _build_dedupe_key("crawl_failure_repeated", source_name=source_name)
    sev = "critical" if failure_count >= 3 else "high"
    return create_or_update_notification(
        "crawl_failure_repeated",
        sev,
        f"Repeated crawl failure: {source_name}",
        f"Source has failed {failure_count} times. Manual attention may be required.",
        dedupe,
        related_source_name=source_name,
        related_crawl_job_run_id=job_run_id,
        related_schedule_id=schedule_id,
        payload={"failure_count": failure_count},
    )


def sync_resolved_notifications() -> Dict[str, int]:
    """Auto-resolve notifications when linked queue item is resolved."""
    supabase = _get_supabase()
    open_with_queue = (
        supabase.table("ops_notifications")
        .select("id, related_queue_item_id")
        .in_("status", ["open", "acknowledged"])
        .not_.is_("related_queue_item_id", "null")
        .execute()
    ).data or []
    resolved = 0
    for n in open_with_queue:
        qid = n.get("related_queue_item_id")
        if not qid:
            continue
        q = supabase.table("review_queue_items").select("status").eq("id", qid).limit(1).execute()
        items = q.data or []
        if items and items[0].get("status") in ("resolved", "rejected"):
            resolve_notification(n["id"], "system")  # system auto-resolve
            resolved += 1
    return {"resolved": resolved}


def recompute_time_based_notifications() -> Dict[str, int]:
    """Periodic job: check queue items and create/update time-based notifications."""
    supabase = _get_supabase()
    open_items = (
        supabase.table("review_queue_items")
        .select("*")
        .in_("status", ["new", "triaged", "assigned", "in_progress", "blocked", "waiting"])
        .limit(500)
        .execute()
    ).data or []
    created = 0
    for it in open_items:
        for n in evaluate_queue_notification_rules(it):
            created += 1
    return {"evaluated": len(open_items), "notifications_created_or_updated": created}
