"""
[AIQ-656] Event-driven case milestone reminders (D-7 / D-3 / D-0).

Replaces the AIQ-34-D cron design. A backend cron endpoint
(POST /api/crons/milestone-reminders, scheduled hourly via pg_cron) calls
run_milestone_reminder_cron(), which scans public.case_milestones for any
milestone whose target_date is exactly 7, 3, or 0 days out and, for each,
writes one public.notification_outbox row (the AIQ-13-E delivery pattern).

Idempotency
-----------
public.case_milestone_reminders has PK (milestone_id, day_offset). The scan
skips milestones already recorded there, and the insert is ON-CONFLICT-safe,
so a milestone never double-fires for the same offset regardless of cadence.

Recipient
---------
Resolved from the milestone's case (public.cases joined on case_id OR
canonical_case_id) and the `owner` column:
  owner='hr'  -> HR owner ;  otherwise -> the employee (the actor on the step).
Resolution is fail-soft: a milestone with no resolvable email is skipped.

All functions are fire-and-forget — they never raise to the caller.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)

# Days-before-target_date offsets to remind on.
OFFSETS = (7, 3, 0)

NOTIFICATION_TYPE = "milestone.reminder"


def _main_db():
    from ....database import db  # type: ignore[import]
    return db


def _engine():
    return _main_db().engine


def _t(name: str) -> str:
    """Schema-qualified on Postgres, bare on SQLite (matches dossier_notifications)."""
    try:
        dialect = _engine().dialect.name
    except Exception:
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


def _date_in_n_days(n: int) -> str:
    """ISO date string for today + n days (UTC). Computed in Python so the
    query is identical on Postgres and SQLite (no DB date math)."""
    return (datetime.now(timezone.utc).date() + timedelta(days=n)).isoformat()


def _due_milestones(offset: int) -> List[Dict[str, Any]]:
    """Milestones whose target_date == today+offset, not finished, and not yet
    reminded for this offset."""
    target = _date_in_n_days(offset)
    q = f"""
        SELECT cm.id            AS milestone_id,
               cm.case_id,
               cm.canonical_case_id,
               cm.title,
               cm.milestone_type,
               cm.target_date,
               cm.owner,
               c.employee_id     AS employee_id,
               c.hr_owner_id      AS hr_owner_id,
               pe.email           AS employee_email,
               ph.email           AS hr_email
        FROM {_t('case_milestones')} cm
        LEFT JOIN {_t('cases')} c
               ON c.id = cm.case_id OR c.id = cm.canonical_case_id
        LEFT JOIN {_t('profiles')} pe ON pe.id = c.employee_id
        LEFT JOIN {_t('profiles')} ph ON ph.id = c.hr_owner_id
        WHERE cm.target_date = :target
          AND cm.status NOT IN ('done', 'skipped')
          AND cm.id NOT IN (
                SELECT milestone_id FROM {_t('case_milestone_reminders')}
                WHERE day_offset = :offset
          )
    """
    try:
        with _engine().connect() as conn:
            rows = conn.execute(
                _sql_text(q), {"target": target, "offset": offset}
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        log.error("milestone_reminders: query failed offset=%d: %s", offset, exc)
        return []


def _resolve_recipient(m: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Pick the recipient (user_id + email) for a milestone. Fail-soft."""
    owner = (m.get("owner") or "").lower()
    if owner == "hr" and m.get("hr_email"):
        return {"user_id": str(m["hr_owner_id"]), "email": m["hr_email"]}
    # Default (employee-owned, joint, or unknown): notify the employee.
    if m.get("employee_email"):
        return {"user_id": str(m["employee_id"]), "email": m["employee_email"]}
    # Fall back to HR if the employee has no email but HR does.
    if m.get("hr_email"):
        return {"user_id": str(m["hr_owner_id"]), "email": m["hr_email"]}
    return None


def _label(offset: int) -> str:
    if offset == 0:
        return "due today"
    return f"due in {offset} day{'s' if offset != 1 else ''}"


def _emit(m: Dict[str, Any], offset: int, recipient: Dict[str, str]) -> bool:
    """Write the outbox row + the idempotency ledger row in one transaction.
    Returns True if a reminder was emitted."""
    milestone_id = str(m["milestone_id"])
    payload = {
        "milestone_id": milestone_id,
        "case_id": m.get("case_id"),
        "milestone_type": m.get("milestone_type"),
        "title": m.get("title"),
        "target_date": str(m.get("target_date")),
        "day_offset": offset,
        "idempotency_key": f"{milestone_id}:{offset}",
        # Brand-voice subject line: clear, calm, specific (relopass-brand-voice).
        "subject": f"Reminder: \"{m.get('title')}\" is {_label(offset)}",
    }
    try:
        with _engine().begin() as conn:
            conn.execute(
                _sql_text(
                    f"INSERT INTO {_t('notification_outbox')} "
                    "(id, notification_id, user_id, to_email, type, payload, status) "
                    "VALUES (:id, NULL, :uid, :email, :type, "
                    + ("CAST(:payload AS jsonb)" if _engine().dialect.name == "postgresql" else ":payload")
                    + ", 'pending')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "uid": recipient["user_id"],
                    "email": recipient["email"],
                    "type": NOTIFICATION_TYPE,
                    "payload": json.dumps(payload),
                },
            )
            conn.execute(
                _sql_text(
                    f"INSERT INTO {_t('case_milestone_reminders')} "
                    "(milestone_id, day_offset, recipient_user_id, to_email) "
                    "VALUES (:mid, :off, :uid, :email)"
                    + (
                        " ON CONFLICT (milestone_id, day_offset) DO NOTHING"
                        if _engine().dialect.name == "postgresql"
                        else ""
                    )
                ),
                {
                    "mid": milestone_id,
                    "off": offset,
                    "uid": recipient["user_id"],
                    "email": recipient["email"],
                },
            )
        return True
    except Exception as exc:  # noqa: BLE001
        # On SQLite the ledger INSERT may raise IntegrityError on a concurrent
        # double-run; treat as already-sent (idempotent), not an error.
        log.warning("milestone_reminders: emit skipped mid=%s off=%d: %s",
                    milestone_id, offset, exc)
        return False


def run_milestone_reminder_cron() -> Dict[str, Any]:
    """Scan all three offsets, emit reminders, return a summary.

    {checked: int, reminded: int, skipped_no_recipient: int}
    """
    checked = 0
    reminded = 0
    skipped = 0
    for offset in OFFSETS:
        for m in _due_milestones(offset):
            checked += 1
            recipient = _resolve_recipient(m)
            if not recipient:
                skipped += 1
                log.info("milestone_reminders: no recipient for milestone=%s",
                         m.get("milestone_id"))
                continue
            if _emit(m, offset, recipient):
                reminded += 1
    log.info("milestone_reminders: checked=%d reminded=%d skipped=%d",
             checked, reminded, skipped)
    return {"checked": checked, "reminded": reminded, "skipped_no_recipient": skipped}
