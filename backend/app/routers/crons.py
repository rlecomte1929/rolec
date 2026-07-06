"""
[P4-4] Cron endpoints — HTTP triggers for scheduled jobs.

Security: every endpoint requires the Authorization header to match
CRON_SECRET env var.  Set this to the same value in your Supabase
pg_cron net.http_post() call or Vercel Cron job definition.

Endpoints
---------
POST /api/crons/deadline-reminder
    Runs the 7-day deadline reminder job.
    Designed to be called daily at 08:00 CET.
POST /api/crons/process-crawl-schedules
    [P3-02a] Runs all due source-monitoring crawl schedules with retry +
    exponential backoff. Designed to be called daily (e.g. 03:00 UTC) by the
    `.github/workflows/crawl-scheduler.yml` GitHub Actions cron.
    [AIQ-872] Also fires notify_superseded_rules() on this same daily tick so
    superseded-rule notifications reach affected open cases within 24h with no
    admin action (completes AIQ-642's manual-only notifier). Idempotent.

Example Supabase pg_cron setup (run once after deployment):
    SELECT cron.schedule(
      'deadline-reminder',
      '0 7 * * *',   -- 07:00 UTC = 08:00 CET (winter) / 09:00 CEST (summer)
      $$
        SELECT net.http_post(
          url      := 'https://api.relopass.com/api/crons/deadline-reminder',
          headers  := '{"Authorization": "Bearer <CRON_SECRET>"}'::jsonb,
          body     := '{}'::jsonb
        )
      $$
    );
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.crawl_scheduler_service import process_due_schedules
from ..services.dossier_notifications import run_deadline_reminder_cron
from ..services.milestone_reminders import run_milestone_reminder_cron
from ..services.monitoring_alerts import send_test_alert
from ..services.rule_change_notifier import notify_superseded_rules
from ..services.source_reliability_service import recompute_reliability_scores
from ..services.vendor_metric_snapshot_service import snapshot_vendor_metrics
from ..services.weekly_mobility_status import run_weekly_mobility_status_cron

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crons", tags=["crons"])


def _verify_cron_secret(request: Request) -> None:
    expected = os.getenv("CRON_SECRET", "")
    if not expected:
        # If CRON_SECRET is not configured, block the endpoint entirely so it
        # cannot be called accidentally in production without a secret.
        log.warning("CRON_SECRET not set — cron endpoint rejected")
        raise HTTPException(status_code=503, detail="Cron endpoint not configured")
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid cron secret")


class CanaryBody(BaseModel):
    failing_requests: Optional[list] = None
    client_context: Optional[Dict[str, Any]] = None
    base_url: Optional[str] = None
    health_path: str = "/health"
    auth_token: Optional[str] = None
    dry_run: bool = False


@router.post("/autopilot-canary")
def autopilot_canary(request: Request, body: CanaryBody) -> Dict[str, Any]:
    """[Autopilot P0] Post-deploy diagnostics-replay canary. Read-only: replays only the
    idempotent (GET/HEAD) failing requests recorded in a feedback item's client_context and
    reports whether the signal is resolved. Not yet wired into auto-merge (that is Phase 2,
    which will call notion_work_queue.set_validation_result with the outcome)."""
    _verify_cron_secret(request)
    from ..services import autopilot_canary as canary

    reqs = body.failing_requests
    if reqs is None:
        reqs = canary.failing_requests_from_context(body.client_context)

    if body.dry_run:
        base = (body.base_url or canary.prod_base_url()).rstrip("/")
        return {
            "dry_run": True,
            "base_url": base,
            "health_path": body.health_path,
            "would_replay": [
                {"method": (r.get("method") or "GET").upper(), "path": r.get("path"), "was": r.get("status")}
                for r in reqs
            ],
        }

    result = canary.run_canary(
        failing_requests=reqs,
        base_url=body.base_url,
        health_path=body.health_path,
        auth_token=body.auth_token,
    )
    return {"dry_run": False, **result.as_dict()}


class AutopilotEventBody(BaseModel):
    event_type: str
    entity_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


@router.post("/autopilot-event")
def autopilot_event(request: Request, body: AutopilotEventBody) -> Dict[str, Any]:
    """[Autopilot P2] Record one autopilot funnel event (fired by the autofix-validate workflow)
    into public.events, so the metrics dashboard sees the CI-side stages — merged / canary /
    reverted / task_done — that the backend can't observe on its own."""
    _verify_cron_secret(request)
    from ..services import autopilot_events as ev

    if body.event_type not in ev.ALL_EVENTS:
        raise HTTPException(status_code=422, detail=f"unknown autopilot event_type {body.event_type!r}")
    ev.emit(body.event_type, entity_id=body.entity_id, properties=body.properties)
    return {"recorded": True, "event_type": body.event_type}


class IngestBody(BaseModel):
    dry_run: bool = False
    lookback_hours: int = 24


@router.post("/autopilot-ingest")
def autopilot_ingest(request: Request, body: IngestBody) -> Dict[str, Any]:
    """[Autopilot P1] Nightly feedback → dedup (by error fingerprint) → engineered Notion task.
    Governor-gated (AUTOPILOT_ENABLED + per-stage flag + monthly-USD cap, all default OFF), capped
    per night, cost-traced, dry-run capable. A no-op that returns {halted:true} until the flags
    are on, so scheduling it is safe before go-live."""
    _verify_cron_secret(request)
    from ..services.autopilot_ingest import run_ingest

    return run_ingest(dry_run=body.dry_run, lookback_hours=body.lookback_hours)


@router.post("/deadline-reminder")
def deadline_reminder(request: Request) -> Dict[str, Any]:
    """
    Daily 7-day deadline reminder cron.
    Finds case_forms with deadline = today+7, deadline_reminded_at IS NULL.
    Sends in-app + email to Employee and Specialist.
    Stamps deadline_reminded_at to prevent duplicates.
    """
    _verify_cron_secret(request)
    log.info("deadline_reminder cron triggered")
    result = run_deadline_reminder_cron()
    return {"ok": True, **result}


@router.post("/milestone-reminders")
def milestone_reminders(request: Request) -> Dict[str, Any]:
    """
    [AIQ-656] Milestone D-7/D-3/D-0 reminder cron (scheduled hourly via pg_cron).
    Scans case_milestones for target_date = today + 7/3/0 days and writes one
    notification_outbox row per due milestone. Idempotent on (milestone_id,
    day_offset) via public.case_milestone_reminders, so re-runs never duplicate.
    """
    _verify_cron_secret(request)
    log.info("milestone_reminders cron triggered")
    result = run_milestone_reminder_cron()
    return {"ok": True, **result}


@router.post("/weekly-mobility-status")
def weekly_mobility_status(request: Request) -> Dict[str, Any]:
    """
    [AIQ-1237] Weekly mobility status check (scheduled Mondays 08:00 UTC via
    GitHub Actions / pg_cron). Finds overdue case_milestones (target_date <
    today, not done/skipped) on active cases, groups them by HR owner, and
    emails each HR owner one digest of their overdue relocation steps. Reads
    only; never raises; with no RESEND_API_KEY the digest is logged, not sent.
    """
    _verify_cron_secret(request)
    log.info("weekly_mobility_status cron triggered")
    result = run_weekly_mobility_status_cron()
    return {"ok": True, **result}


@router.post("/process-crawl-schedules")
def process_crawl_schedules(request: Request) -> Dict[str, Any]:
    """
    [P3-02a] Production source-monitoring scheduler trigger.
    Processes every due crawl schedule (next_run_at <= now, active), each fetch
    using 3-retry exponential backoff on transient failures. Per-schedule job
    locks prevent concurrent runs. Never raises on individual schedule failure —
    failures are logged on the job run so the cron stays green.
    """
    _verify_cron_secret(request)
    log.info("process_crawl_schedules cron triggered")
    results = process_due_schedules(user_id="cron")
    succeeded = sum(1 for r in results if r.get("status") == "succeeded")
    failed = sum(1 for r in results if r.get("status") == "failed")

    # [AIQ-872 / P1-08d-followup] Piggyback the rule-change notifier on this daily
    # tick so affected open cases learn of a superseded rule within 24h with NO
    # admin action — completing AIQ-642 (which shipped notify_superseded_rules()
    # admin-trigger-only). It's idempotent (per case, prior rule_version) and
    # non-fatal here: a notifier error must never fail the crawl cron.
    try:
        rule_change_notifications: Dict[str, Any] = notify_superseded_rules()
    except Exception:
        log.exception("process_crawl_schedules: rule-change notifier failed")
        rule_change_notifications = {"error": "notifier_failed"}

    return {
        "ok": True,
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
        "rule_change_notifications": rule_change_notifications,
    }


@router.post("/snapshot-vendor-metrics")
def snapshot_vendor_metrics_cron(request: Request) -> Dict[str, Any]:
    """
    [NAV-SP-2 Tier 3] Daily snapshot of per-supplier-per-category aggregates
    (rating, cost, review_count) into vendor_metric_snapshots, powering the Vendor
    Performance trend charts and watchlist deltas. Idempotent per (supplier,
    category, day) — safe to re-run. Designed to run daily (e.g. 05:30 UTC).
    """
    _verify_cron_secret(request)
    log.info("snapshot_vendor_metrics cron triggered")
    result = snapshot_vendor_metrics()
    return {"ok": True, **result}


@router.post("/recompute-source-reliability")
def recompute_source_reliability(request: Request) -> Dict[str, Any]:
    """
    [N8/AIQ-848] Nightly recompute of immigration_corpus_chunks.reliability_score
    from the feedback loop (cited chunks in rejected answers get down-ranked).
    Full recompute — idempotent. Designed to be called daily (e.g. 02:00 UTC).
    Staleness of up to 24h is acceptable, so this is never run synchronously on an
    answer. See backend/app/services/source_reliability_service.py.
    """
    _verify_cron_secret(request)
    log.info("recompute_source_reliability cron triggered")
    result = recompute_reliability_scores()
    return {"ok": True, **result}


@router.post("/test-monitoring-alert")
def test_monitoring_alert(request: Request) -> Dict[str, Any]:
    """
    [P3-02c] Fire a test source-monitoring alert through Slack + email.
    Used to validate the webhook wiring in staging — a message should land in
    the configured test channel.
    """
    _verify_cron_secret(request)
    log.info("test_monitoring_alert cron triggered")
    result = send_test_alert()
    return {"ok": True, **result}


@router.post("/case-health-scan")
def case_health_scan(request: Request) -> Dict[str, Any]:
    """
    [AIQ-378b] Nightly proactive case-health scan. Flags active immigration cases
    past their expected milestone date (AIQ-378a signal) and raises one deduped
    HR alert per behind-schedule case (ops-notification + best-effort Slack/email).
    Read-only on case data; inert until the pilot populates case milestones.
    Daily via `.github/workflows/case-health-scan.yml`, gated behind the
    `CASE_HEALTH_CRON_ENABLED` repo var. Idempotent (per-case dedupe).
    """
    _verify_cron_secret(request)
    log.info("case_health_scan cron triggered")
    from ..services.case_health_scan import run_case_health_scan

    result = run_case_health_scan()
    return {"ok": True, **result}


@router.post("/coordinator-proactive-scan")
def coordinator_proactive_scan(request: Request) -> Dict[str, Any]:
    """
    [AIQ-1414 Phase 3b] Proactive Mobility Coordinator scan. For each active coordinator
    session, delivers one in-session proactive update when new notify-worthy case_events
    landed since the session's cursor, and closes sessions whose case is terminal.
    Breaker-aware (skips relocations over their monthly cap). Inert while
    RELOPASS_AI_COORDINATOR_ENABLED is OFF. Daily via
    `.github/workflows/coordinator-proactive-scan.yml`, gated behind the
    `COORDINATOR_PROACTIVE_CRON_ENABLED` repo var. Idempotent (cursor-advanced).
    """
    _verify_cron_secret(request)
    log.info("coordinator_proactive_scan cron triggered")
    from ..services.coordinator_proactive_service import run_coordinator_proactive_scan

    return run_coordinator_proactive_scan()


@router.post("/hr-mobility-briefing")
def hr_mobility_briefing_cron(
    request: Request,
    dry_run: bool = False,
    only_company_id: Optional[str] = None,
    to_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [AIQ-1220] Weekly HR mobility briefing. Emails each active HR company's admin a
    deterministic, data-driven summary: active assignments + status, at-risk
    relocations, and upcoming compliance deadlines. NO LLM call (no LLM cost / no
    PII leaving the platform). Sends via Resend, falling back to logging when
    RESEND_API_KEY is unset. Designed to run weekly (Monday 08:00) via
    `.github/workflows/hr-mobility-briefing.yml`.

    Safety params for a targeted beta test:
      * `dry_run`        — compose + return payloads under `previews`, send nothing.
      * `only_company_id`— restrict the run to one company.
      * `to_override`    — send every briefing to this single address (preview it
                           in a tester's inbox instead of each company's admin).
    """
    _verify_cron_secret(request)
    log.info(
        "hr_mobility_briefing cron triggered (dry_run=%s, only_company_id=%s, to_override=%s)",
        dry_run,
        only_company_id,
        bool(to_override),
    )
    from ..services.hr_mobility_briefing_service import run_hr_mobility_briefing

    result = run_hr_mobility_briefing(
        dry_run=dry_run,
        only_company_id=only_company_id,
        to_override=to_override,
    )
    return {"ok": True, **result}


@router.post("/promote-hr-vendors")
def promote_hr_vendors_cron(
    request: Request,
    threshold: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    [CATALOG-2-FU/AIQ-1077] Scheduled automatic promotion of popular HR custom
    vendors into the master catalog. Mirrors the admin-triggered
    POST /api/admin/catalog/promote-hr-vendors, but runs unattended via
    `.github/workflows/catalog-promotion.yml` (daily), gated behind the
    `CATALOG_PROMOTION_CRON_ENABLED` repo var. The service is idempotent —
    vendors already present in the master catalog are skipped, so re-runs never
    duplicate. `threshold`/`dry_run` are query-configurable for manual
    workflow_dispatch testing (default: configured threshold, real run).
    """
    _verify_cron_secret(request)
    log.info(
        "promote_hr_vendors cron triggered (threshold=%s, dry_run=%s)",
        threshold,
        dry_run,
    )
    from ..services.catalog_promotion_service import promote_hr_vendors

    result = promote_hr_vendors(threshold=threshold, dry_run=dry_run, actor_id="cron")
    return {"ok": True, **result}
