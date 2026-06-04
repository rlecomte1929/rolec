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
    return {
        "ok": True,
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
