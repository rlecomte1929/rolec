"""
Employee task reminder cron (AIQ-76 / AIQ-34-D).

Daily job that scans public.employee_tasks for tasks whose due_date falls in one
of three windows and emails the employee a consolidated reminder with a deep link
back to their task portal (/employee/tasks):

  * D-7  — due in 7 days
  * D-3  — due in 3 days
  * D-0  — due today (also notifies the case HR owner that tasks are due)

Idempotency
-----------
Each window stamps its own column (reminded_d7_at / reminded_d3_at / reminded_d0_at)
on employee_tasks once the reminder is sent, so a task is reminded at most once per
window even if the cron runs more than once a day. Mirrors the
case_forms.deadline_reminded_at pattern in dossier_notifications.py.

Delivery
--------
Email via Resend (RESEND_API_KEY); falls back to INFO logging in dev. In-app
notifications (D-0 only) via main_db.create_notification_with_preferences().
Every email carries an unsubscribe link to the in-app notification settings.

Cron entry point: run_task_reminder_cron(), called by POST /api/crons/task-reminders.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests as http_requests
from sqlalchemy import bindparam as _bindparam
from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)

# Windows: (kind, days_ahead, stamp column).
_WINDOWS: List[Tuple[str, int, str]] = [
    ("d7", 7, "reminded_d7_at"),
    ("d3", 3, "reminded_d3_at"),
    ("d0", 0, "reminded_d0_at"),
]

# Statuses that no longer need a reminder.
_DONE_STATUSES = ("submitted", "approved")


# ---------------------------------------------------------------------------
# Lazy DB helpers (mirror dossier_notifications.py)
# ---------------------------------------------------------------------------

def _main_db():
    from ....database import db  # type: ignore[import]
    return db


def _engine():
    return _main_db().engine


def _t(name: str) -> str:
    """Schema-qualified table name on Postgres, bare name on SQLite."""
    try:
        dialect = _engine().dialect.name
    except Exception:
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


def _app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "https://app.relopass.com")


# ---------------------------------------------------------------------------
# Email (Resend) — mirrors dossier_notifications, plus an unsubscribe footer
# ---------------------------------------------------------------------------

_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,
             Helvetica,Arial,sans-serif;background:#f8fafc;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="width:100%;max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;
                    box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#0b2b43;padding:24px 32px;">
            <span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">
              ReloPass
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <p style="margin:0 0 8px;font-size:22px;font-weight:700;color:#0b2b43;">{title}</p>
            <p style="margin:0 0 16px;font-size:15px;color:#334155;line-height:1.6;">{body}</p>
            {tasks}
            {cta}
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px 24px;border-top:1px solid #f1f5f9;">
            <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.5;">
              You are receiving this because you have open relocation tasks in ReloPass.
              <a href="{unsubscribe_url}" style="color:#94a3b8;text-decoration:underline;">Manage email reminders</a>.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

_CTA_BLOCK = """\
<table cellpadding="0" cellspacing="0">
  <tr>
    <td style="background:#0b2b43;border-radius:6px;padding:12px 24px;">
      <a href="{url}" style="color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;">
        Open my tasks →
      </a>
    </td>
  </tr>
</table>
"""


def _tasks_html(titles: List[str]) -> str:
    if not titles:
        return ""
    items = "".join(
        f'<li style="margin:0 0 6px;font-size:15px;color:#0b2b43;">{t}</li>' for t in titles
    )
    return (
        '<ul style="margin:0 0 24px;padding-left:20px;">' + items + "</ul>"
    )


def _unsubscribe_url() -> str:
    return f"{_app_base_url()}/settings/notifications"


def _send_email(
    to: str,
    subject: str,
    title: str,
    body: str,
    task_titles: List[str],
    cta_url: str,
) -> None:
    """Send one transactional reminder email via Resend. Never raises."""
    cta = _CTA_BLOCK.format(url=cta_url) if cta_url else ""
    unsubscribe = _unsubscribe_url()
    html = _EMAIL_HTML.format(
        title=title,
        body=body,
        tasks=_tasks_html(task_titles),
        cta=cta,
        unsubscribe_url=unsubscribe,
    )
    bullet = "\n".join(f"  - {t}" for t in task_titles)
    plain = (
        f"{title}\n\n{body}\n\n{bullet}\n\n{cta_url}\n\n"
        f"Manage email reminders: {unsubscribe}"
    )
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("EMAIL_FROM", "noreply@relopass.com")
    try:
        if resend_key:
            resp = http_requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                json={"from": from_addr, "to": [to], "subject": subject, "text": plain, "html": html},
                timeout=10,
            )
            if not resp.ok:
                log.error("task_reminders: email delivery failed %s %s", resp.status_code, resp.text[:200])
        else:
            log.info("TASK REMINDER EMAIL (no RESEND_API_KEY): to=%s subject=%r\n%s", to, subject, plain)
    except Exception as exc:  # noqa: BLE001
        log.error("task_reminders: email send error: %s", exc)


def _inapp(user_id: str, type_: str, title: str, body: str, case_id: Optional[str]) -> None:
    """Write one in-app notification row. Never raises."""
    try:
        _main_db().create_notification_with_preferences(
            user_id=user_id,
            type_=type_,
            title=title,
            body=body,
            case_id=case_id,
        )
    except Exception as exc:  # noqa: BLE001
        log.error("task_reminders: in-app write failed user=%s type=%s: %s", user_id, type_, exc)


# ---------------------------------------------------------------------------
# Copy per window
# ---------------------------------------------------------------------------

def _copy(kind: str, count: int) -> Tuple[str, str, str]:
    """Return (subject, title, body) for the given window and task count."""
    plural = "task" if count == 1 else "tasks"
    if kind == "d7":
        subject = f"{count} relocation {plural} due in 7 days"
        title = "You have tasks due in 7 days"
        body = f"You have {count} relocation {plural} due in one week. Please complete the following:"
    elif kind == "d3":
        subject = f"Reminder: {count} relocation {plural} due in 3 days"
        title = "Your tasks are due in 3 days"
        body = f"You have {count} relocation {plural} due in three days. Please complete the following:"
    else:  # d0
        subject = f"{count} relocation {plural} due today"
        title = "Tasks due today"
        body = f"You have {count} relocation {plural} due today. Please complete the following:"
    return subject, title, body


# ---------------------------------------------------------------------------
# Query + cron runner
# ---------------------------------------------------------------------------

def _fetch_due_tasks(target_date: str, stamp_col: str) -> List[Dict[str, Any]]:
    """Task-level rows (with employee + HR context) due on target_date, not yet reminded."""
    q = f"""
        SELECT et.id              AS task_id,
               et.title           AS title,
               et.case_id         AS case_id,
               et.employee_id     AS employee_id,
               pe.full_name       AS employee_name,
               pe.email           AS employee_email,
               c.hr_owner_id      AS hr_owner_id,
               ph.full_name       AS hr_name,
               ph.email           AS hr_email
        FROM {_t('employee_tasks')} et
        LEFT JOIN {_t('cases')} c     ON c.id  = et.case_id
        LEFT JOIN {_t('profiles')} pe ON pe.id = et.employee_id
        LEFT JOIN {_t('profiles')} ph ON ph.id = c.hr_owner_id
        WHERE et.due_date = :target_date
          AND et.status NOT IN ('submitted', 'approved')
          AND et.{stamp_col} IS NULL
    """
    with _engine().connect() as conn:
        rows = conn.execute(_sql_text(q), {"target_date": target_date}).mappings().all()
    return [dict(r) for r in rows]


def _stamp(task_ids: List[str], stamp_col: str) -> None:
    if not task_ids:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _engine().begin() as conn:
            conn.execute(
                _sql_text(
                    f"UPDATE {_t('employee_tasks')} SET {stamp_col} = :now "
                    f"WHERE id IN :ids"
                ).bindparams(_bindparam("ids", expanding=True)),
                {"now": now_iso, "ids": task_ids},
            )
    except Exception as exc:  # noqa: BLE001
        log.error("task_reminders: stamp failed col=%s: %s", stamp_col, exc)


def _process_window(kind: str, days: int, stamp_col: str) -> Dict[str, int]:
    """Send reminders for a single window. Returns {checked, reminded, errors}."""
    target_date = (date.today() + timedelta(days=days)).isoformat()
    try:
        rows = _fetch_due_tasks(target_date, stamp_col)
    except Exception as exc:  # noqa: BLE001
        log.error("task_reminders: query failed kind=%s: %s", kind, exc)
        return {"checked": 0, "reminded": 0, "errors": 1}

    # Group by (employee_id, case_id) so each employee gets one consolidated email.
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (str(r.get("employee_id")), str(r.get("case_id")))
        groups.setdefault(key, []).append(r)

    reminded = 0
    errors = 0
    cta_url = f"{_app_base_url()}/employee/tasks"

    for (_emp_id, case_id), grp in groups.items():
        first = grp[0]
        titles = [str(t.get("title") or "Untitled task") for t in grp]
        task_ids = [str(t.get("task_id")) for t in grp]
        subject, title, body = _copy(kind, len(grp))
        try:
            if first.get("employee_email"):
                _send_email(
                    to=str(first["employee_email"]),
                    subject=subject,
                    title=title,
                    body=body,
                    task_titles=titles,
                    cta_url=cta_url,
                )
            if kind == "d0":
                emp_id = str(first.get("employee_id"))
                _inapp(emp_id, "task.reminder_d0", title, body, case_id)
                hr_id = first.get("hr_owner_id")
                if hr_id:
                    emp_label = first.get("employee_name") or "An employee"
                    hr_title = f"{emp_label} has {len(grp)} task(s) due today"
                    hr_body = "Relocation tasks are due today and still open: " + ", ".join(titles) + "."
                    _inapp(str(hr_id), "task.reminder_hr_d0", hr_title, hr_body, case_id)
                    if first.get("hr_email"):
                        _send_email(
                            to=str(first["hr_email"]),
                            subject=hr_title,
                            title="Employee tasks due today",
                            body=hr_body,
                            task_titles=titles,
                            cta_url=cta_url,
                        )
            _stamp(task_ids, stamp_col)
            reminded += len(grp)
        except Exception as exc:  # noqa: BLE001
            log.error("task_reminders: group error kind=%s case=%s: %s", kind, case_id, exc)
            errors += 1

    return {"checked": len(rows), "reminded": reminded, "errors": errors}


def run_task_reminder_cron() -> Dict[str, Any]:
    """
    Run all three reminder windows (D-7 / D-3 / D-0).

    Returns a summary dict keyed by window plus a 'totals' rollup, e.g.:
        {"d7": {...}, "d3": {...}, "d0": {...},
         "totals": {"checked": int, "reminded": int, "errors": int}}
    """
    summary: Dict[str, Any] = {}
    totals = {"checked": 0, "reminded": 0, "errors": 0}
    for kind, days, col in _WINDOWS:
        res = _process_window(kind, days, col)
        summary[kind] = res
        for k in totals:
            totals[k] += res[k]
    summary["totals"] = totals
    log.info("task_reminders: %s", totals)
    return summary
