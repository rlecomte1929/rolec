"""
[P4-4] Dossier Notification Service

Fires in-app (public.notifications) + email (Resend) for 8 key dossier events:

  1. new_form_created    — Employee: 'New document added'
  2. form_auto_filled    — Employee: 'Form ready for review, N pre-filled'
  3. deadline_7d         — Employee + Specialist: 'Form due in 7 days'
  4. blocker_resolved    — Employee: 'Your [doc] received. [Form] updated.'
  5. form_ready          — Specialist: 'Form is ready to submit'
  6. form_submitted      — Employee + HR: 'Submitted to [Authority]'
  7. form_rejected       — Employee + Specialist: '[Authority] returned form'
  8. dossier_built       — Specialist: 'Dossier ready'

Usage
-----
All public functions are fire-and-forget — they never raise to the caller.
They can be called inside open SQLAlchemy transactions or after commit.

Email delivery
--------------
Uses RESEND_API_KEY env var. Falls back to INFO-level logging in dev (no key).
EMAIL_FROM defaults to noreply@relopass.com.

In-app delivery
---------------
Writes to public.notifications via main_db.create_notification_with_preferences().
Uses type strings that start with 'dossier.' for easy frontend filtering.

Cron
----
run_deadline_reminder_cron() is the daily 08:00 CET job.  Call it from
POST /api/crons/deadline-reminder.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

import requests as http_requests
from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import helpers (avoid circular at module load; main_db is heavy)
# ---------------------------------------------------------------------------

def _main_db():
    from ....database import db  # type: ignore[import]
    return db


def _engine():
    return _main_db().engine


# ---------------------------------------------------------------------------
# Dialect helper  (mirrors cases.py)
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    """Return schema-qualified table name on Postgres, bare name on SQLite."""
    try:
        dialect = _engine().dialect.name
    except Exception:
        dialect = "sqlite"
    return f"public.{name}" if dialect == "postgresql" else name


# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

_CTX_QUERY = """
SELECT
    cf.id                AS case_form_id,
    cf.case_id,
    cf.status,
    cf.deadline,
    ft.name              AS form_name,
    ft.code              AS form_code,
    ft.authority_name    AS authority_name,
    cs.employee_id,
    cs.hr_owner_id,
    pe.full_name         AS employee_name,
    ps.full_name         AS specialist_name,
    pe.email             AS employee_email,
    ps.email             AS specialist_email,
    (SELECT COUNT(*) FROM {fv}
     WHERE case_form_id = cf.id AND filled_by = 'ai')           AS pre_filled_count,
    (SELECT COUNT(*) FROM {fv}
     WHERE case_form_id = cf.id AND filled_by IN
       ('employee','hr','specialist','system'))                  AS human_count
FROM {cf} cf
JOIN {ft} ft  ON ft.id  = cf.form_template_id
JOIN {cs} cs  ON cs.id  = cf.case_id
LEFT JOIN {pr} pe ON pe.id = cs.employee_id
LEFT JOIN {pr} ps ON ps.id = cs.hr_owner_id
WHERE cf.id = :case_form_id
LIMIT 1
"""


def _get_context(case_form_id: str) -> Optional[Dict[str, Any]]:
    """Return a dict with form/case/user context, or None if not found."""
    q = _CTX_QUERY.format(
        cf=_t("case_forms"),
        ft=_t("form_templates"),
        cs=_t("cases"),
        pr=_t("profiles"),
        fv=_t("case_form_field_values"),
    )
    try:
        with _engine().connect() as conn:
            row = conn.execute(_sql_text(q), {"case_form_id": case_form_id}).mappings().first()
        if not row:
            return None
        return dict(row)
    except Exception as exc:  # noqa: BLE001
        log.error("dossier_notifications: context load failed cf=%s: %s", case_form_id, exc)
        return None


def _get_case_context(case_id: str) -> Optional[Dict[str, Any]]:
    """Return aggregate case context (for dossier_built event)."""
    q = """
    SELECT
        c.id            AS case_id,
        c.employee_id,
        c.hr_owner_id,
        pe.full_name    AS employee_name,
        ps.full_name    AS specialist_name,
        pe.email        AS employee_email,
        ps.email        AS specialist_email,
        COUNT(cf.id)    AS form_count
    FROM {cs} c
    LEFT JOIN {pr} pe ON pe.id = c.employee_id
    LEFT JOIN {pr} ps ON ps.id = c.hr_owner_id
    LEFT JOIN {cf} cf ON cf.case_id = c.id
    WHERE c.id = :case_id
    GROUP BY c.id, c.employee_id, c.hr_owner_id, pe.full_name, ps.full_name,
             pe.email, ps.email
    LIMIT 1
    """.format(
        cs=_t("cases"),
        pr=_t("profiles"),
        cf=_t("case_forms"),
    )
    try:
        with _engine().connect() as conn:
            row = conn.execute(_sql_text(q), {"case_id": case_id}).mappings().first()
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        log.error("dossier_notifications: case context load failed case_id=%s: %s", case_id, exc)
        return None


# ---------------------------------------------------------------------------
# In-app notification writer
# ---------------------------------------------------------------------------

def _inapp(
    user_id: str,
    type_: str,
    title: str,
    body: str,
    case_id: Optional[str] = None,
) -> None:
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
        log.error("dossier_notifications: in-app write failed user=%s type=%s: %s", user_id, type_, exc)


# ---------------------------------------------------------------------------
# Email sender  (Resend — matches prescreening_notification.py pattern)
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
             style="background:#ffffff;border-radius:8px;overflow:hidden;
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
            <p style="margin:0 0 24px;font-size:15px;color:#334155;line-height:1.6;">{body}</p>
            {cta}
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px 24px;border-top:1px solid #f1f5f9;">
            <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.5;">
              You are receiving this because you are part of a ReloPass relocation case.
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
        View in ReloPass →
      </a>
    </td>
  </tr>
</table>
"""


def _send_email(to: str, subject: str, title: str, body: str, cta_url: Optional[str] = None) -> None:
    """Send one transactional email via Resend. Never raises."""
    cta = _CTA_BLOCK.format(url=cta_url) if cta_url else ""
    html = _EMAIL_HTML.format(title=title, body=body, cta=cta)
    plain = f"{title}\n\n{body}\n\n{cta_url or ''}"
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
                log.error("dossier_notifications: email delivery failed %s %s", resp.status_code, resp.text[:200])
        else:
            log.info("DOSSIER EMAIL (no RESEND_API_KEY): to=%s subject=%r\n%s", to, subject, plain)
    except Exception as exc:  # noqa: BLE001
        log.error("dossier_notifications: email send error: %s", exc)


def _case_url(case_id: Optional[str]) -> Optional[str]:
    if not case_id:
        return None
    base = os.getenv("APP_BASE_URL", "https://app.relopass.com")
    return f"{base}/hr/cases/{case_id}/dossier"


# ---------------------------------------------------------------------------
# 8 public notification functions
# ---------------------------------------------------------------------------

def notify_new_form_created(case_form_id: str) -> None:
    """Event 1 — New form created → notify Employee."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx:
            return
        title = f"New document added: {ctx['form_name']}"
        body = "We've pre-filled what we can. Open the form to review and complete it."
        emp_id = str(ctx["employee_id"])
        _inapp(emp_id, "dossier.new_form", title, body, str(ctx["case_id"]))
        if ctx.get("employee_email"):
            _send_email(
                to=ctx["employee_email"],
                subject=title,
                title=title,
                body=body,
                cta_url=_case_url(str(ctx["case_id"])),
            )
    except Exception as exc:  # noqa: BLE001
        log.error("notify_new_form_created failed cf=%s: %s", case_form_id, exc)


def notify_form_auto_filled(case_form_id: str) -> None:
    """Event 2 — Form auto-filled by Pre-Fill Engine → notify Employee."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx:
            return
        pre = int(ctx.get("pre_filled_count") or 0)
        human = int(ctx.get("human_count") or 0)
        title = f"{ctx['form_name']} ready for review"
        body = f"{pre} fields pre-filled, {human} still need your input."
        emp_id = str(ctx["employee_id"])
        _inapp(emp_id, "dossier.auto_filled", title, body, str(ctx["case_id"]))
        if ctx.get("employee_email"):
            _send_email(
                to=ctx["employee_email"],
                subject=title,
                title=title,
                body=body,
                cta_url=_case_url(str(ctx["case_id"])),
            )
    except Exception as exc:  # noqa: BLE001
        log.error("notify_form_auto_filled failed cf=%s: %s", case_form_id, exc)


def notify_blocker_resolved(case_form_id: str, unblocked_form_name: str) -> None:
    """Event 4 — Blocking form approved → notify Employee about the newly unblocked form."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx:
            return
        title = f"Your {ctx['form_name']} has been approved"
        body = f"{unblocked_form_name} is now unblocked and ready for you to complete."
        emp_id = str(ctx["employee_id"])
        _inapp(emp_id, "dossier.blocker_resolved", title, body, str(ctx["case_id"]))
        if ctx.get("employee_email"):
            _send_email(
                to=ctx["employee_email"],
                subject=title,
                title=title,
                body=body,
                cta_url=_case_url(str(ctx["case_id"])),
            )
    except Exception as exc:  # noqa: BLE001
        log.error("notify_blocker_resolved failed cf=%s: %s", case_form_id, exc)


def notify_form_ready(case_form_id: str) -> None:
    """Event 5 — Form marked ready → notify Specialist."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx or not ctx.get("hr_owner_id"):
            return
        emp = ctx.get("employee_name") or "The employee"
        title = f"{emp}'s {ctx['form_name']} is ready to submit"
        body = "All required fields are filled. You can now submit this form to the authority."
        spec_id = str(ctx["hr_owner_id"])
        _inapp(spec_id, "dossier.form_ready", title, body, str(ctx["case_id"]))
        if ctx.get("specialist_email"):
            _send_email(
                to=ctx["specialist_email"],
                subject=title,
                title=title,
                body=body,
                cta_url=_case_url(str(ctx["case_id"])),
            )
    except Exception as exc:  # noqa: BLE001
        log.error("notify_form_ready failed cf=%s: %s", case_form_id, exc)


def notify_form_submitted(case_form_id: str, receipt_ref: Optional[str] = None) -> None:
    """Event 6 — Form submitted to authority → notify Employee + HR."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx:
            return
        authority = ctx.get("authority_name") or "the authority"
        ref_str = f" Ref: {receipt_ref}." if receipt_ref else ""
        title = f"{ctx['form_name']} submitted to {authority}"
        body = f"Your form has been submitted.{ref_str} You will be notified of any updates."
        case_id = str(ctx["case_id"])
        url = _case_url(case_id)
        emp_id = str(ctx["employee_id"])
        _inapp(emp_id, "dossier.submitted", title, body, case_id)
        if ctx.get("employee_email"):
            _send_email(to=ctx["employee_email"], subject=title, title=title, body=body, cta_url=url)
        if ctx.get("hr_owner_id"):
            hr_id = str(ctx["hr_owner_id"])
            _inapp(hr_id, "dossier.submitted", title, body, case_id)
            if ctx.get("specialist_email"):
                _send_email(to=ctx["specialist_email"], subject=title, title=title, body=body, cta_url=url)
    except Exception as exc:  # noqa: BLE001
        log.error("notify_form_submitted failed cf=%s: %s", case_form_id, exc)


def notify_form_rejected(case_form_id: str, reason: Optional[str] = None) -> None:
    """Event 7 — Form rejected by authority → notify Employee + Specialist."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx:
            return
        authority = ctx.get("authority_name") or "The authority"
        reason_str = f" Reason: {reason}." if reason else ""
        title = f"{ctx['form_name']} was returned"
        body = f"{authority} returned this form.{reason_str} Please review and resubmit."
        case_id = str(ctx["case_id"])
        url = _case_url(case_id)
        emp_id = str(ctx["employee_id"])
        _inapp(emp_id, "dossier.rejected", title, body, case_id)
        if ctx.get("employee_email"):
            _send_email(to=ctx["employee_email"], subject=title, title=title, body=body, cta_url=url)
        if ctx.get("hr_owner_id"):
            hr_id = str(ctx["hr_owner_id"])
            _inapp(hr_id, "dossier.rejected", title, body, case_id)
            if ctx.get("specialist_email"):
                _send_email(to=ctx["specialist_email"], subject=title, title=title, body=body, cta_url=url)
    except Exception as exc:  # noqa: BLE001
        log.error("notify_form_rejected failed cf=%s: %s", case_form_id, exc)


def notify_dossier_built(case_id: str, form_count: int) -> None:
    """Event 8 — All forms submitted/approved → notify Specialist."""
    try:
        ctx = _get_case_context(case_id)
        if not ctx or not ctx.get("hr_owner_id"):
            return
        title = "Dossier ready"
        body = f"All {form_count} form(s) in this dossier have been submitted or approved."
        spec_id = str(ctx["hr_owner_id"])
        _inapp(spec_id, "dossier.built", title, body, case_id)
        if ctx.get("specialist_email"):
            _send_email(
                to=ctx["specialist_email"],
                subject=title,
                title=title,
                body=body,
                cta_url=_case_url(case_id),
            )
    except Exception as exc:  # noqa: BLE001
        log.error("notify_dossier_built failed case_id=%s: %s", case_id, exc)


# ---------------------------------------------------------------------------
# Deadline reminder  (Event 3 — called by daily cron)
# ---------------------------------------------------------------------------

def notify_deadline_7d(case_form_id: str) -> None:
    """Event 3 — Form deadline in 7 days → notify Employee + Specialist."""
    try:
        ctx = _get_context(case_form_id)
        if not ctx:
            return
        status_str = str(ctx.get("status") or "in progress")
        title = f"{ctx['form_name']} due in 7 days"
        body = f"This form is due in 7 days. Current status: {status_str}."
        case_id = str(ctx["case_id"])
        url = _case_url(case_id)
        emp_id = str(ctx["employee_id"])
        _inapp(emp_id, "dossier.deadline_7d", title, body, case_id)
        if ctx.get("employee_email"):
            _send_email(to=ctx["employee_email"], subject=title, title=title, body=body, cta_url=url)
        if ctx.get("hr_owner_id"):
            hr_id = str(ctx["hr_owner_id"])
            _inapp(hr_id, "dossier.deadline_7d", title, body, case_id)
            if ctx.get("specialist_email"):
                _send_email(to=ctx["specialist_email"], subject=title, title=title, body=body, cta_url=url)
    except Exception as exc:  # noqa: BLE001
        log.error("notify_deadline_7d failed cf=%s: %s", case_form_id, exc)


# ---------------------------------------------------------------------------
# Daily cron runner
# ---------------------------------------------------------------------------

def run_deadline_reminder_cron() -> Dict[str, Any]:
    """
    Find all case_forms with deadline = today + 7 days and deadline_reminded_at IS NULL.
    Send notifications and stamp deadline_reminded_at to prevent duplicates.

    Returns a summary dict: {checked: int, reminded: int, errors: int}
    """
    target_date = _date_in_n_days(7)
    reminded = 0
    errors = 0
    forms: list = []

    try:
        with _engine().connect() as conn:
            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, deadline FROM {_t('case_forms')}
                    WHERE deadline = :target_date
                      AND deadline_reminded_at IS NULL
                      AND status NOT IN ('submitted', 'approved', 'rejected')
                    """
                ),
                {"target_date": target_date},
            ).mappings().all()
            forms = [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        log.error("deadline_cron: query failed: %s", exc)
        return {"checked": 0, "reminded": 0, "errors": 1}

    for form in forms:
        cf_id = str(form["id"])
        try:
            notify_deadline_7d(cf_id)
            _stamp_reminded_at(cf_id)
            reminded += 1
        except Exception as exc:  # noqa: BLE001
            log.error("deadline_cron: error for cf=%s: %s", cf_id, exc)
            errors += 1

    log.info("deadline_cron: checked=%d reminded=%d errors=%d", len(forms), reminded, errors)
    return {"checked": len(forms), "reminded": reminded, "errors": errors}


def _stamp_reminded_at(case_form_id: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with _engine().begin() as conn:
            conn.execute(
                _sql_text(
                    f"UPDATE {_t('case_forms')} "
                    f"SET deadline_reminded_at = :now WHERE id = :id"
                ),
                {"now": now_iso, "id": case_form_id},
            )
    except Exception as exc:  # noqa: BLE001
        log.error("_stamp_reminded_at failed cf=%s: %s", case_form_id, exc)


def _date_in_n_days(n: int) -> str:
    """Return ISO date string for today + n days (UTC)."""
    from datetime import timedelta
    return (date.today() + timedelta(days=n)).isoformat()
