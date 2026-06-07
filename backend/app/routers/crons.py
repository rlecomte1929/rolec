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
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from ..services.crawl_scheduler_service import process_due_schedules
from ..services.dossier_notifications import run_deadline_reminder_cron
from ..services.monitoring_alerts import send_test_alert
from ..services.rule_change_notifier import notify_superseded_rules
from ..services.source_reliability_service import recompute_reliability_scores

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
