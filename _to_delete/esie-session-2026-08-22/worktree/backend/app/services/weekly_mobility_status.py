"""
[AIQ-1237] Weekly mobility status check.

A backend cron endpoint (POST /api/crons/weekly-mobility-status, scheduled
Mondays 08:00 UTC via GitHub Actions / pg_cron) calls
``run_weekly_mobility_status_cron()``, which:

  1. Finds overdue ``case_milestones`` (target_date < today, status not
     done/skipped) on active ``cases``, joined to the employee + HR owner.
  2. Groups the overdue steps by HR owner.
  3. Emails each HR owner ONE digest listing employee, the overdue step, and
     how many days overdue.

Reads only (writes nothing); fail-soft; never raises to the caller. Email goes
through the shared Resend path (``_resend_send`` in ``assignment_invite_email``);
with no ``RESEND_API_KEY`` the digest is logged at INFO (dev), not sent —
the same posture as every other ReloPass transactional email.

This is the in-repo equivalent of the "Mobility Autopilot" weekly status agent:
it reuses the existing cron/email/milestone infrastructure rather than a hosted
external agent, so it's testable, versioned, and runs on our own data path.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)


def _main_db():
    from ....database import db  # type: ignore[import]
    return db


def _engine():
    return _main_db().engine


def _t(name: str) -> str:
    """Schema-qualified on Postgres, bare on SQLite (matches milestone_reminders)."""
    try:
        dialect = _engine().dialect.name
    except Exception:  # noqa: BLE001
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _overdue_milestones(today: str) -> List[Dict[str, Any]]:
    """Overdue milestones on active cases, with employee + HR-owner context.

    Overdue = target_date strictly before today and not finished. ISO date
    strings compare correctly on both Postgres (date < date) and SQLite
    (lexicographic on 'YYYY-MM-DD'), so no DB-specific date math is needed.
    Fail-soft: any query error yields an empty list (cron stays green).
    """
    q = f"""
        SELECT cm.id            AS milestone_id,
               cm.case_id,
               cm.title,
               cm.target_date,
               c.employee_id,
               c.hr_owner_id,
               pe.full_name      AS employee_name,
               ph.full_name      AS hr_name,
               ph.email          AS hr_email
        FROM {_t('case_milestones')} cm
        JOIN {_t('cases')} c
               ON c.id = cm.case_id OR c.id = cm.canonical_case_id
        LEFT JOIN {_t('profiles')} pe ON pe.id = c.employee_id
        LEFT JOIN {_t('profiles')} ph ON ph.id = c.hr_owner_id
        WHERE cm.target_date < :today
          AND cm.status NOT IN ('done', 'skipped')
          AND c.status = 'active'
          AND c.hr_owner_id IS NOT NULL
    """
    try:
        with _engine().connect() as conn:
            rows = conn.execute(_sql_text(q), {"today": today}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        log.error("weekly_mobility_status: query failed: %s", exc)
        return []


def _days_overdue(target_date: Any, today: date) -> int:
    """Whole days between target_date and today (>= 0). Fail-soft to 0."""
    try:
        if isinstance(target_date, date):
            td = target_date
        else:
            td = datetime.strptime(str(target_date)[:10], "%Y-%m-%d").date()
        return max((today - td).days, 0)
    except Exception:  # noqa: BLE001
        return 0


def _group_by_hr(rows: List[Dict[str, Any]], today: date) -> Dict[str, Dict[str, Any]]:
    """Group overdue steps by HR owner email. Skips rows with no HR email."""
    groups: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        hr_email = (r.get("hr_email") or "").strip()
        if not hr_email or "@" not in hr_email:
            continue
        g = groups.setdefault(
            hr_email,
            {"hr_name": r.get("hr_name"), "hr_email": hr_email, "items": []},
        )
        g["items"].append(
            {
                "employee_name": (r.get("employee_name") or "An employee").strip() or "An employee",
                "step": (r.get("title") or "Untitled step").strip() or "Untitled step",
                "target_date": str(r.get("target_date"))[:10],
                "days_overdue": _days_overdue(r.get("target_date"), today),
            }
        )
    # Most-overdue first within each digest.
    for g in groups.values():
        g["items"].sort(key=lambda i: -i["days_overdue"])
    return groups


def render_weekly_mobility_email(
    *, hr_name: Optional[str], items: List[Dict[str, Any]]
):
    """Return (subject, plain, html) for one HR owner's overdue-steps digest.

    Pure — no I/O. Brand voice: clear, calm, specific (relopass-brand-voice).
    """
    name = (hr_name or "").strip() or "there"
    n = len(items)
    subject = f"Weekly mobility status: {n} step{'s' if n != 1 else ''} overdue"

    def line(i: Dict[str, Any]) -> str:
        d = i["days_overdue"]
        ago = "due today" if d == 0 else f"{d} day{'s' if d != 1 else ''} overdue"
        return f"• {i['employee_name']} — {i['step']} ({ago}, was due {i['target_date']})"

    plain = (
        f"Hi {name},\n\n"
        f"Here are the relocation steps across your active cases that are past their "
        f"due date and not yet complete:\n\n"
        + "\n".join(line(i) for i in items)
        + "\n\nReview these in your ReloPass command center.\n\n— The ReloPass team\n"
    )

    rows_html = "".join(
        f'<li style="margin:0 0 8px;font-size:14px;color:#334155">'
        f'<strong style="color:#0b2b43">{i["employee_name"]}</strong> — {i["step"]} '
        f'<span style="color:#b91c1c">'
        f'({"due today" if i["days_overdue"] == 0 else str(i["days_overdue"]) + " day" + ("s" if i["days_overdue"] != 1 else "") + " overdue"})</span> '
        f'<span style="color:#94a3b8">· was due {i["target_date"]}</span></li>'
        for i in items
    )
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        f'max-width:560px;margin:0 auto;color:#0f172a">'
        f'<p style="font-size:16px;margin:0 0 12px">Hi {name},</p>'
        f'<p style="font-size:15px;line-height:1.5;color:#334155;margin:0 0 16px">'
        f"These relocation steps across your active cases are past their due date and not yet complete:</p>"
        f'<ul style="padding-left:18px;margin:0 0 24px">{rows_html}</ul>'
        f'<p style="margin:0 0 0;color:#94a3b8;font-size:12px">Review these in your ReloPass command center.<br/>— The ReloPass team</p>'
        f"</div>"
    )
    return subject, plain, html


def run_weekly_mobility_status_cron() -> Dict[str, Any]:
    """Email each HR owner a digest of their overdue relocation steps.

    Returns ``{overdue_steps, hr_admins, sent, logged, failed}``. Never raises.
    """
    today = _today()
    rows = _overdue_milestones(today.isoformat())
    groups = _group_by_hr(rows, today)

    # Shared Resend delivery path — same provider/env as every other email.
    from .assignment_invite_email import _resend_send

    sent = logged = failed = 0
    for g in groups.values():
        try:
            subject, plain, html = render_weekly_mobility_email(
                hr_name=g["hr_name"], items=g["items"]
            )
        except Exception:  # noqa: BLE001 — one bad digest must not abort the run
            log.exception("weekly_mobility_status: render failed for hr=%s", g.get("hr_email"))
            failed += 1
            continue
        res = _resend_send(
            to_email=g["hr_email"],
            subject=subject,
            plain=plain,
            html=html,
            context="weekly mobility status",
        )
        status = res.get("status")
        if status == "sent":
            sent += 1
        elif status == "no_key":
            logged += 1
        else:
            failed += 1

    summary = {
        "overdue_steps": len(rows),
        "hr_admins": len(groups),
        "sent": sent,
        "logged": logged,
        "failed": failed,
    }
    log.info("weekly_mobility_status: %s", summary)
    return summary
