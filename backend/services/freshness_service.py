"""
Freshness service: compute source/document/destination freshness states.
Detect stale live resources/events. No auto-publish.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

_DEFAULT_CADENCE_DAYS = {
    "events": 1,
    "culture_leisure": 2,
    "transport": 2,
    "admin_essentials": 7,
    "housing": 7,
    "healthcare": 7,
    "schools_childcare": 7,
    "daily_life": 7,
    "community": 7,
    "cost_of_living": 14,
    "safety": 14,
}

_FRESHNESS_WARNING_RATIO = 0.75  # warning when 75% of cadence elapsed
_FRESHNESS_STALE_RATIO = 1.0
_FRESHNESS_OVERDUE_RATIO = 1.5
_LIVE_RESOURCE_STALE_DAYS = 180
_LIVE_EVENT_EXPIRY_DAYS = 0  # past events are expired


def _get_supabase():
    return get_supabase_admin_client()


def _cadence_days_for_domain(content_domain: Optional[str]) -> int:
    return _DEFAULT_CADENCE_DAYS.get(content_domain or "admin_essentials", 7)


def compute_source_freshness(
    last_successful_crawl: Optional[datetime],
    expected_cadence_days: int,
    recent_failures: int = 0,
) -> str:
    """
    Compute freshness state: fresh, warning, stale, overdue, error.
    """
    if recent_failures >= 2:
        return "error"
    if not last_successful_crawl:
        return "overdue"
    now = datetime.now(timezone.utc)
    delta = now - last_successful_crawl
    days = delta.total_seconds() / 86400
    ratio = days / expected_cadence_days if expected_cadence_days else 1
    if ratio >= _FRESHNESS_OVERDUE_RATIO:
        return "overdue"
    if ratio >= _FRESHNESS_STALE_RATIO:
        return "stale"
    if ratio >= _FRESHNESS_WARNING_RATIO:
        return "warning"
    return "fresh"


def get_source_freshness_signals() -> List[Dict[str, Any]]:
    """Get per-source freshness signals from crawl history."""
    supabase = _get_supabase()

    # Last successful run per source (from crawl_runs + crawled_source_documents)
    runs = (
        supabase.table("crawl_runs")
        .select("id, started_at, finished_at, status, source_scope")
        .eq("status", "completed")
        .order("finished_at", desc=True)
        .limit(500)
        .execute()
    ).data or []

    docs = (
        supabase.table("crawled_source_documents")
        .select("id, source_name, country_code, city_name, crawl_run_id, fetched_at")
        .execute()
    ).data or []

    run_by_id = {r["id"]: r for r in runs}
    source_last: Dict[str, Dict] = {}
    for d in docs:
        run = run_by_id.get(d.get("crawl_run_id", ""))
        if not run or run.get("status") != "completed":
            continue
        key = d.get("source_name", "") or "unknown"
        fetched = d.get("fetched_at") or run.get("finished_at")
        if key not in source_last or (fetched and (
            not source_last[key].get("last_crawl") or
            fetched > source_last[key]["last_crawl"]
        )):
            source_last[key] = {
                "source_name": key,
                "country_code": d.get("country_code"),
                "city_name": d.get("city_name"),
                "last_crawl": fetched,
                "content_domain": "admin_essentials",
            }

    # Content domain from crawl config - we don't have it in DB, use default
    result = []
    for key, v in source_last.items():
        cadence = _cadence_days_for_domain(v.get("content_domain"))
        last_dt = None
        if v.get("last_crawl"):
            try:
                last_dt = datetime.fromisoformat(v["last_crawl"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        state = compute_source_freshness(last_dt, cadence, 0)
        result.append({
            **v,
            "expected_cadence_days": cadence,
            "freshness_state": state,
        })
    return result


def get_stale_live_resources(
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Find live resources that may be stale (old updated_at or linked source changed)."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=_LIVE_RESOURCE_STALE_DAYS)).isoformat()

    q = (
        supabase.table("country_resources")
        .select("id, title, country_code, city_name, external_url, updated_at, source_id")
        .eq("is_active", True)
        .lt("updated_at", cutoff)
    )
    if country_code:
        q = q.eq("country_code", country_code)
    if city_name:
        q = q.eq("city_name", city_name)
    r = q.limit(limit).execute()
    return [
        {
            **row,
            "stale_reason": "old_updated_at",
            "days_since_update": (now - datetime.fromisoformat((row.get("updated_at") or now.isoformat()).replace("Z", "+00:00"))).days,
        }
        for row in (r.data or [])
    ]


def get_stale_live_events(
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Find live events that are expired (past) or stale."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    q = (
        supabase.table("rkg_country_events")
        .select("id, title, country_code, city_name, start_datetime, end_datetime, status")
        .lt("start_datetime", now)
    )
    if country_code:
        q = q.eq("country_code", country_code)
    if city_name:
        q = q.eq("city_name", city_name)
    r = q.limit(limit).execute()
    return [
        {
            **row,
            "stale_reason": "event_expired",
        }
        for row in (r.data or [])
    ]


def refresh_freshness_metrics() -> Dict[str, Any]:
    """Compute and persist freshness snapshot (global scope)."""
    supabase = _get_supabase()
    signals = get_source_freshness_signals()
    fresh = sum(1 for s in signals if s.get("freshness_state") == "fresh")
    stale = sum(1 for s in signals if s.get("freshness_state") == "stale")
    overdue = sum(1 for s in signals if s.get("freshness_state") == "overdue")

    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        changes_r = (
            supabase.table("document_change_events")
            .select("id", count="exact")
            .gte("detected_at", since)
            .neq("change_type", "unchanged")
            .limit(1)
            .execute()
        )
        changes_count = changes_r.count if hasattr(changes_r, "count") and changes_r.count is not None else 0
    except Exception:
        changes_count = 0

    try:
        needs_review_res = (
            supabase.table("staged_resource_candidates")
            .select("id", count="exact")
            .in_("status", ["new", "needs_review"])
            .limit(1)
            .execute()
        )
        needs_review_res_count = needs_review_res.count if hasattr(needs_review_res, "count") else 0
    except Exception:
        needs_review_res_count = 0
    try:
        needs_review_ev = (
            supabase.table("staged_event_candidates")
            .select("id", count="exact")
            .in_("status", ["new", "needs_review"])
            .limit(1)
            .execute()
        )
        needs_review_ev_count = needs_review_ev.count if hasattr(needs_review_ev, "count") else 0
    except Exception:
        needs_review_ev_count = 0
    needs_review = (needs_review_res_count or 0) + (needs_review_ev_count or 0)

    stale_resources = get_stale_live_resources(limit=1000)
    stale_events = get_stale_live_events(limit=1000)

    snapshot = {
        "snapshot_scope_type": "global",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "fresh_sources_count": fresh,
        "stale_sources_count": stale,
        "overdue_sources_count": overdue,
        "documents_changed_recently_count": changes_count,
        "live_resources_stale_count": len(stale_resources),
        "live_events_expired_count": len(stale_events),
        "needs_review_candidates_count": needs_review,
        "metrics_json": {
            "source_signals_count": len(signals),
        },
    }
    supabase.table("freshness_snapshots").insert(snapshot).execute()
    return snapshot


def get_freshness_overview() -> Dict[str, Any]:
    """Get latest freshness overview for dashboard."""
    supabase = _get_supabase()
    latest = (
        supabase.table("freshness_snapshots")
        .select("*")
        .eq("snapshot_scope_type", "global")
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
    ).data
    snapshot = (latest or [{}])[0] if latest else {}

    schedules = (
        supabase.table("crawl_schedules")
        .select("id, next_run_at, is_active")
        .eq("is_active", True)
        .execute()
    ).data or []
    now = datetime.now(timezone.utc)
    due = sum(1 for s in schedules if s.get("next_run_at") and s["next_run_at"] <= now.isoformat())
    overdue = due
    active = len(schedules)

    job_runs_24h = (
        supabase.table("crawl_job_runs")
        .select("id, status")
        .gte("created_at", (now - timedelta(hours=24)).isoformat())
        .execute()
    ).data or []
    success_24h = sum(1 for j in job_runs_24h if j.get("status") in ("succeeded", "partial_success"))
    failed_24h = sum(1 for j in job_runs_24h if j.get("status") == "failed")

    return {
        "active_schedules_count": active,
        "due_schedules_count": due,
        "overdue_schedules_count": overdue,
        "last_24h_crawl_success_count": success_24h,
        "last_24h_crawl_failure_count": failed_24h,
        "documents_changed_recently": snapshot.get("documents_changed_recently_count", 0),
        "new_staged_resources_pending": snapshot.get("needs_review_candidates_count", 0),
        "live_resources_stale_count": snapshot.get("live_resources_stale_count", 0),
        "live_events_expired_count": snapshot.get("live_events_expired_count", 0),
        "fresh_sources_count": snapshot.get("fresh_sources_count", 0),
        "stale_sources_count": snapshot.get("stale_sources_count", 0),
        "overdue_sources_count": snapshot.get("overdue_sources_count", 0),
        "snapshot_captured_at": snapshot.get("captured_at"),
    }


def get_freshness_by_country() -> List[Dict[str, Any]]:
    """Aggregate freshness by country."""
    signals = get_source_freshness_signals()
    by_country: Dict[str, Dict] = {}
    for s in signals:
        cc = s.get("country_code") or "unknown"
        if cc not in by_country:
            by_country[cc] = {
                "country_code": cc,
                "fresh_count": 0,
                "stale_count": 0,
                "overdue_count": 0,
                "sources": [],
            }
        state = s.get("freshness_state", "unknown")
        if state == "fresh":
            by_country[cc]["fresh_count"] += 1
        elif state in ("stale", "warning"):
            by_country[cc]["stale_count"] += 1
        elif state == "overdue":
            by_country[cc]["overdue_count"] += 1
        by_country[cc]["sources"].append(s.get("source_name"))
    return list(by_country.values())


def get_freshness_by_source() -> List[Dict[str, Any]]:
    """Get per-source freshness."""
    return get_source_freshness_signals()
