"""
Admin Freshness & Crawl API - Admin-only endpoints for crawl scheduling,
change detection, and freshness monitoring. No auto-publish.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ...database import db
from ...services.change_detection_service import (
    get_document_change,
    list_document_changes,
)
from ...services.crawl_scheduler_service import (
    create_job_run,
    acquire_job_lock,
    complete_job_run,
    create_schedule,
    get_due_schedules,
    get_job_run,
    list_job_runs,
    list_schedules,
    pause_schedule,
    process_due_schedules,
    resume_schedule,
    run_crawl_for_scope,
    trigger_schedule_now,
    update_schedule,
)
from ...services.freshness_service import (
    get_freshness_by_country,
    get_freshness_by_source,
    get_freshness_overview,
    get_stale_live_events,
    get_stale_live_resources,
    refresh_freshness_metrics,
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


router = APIRouter(prefix="/freshness", tags=["admin-freshness"])
crawl_router = APIRouter(prefix="/crawl", tags=["admin-crawl"])
changes_router = APIRouter(prefix="/changes", tags=["admin-changes"])


# --- Freshness overview ---
@router.get("/overview")
def get_overview(user: Dict[str, Any] = Depends(_require_admin)):
    return get_freshness_overview()


@router.get("/countries")
def get_countries(user: Dict[str, Any] = Depends(_require_admin)):
    return {"items": get_freshness_by_country()}


@router.get("/cities")
def get_cities(
    country_code: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_admin),
):
    signals = get_freshness_by_source()
    by_city: Dict[str, Dict] = {}
    for s in signals:
        if country_code and s.get("country_code") != country_code:
            continue
        key = f"{s.get('country_code', '')}:{s.get('city_name', '') or 'unknown'}"
        if key not in by_city:
            by_city[key] = {
                "country_code": s.get("country_code"),
                "city_name": s.get("city_name") or "unknown",
                "fresh_count": 0,
                "stale_count": 0,
                "overdue_count": 0,
            }
        state = s.get("freshness_state", "unknown")
        if state == "fresh":
            by_city[key]["fresh_count"] += 1
        elif state in ("stale", "warning"):
            by_city[key]["stale_count"] += 1
        elif state == "overdue":
            by_city[key]["overdue_count"] += 1
    return {"items": list(by_city.values())}


@router.get("/sources")
def get_sources(user: Dict[str, Any] = Depends(_require_admin)):
    return {"items": get_freshness_by_source()}


@router.post("/refresh")
def post_refresh(user: Dict[str, Any] = Depends(_require_admin)):
    return refresh_freshness_metrics()


# --- Crawl schedules ---
@crawl_router.get("/schedules")
def get_schedules(
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100, le=200),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return {"items": list_schedules(is_active=is_active, limit=limit)}


@crawl_router.get("/schedules/due")
def get_due(user: Dict[str, Any] = Depends(_require_admin)):
    return {"items": get_due_schedules()}


@crawl_router.get("/schedules/{schedule_id}")
def get_schedule_detail(
    schedule_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    from ...services.crawl_scheduler_service import get_schedule
    s = get_schedule(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@crawl_router.post("/schedules")
def post_create_schedule(
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    name = payload.get("name")
    schedule_type = payload.get("schedule_type", "interval")
    schedule_expression = payload.get("schedule_expression", "24")
    source_scope_type = payload.get("source_scope_type", "source")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    return create_schedule(
        name=name,
        schedule_type=schedule_type,
        schedule_expression=schedule_expression,
        source_scope_type=source_scope_type,
        source_scope_ref=payload.get("source_scope_ref"),
        country_code=payload.get("country_code"),
        city_name=payload.get("city_name"),
        content_domain=payload.get("content_domain"),
        priority=payload.get("priority", 0),
        max_runtime_seconds=payload.get("max_runtime_seconds"),
        retry_policy=payload.get("retry_policy"),
        user_id=user.get("id"),
    )


@crawl_router.put("/schedules/{schedule_id}")
def put_schedule(
    schedule_id: str,
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    s = update_schedule(
        schedule_id,
        is_active=payload.get("is_active"),
        schedule_type=payload.get("schedule_type"),
        schedule_expression=payload.get("schedule_expression"),
        user_id=user.get("id"),
    )
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@crawl_router.post("/schedules/{schedule_id}/pause")
def post_pause_schedule(
    schedule_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    s = pause_schedule(schedule_id, user_id=user.get("id"))
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@crawl_router.post("/schedules/{schedule_id}/resume")
def post_resume_schedule(
    schedule_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    s = resume_schedule(schedule_id, user_id=user.get("id"))
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@crawl_router.post("/schedules/{schedule_id}/trigger")
def post_trigger_schedule(
    schedule_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    s = trigger_schedule_now(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@crawl_router.post("/process-due")
def post_process_due(user: Dict[str, Any] = Depends(_require_admin)):
    """Process all due schedules. Call from cron or manually."""
    results = process_due_schedules(user_id=user.get("id"))
    return {"results": results}


@crawl_router.post("/trigger")
def post_trigger_crawl(
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(_require_admin),
):
    """Manually trigger a crawl for the given scope (source, country, city, domain)."""
    source_name = payload.get("source_name")
    country_code = payload.get("country_code")
    city_name = payload.get("city_name")
    content_domain = payload.get("content_domain")
    if not any([source_name, country_code, city_name, content_domain]):
        raise HTTPException(
            status_code=400,
            detail="At least one of source_name, country_code, city_name, content_domain required",
        )
    job = create_job_run(
        job_type="crawl_country_city_scope",
        trigger_type="manual",
        scope={
            "source_name": source_name,
            "country_code": country_code,
            "city_name": city_name,
            "content_domain": content_domain,
        },
        requested_by=user.get("id"),
    )
    if not acquire_job_lock(job["id"]):
        raise HTTPException(status_code=409, detail="Could not acquire job lock")
    try:
        report = run_crawl_for_scope(
            source_name=source_name,
            country_code=country_code,
            city_name=city_name,
            content_domain=content_domain,
        )
        if "error" in report:
            complete_job_run(job["id"], status="failed", error_summary=report.get("error"))
            raise HTTPException(status_code=400, detail=report.get("error"))
        complete_job_run(
            job["id"],
            status="succeeded" if not report.get("errors") else "partial_success",
            crawl_run_id=report.get("run_id"),
            documents_fetched=report.get("documents_fetched", 0),
            chunks_created=report.get("chunks_created", 0),
            staged_resources=report.get("resources_staged", 0),
            staged_events=report.get("events_staged", 0),
            errors=len(report.get("errors", [])),
            summary=report,
        )
        try:
            from ...services.change_detection_service import run_change_detection_for_crawl_run
            from ...services.freshness_service import refresh_freshness_metrics
            run_change_detection_for_crawl_run(report.get("run_id"), job_run_id=job["id"])
            refresh_freshness_metrics()
        except Exception:
            pass
        return {"job_run_id": job["id"], "crawl_run_id": report.get("run_id"), "report": report}
    except HTTPException:
        raise
    except Exception as e:
        complete_job_run(job["id"], status="failed", error_summary=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@crawl_router.get("/job-runs")
def get_job_runs(
    schedule_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_job_runs(schedule_id=schedule_id, status=status, limit=limit, offset=offset)


@crawl_router.get("/job-runs/{job_run_id}")
def get_job_run_detail(
    job_run_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    j = get_job_run(job_run_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job run not found")
    return j


# --- Change detection ---
@changes_router.get("/documents")
def get_document_changes(
    job_run_id: Optional[str] = Query(None),
    source_name: Optional[str] = Query(None),
    change_type: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return list_document_changes(
        job_run_id=job_run_id,
        source_name=source_name,
        change_type=change_type,
        since=since,
        limit=limit,
        offset=offset,
    )


@changes_router.get("/documents/{change_id}")
def get_document_change_detail(
    change_id: str,
    user: Dict[str, Any] = Depends(_require_admin),
):
    c = get_document_change(change_id)
    if not c:
        raise HTTPException(status_code=404, detail="Change event not found")
    return c


@changes_router.get("/live-stale-resources")
def get_live_stale_resources(
    country_code: Optional[str] = Query(None),
    city_name: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return {"items": get_stale_live_resources(country_code=country_code, city_name=city_name, limit=limit)}


@changes_router.get("/live-stale-events")
def get_live_stale_events(
    country_code: Optional[str] = Query(None),
    city_name: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    user: Dict[str, Any] = Depends(_require_admin),
):
    return {"items": get_stale_live_events(country_code=country_code, city_name=city_name, limit=limit)}
