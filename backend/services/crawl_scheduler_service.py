"""
Crawl scheduler service: schedule management, job runs, orchestration.
Supports scheduled and manual triggers. No auto-publish.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

_JOB_LOCK_MINUTES = 30  # stale lock threshold
_DEFAULT_CADENCE_DAYS = {
    "events": 1,
    "transport": 2,
    "culture_leisure": 3,
    "admin_essentials": 7,
    "housing": 7,
    "healthcare": 7,
    "schools_childcare": 7,
    "daily_life": 7,
    "community": 7,
    "cost_of_living": 14,
    "safety": 14,
}


def _get_supabase():
    return get_supabase_admin_client()


def _compute_next_run(
    schedule_type: str,
    schedule_expression: str,
    from_time: Optional[datetime] = None,
) -> Optional[datetime]:
    """Compute next run time from expression."""
    from_time = from_time or datetime.now(timezone.utc)
    if schedule_type == "interval":
        try:
            hours = int(schedule_expression.strip())
            return from_time + timedelta(hours=hours)
        except (ValueError, TypeError):
            return from_time + timedelta(days=1)
    if schedule_type == "cron":
        try:
            import croniter
            cron = croniter.croniter(schedule_expression, from_time)
            return cron.get_next(datetime)
        except Exception:
            return from_time + timedelta(days=1)
    return from_time + timedelta(days=1)


def list_schedules(
    is_active: Optional[bool] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List crawl schedules."""
    supabase = _get_supabase()
    q = supabase.table("crawl_schedules").select("*").order("next_run_at", desc=False)
    if is_active is not None:
        q = q.eq("is_active", is_active)
    r = q.limit(limit).execute()
    return r.data or []


def get_schedule(schedule_id: str) -> Optional[Dict[str, Any]]:
    """Get single schedule."""
    supabase = _get_supabase()
    r = supabase.table("crawl_schedules").select("*").eq("id", schedule_id).limit(1).execute()
    return (r.data or [None])[0]


def get_due_schedules() -> List[Dict[str, Any]]:
    """Get schedules due to run (next_run_at <= now, is_active)."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    r = supabase.table("crawl_schedules").select("*").eq("is_active", True).lte("next_run_at", now).execute()
    return r.data or []


def create_schedule(
    name: str,
    schedule_type: str,
    schedule_expression: str,
    source_scope_type: str,
    *,
    source_scope_ref: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    content_domain: Optional[str] = None,
    priority: int = 0,
    max_runtime_seconds: Optional[int] = None,
    retry_policy: Optional[Dict] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new schedule. Sets next_run_at to now (immediately due)."""
    supabase = _get_supabase()
    next_run = _compute_next_run(schedule_type, schedule_expression)
    row = {
        "name": name,
        "is_active": True,
        "schedule_type": schedule_type,
        "schedule_expression": schedule_expression,
        "source_scope_type": source_scope_type,
        "source_scope_ref": source_scope_ref,
        "country_code": country_code,
        "city_name": city_name,
        "content_domain": content_domain,
        "priority": priority,
        "max_runtime_seconds": max_runtime_seconds,
        "retry_policy_json": retry_policy or {},
        "next_run_at": next_run.isoformat() if next_run else None,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }
    r = supabase.table("crawl_schedules").insert(row).execute()
    return (r.data or [{}])[0]


def update_schedule(
    schedule_id: str,
    *,
    is_active: Optional[bool] = None,
    schedule_type: Optional[str] = None,
    schedule_expression: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update schedule. If cadence changed, recompute next_run_at."""
    s = get_schedule(schedule_id)
    if not s:
        return None
    supabase = _get_supabase()
    upd = {"updated_by_user_id": user_id}
    if is_active is not None:
        upd["is_active"] = is_active
    if schedule_type is not None:
        upd["schedule_type"] = schedule_type
    if schedule_expression is not None:
        upd["schedule_expression"] = schedule_expression
    if schedule_type or schedule_expression:
        st = schedule_type or s.get("schedule_type", "interval")
        ex = schedule_expression or s.get("schedule_expression", "24")
        next_run = _compute_next_run(st, ex)
        upd["next_run_at"] = next_run.isoformat() if next_run else None
    supabase.table("crawl_schedules").update(upd).eq("id", schedule_id).execute()
    return get_schedule(schedule_id)


def pause_schedule(schedule_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return update_schedule(schedule_id, is_active=False, user_id=user_id)


def resume_schedule(schedule_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return update_schedule(schedule_id, is_active=True, user_id=user_id)


def trigger_schedule_now(schedule_id: str) -> Optional[Dict[str, Any]]:
    """Set next_run_at to now so it gets picked up immediately."""
    s = get_schedule(schedule_id)
    if not s:
        return None
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("crawl_schedules").update({"next_run_at": now}).eq("id", schedule_id).execute()
    return get_schedule(schedule_id)


def create_job_run(
    job_type: str,
    trigger_type: str = "manual",
    schedule_id: Optional[str] = None,
    scope: Optional[Dict] = None,
    requested_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a job run record."""
    supabase = _get_supabase()
    row = {
        "job_type": job_type,
        "trigger_type": trigger_type,
        "schedule_id": schedule_id,
        "scope_json": scope or {},
        "requested_by_user_id": requested_by,
        "status": "queued",
    }
    r = supabase.table("crawl_job_runs").insert(row).execute()
    return (r.data or [{}])[0]


def acquire_job_lock(job_run_id: str) -> bool:
    """Attempt to acquire lock. Returns True if locked."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc)
    lock_until = (now + timedelta(minutes=_JOB_LOCK_MINUTES)).isoformat()
    r = supabase.table("crawl_job_runs").update({
        "status": "running",
        "started_at": now.isoformat(),
        "lock_until": lock_until,
    }).eq("id", job_run_id).eq("status", "queued").execute()
    return len(r.data or []) > 0


def release_job_lock(job_run_id: str) -> None:
    supabase = _get_supabase()
    supabase.table("crawl_job_runs").update({
        "lock_until": None,
    }).eq("id", job_run_id).execute()


def complete_job_run(
    job_run_id: str,
    status: str = "succeeded",
    *,
    crawl_run_id: Optional[str] = None,
    documents_fetched: Optional[int] = None,
    documents_changed: Optional[int] = None,
    documents_unchanged: Optional[int] = None,
    chunks_created: Optional[int] = None,
    staged_resources: Optional[int] = None,
    staged_events: Optional[int] = None,
    warnings: Optional[int] = None,
    errors: Optional[int] = None,
    summary: Optional[Dict] = None,
    error_summary: Optional[str] = None,
) -> None:
    """Update job run with completion data."""
    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    upd = {
        "status": status,
        "finished_at": now,
        "lock_until": None,
        "crawl_run_id": crawl_run_id,
    }
    if documents_fetched is not None:
        upd["documents_fetched_count"] = documents_fetched
    if documents_changed is not None:
        upd["documents_changed_count"] = documents_changed
    if documents_unchanged is not None:
        upd["documents_unchanged_count"] = documents_unchanged
    if chunks_created is not None:
        upd["chunks_created_count"] = chunks_created
    if staged_resources is not None:
        upd["staged_resources_count"] = staged_resources
    if staged_events is not None:
        upd["staged_events_count"] = staged_events
    if warnings is not None:
        upd["warnings_count"] = warnings
    if errors is not None:
        upd["errors_count"] = errors
    if summary is not None:
        upd["summary_json"] = summary
    if error_summary is not None:
        upd["error_summary"] = error_summary
    supabase.table("crawl_job_runs").update(upd).eq("id", job_run_id).execute()


def update_schedule_after_run(schedule_id: str, success: bool) -> None:
    """Update last_run_at and next_run_at after a run."""
    s = get_schedule(schedule_id)
    if not s:
        return
    supabase = _get_supabase()
    now = datetime.now(timezone.utc)
    next_run = _compute_next_run(
        s.get("schedule_type", "interval"),
        s.get("schedule_expression", "24"),
        from_time=now,
    )
    supabase.table("crawl_schedules").update({
        "last_run_at": now.isoformat(),
        "next_run_at": next_run.isoformat() if next_run else None,
    }).eq("id", schedule_id).execute()


def run_crawl_for_scope(
    source_name: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    content_domain: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute crawler pipeline for the given scope.
    Returns report dict with run_id, counts, errors.
    """
    from backend.crawler.config.models import CrawlConfig
    from backend.crawler.config.registry import load_sources
    from backend.crawler.pipeline import run_pipeline

    sources = load_sources(None)
    if not sources:
        return {"error": "No sources loaded", "run_id": None}

    config = CrawlConfig(sources=sources, dry_run=False, parse_only=False, extract_only=False)
    report = run_pipeline(
        config,
        source_name=source_name,
        country_code=country_code,
        city_name=city_name,
        content_domain=content_domain,
        initiated_by="crawl_scheduler",
    )

    return {
        "run_id": report.run_id,
        "documents_fetched": report.documents_fetched,
        "documents_failed": report.documents_failed,
        "chunks_created": report.chunks_created,
        "resources_staged": report.resources_staged,
        "events_staged": report.events_staged,
        "duplicates_detected": report.duplicates_detected,
        "errors": report.errors,
        "warnings": report.warnings,
    }


def process_due_schedules(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Process all due schedules. Creates job runs, executes crawls, runs change detection.
    Call from cron or manually. Prevents concurrent runs per schedule via lock.
    """
    due = get_due_schedules()
    results = []
    for s in due:
        schedule_id = s["id"]
        scope = {
            "source_scope_type": s.get("source_scope_type"),
            "source_scope_ref": s.get("source_scope_ref"),
            "country_code": s.get("country_code"),
            "city_name": s.get("city_name"),
            "content_domain": s.get("content_domain"),
        }
        job = create_job_run(
            job_type="crawl_source" if s.get("source_scope_type") == "source" else "crawl_country_city_scope",
            trigger_type="scheduled",
            schedule_id=schedule_id,
            scope=scope,
            requested_by=user_id,
        )
        if not acquire_job_lock(job["id"]):
            results.append({"schedule_id": schedule_id, "status": "skipped", "reason": "lock_failed"})
            continue

        try:
            report = run_crawl_for_scope(
                source_name=s.get("source_scope_ref") if s.get("source_scope_type") == "source" else None,
                country_code=s.get("country_code"),
                city_name=s.get("city_name"),
                content_domain=s.get("content_domain"),
            )
            if "error" in report:
                complete_job_run(
                    job["id"],
                    status="failed",
                    error_summary=report.get("error"),
                )
                update_schedule_after_run(schedule_id, False)
                results.append({"schedule_id": schedule_id, "status": "failed", "error": report["error"]})
                continue

            complete_job_run(
                job["id"],
                status="succeeded" if not report.get("errors") else "partial_success",
                crawl_run_id=report.get("run_id"),
                documents_fetched=report.get("documents_fetched", 0),
                chunks_created=report.get("chunks_created", 0),
                staged_resources=report.get("resources_staged", 0),
                staged_events=report.get("events_staged", 0),
                errors=len(report.get("errors", [])),
                warnings=len(report.get("warnings", [])),
                summary=report,
            )
            update_schedule_after_run(schedule_id, not report.get("errors"))

            # Trigger change detection and freshness refresh
            try:
                from .change_detection_service import run_change_detection_for_crawl_run
                from .freshness_service import refresh_freshness_metrics
                run_change_detection_for_crawl_run(report.get("run_id"), job_run_id=job["id"])
                refresh_freshness_metrics()
            except Exception as e:
                log.warning("Change detection or freshness refresh failed: %s", e)

            results.append({
                "schedule_id": schedule_id,
                "job_run_id": job["id"],
                "status": "succeeded",
                "run_id": report.get("run_id"),
            })
        except Exception as e:
            log.exception("Schedule %s failed: %s", schedule_id, e)
            release_job_lock(job["id"])
            complete_job_run(job["id"], status="failed", error_summary=str(e))
            update_schedule_after_run(schedule_id, False)
            results.append({"schedule_id": schedule_id, "status": "failed", "error": str(e)})

    return results


def list_job_runs(
    schedule_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List job runs with total count."""
    supabase = _get_supabase()
    q = supabase.table("crawl_job_runs").select("*", count="exact").order("created_at", desc=True)
    if schedule_id:
        q = q.eq("schedule_id", schedule_id)
    if status:
        q = q.eq("status", status)
    r = q.range(offset, offset + limit - 1).execute()
    return {"items": r.data or [], "total": r.count or 0}


def get_job_run(job_run_id: str) -> Optional[Dict[str, Any]]:
    supabase = _get_supabase()
    r = supabase.table("crawl_job_runs").select("*").eq("id", job_run_id).limit(1).execute()
    return (r.data or [None])[0]
