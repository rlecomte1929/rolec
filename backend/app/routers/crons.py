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

POST /api/crons/task-reminders
    Runs the employee-task D-7 / D-3 / D-0 reminder job (AIQ-76).
    Designed to be called daily at 08:00 UTC.

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

from ..services.dossier_notifications import run_deadline_reminder_cron
from ..services.employee_task_reminders import run_task_reminder_cron

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


@router.post("/task-reminders")
def task_reminders(request: Request) -> Dict[str, Any]:
    """
    Daily employee-task reminder cron (AIQ-76).
    Sends D-7 / D-3 / D-0 reminders for employee_tasks with a due_date in those
    windows, one consolidated email per employee per window. D-0 also notifies
    the case HR owner. Stamps reminded_d{7,3,0}_at to prevent duplicates.
    """
    _verify_cron_secret(request)
    log.info("task_reminders cron triggered")
    result = run_task_reminder_cron()
    return {"ok": True, **result}
