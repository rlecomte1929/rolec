"""[AIQ-1220] Weekly HR mobility-briefing service.

Composes — and (unless ``dry_run``) emails — a once-a-week mobility briefing to
each active HR company's admin. The briefing is **deterministic / data-driven**:
it aggregates existing case data and renders a fixed HTML+plain-text template.
There is **no LLM call** in this path (no LLM cost / no PII leaving the platform).

Sections per company
--------------------
  1. Active assignments + status — counts grouped by ``case_assignments.status``.
  2. At-risk relocations — risk-flagged assignments (``risk_status`` yellow/red)
     plus the behind-schedule feed from
     ``case_health_scan.list_behind_cases_for_company`` (AIQ-378d).
  3. Upcoming compliance deadlines — ``case_forms`` due within the window
     (mirrors the deadline query in ``dossier_notifications``).

Company / recipient resolution
------------------------------
"Active HR company" = a company with ≥1 non-archived, non-terminal assignment.
Assignments link to a company via ``case_assignments.hr_user_id =
hr_users.profile_id → hr_users.company_id`` (the link that actually resolves in
prod — the bare ``hr_user_id = hr_users.id`` join matches almost nothing). The
admin recipient is the company's HR/admin profile email (``role='admin'``
preferred), or ``None`` when no emailable contact exists (then the company is
skipped).

Email delivery
--------------
Sends via Resend (``RESEND_API_KEY`` / ``EMAIL_FROM``), exactly like
``dossier_notifications._send_email``: falls back to INFO logging when the key is
unset (dev). Never raises to the caller — a send failure is counted, not fatal.

Cron entry point
----------------
``run_hr_mobility_briefing()`` is called by ``POST /api/crons/hr-mobility-briefing``
(weekly, Monday 08:00 via ``.github/workflows/hr-mobility-briefing.yml``).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests as http_requests
from sqlalchemy import bindparam as _bindparam
from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)

# Active = not archived and not in a terminal status.
_TERMINAL_STATUSES = ("submitted", "approved", "rejected", "cancelled", "completed")
_AT_RISK_STATUSES = ("yellow", "red")
_DEFAULT_DEADLINE_WINDOW_DAYS = 30


def _engine():
    from ...database import db  # type: ignore[import]
    return db.engine


# ---------------------------------------------------------------------------
# Data-source helpers — each safe-fails to an empty result (never raises).
# All SQL is Postgres-flavoured (text/uuid casts); unit tests mock these.
# ---------------------------------------------------------------------------

_ACTIVE_COMPANIES_SQL = """
WITH active_co AS (
    SELECT DISTINCT hu.company_id
    FROM public.case_assignments ca
    JOIN public.hr_users hu ON hu.profile_id = ca.hr_user_id
    WHERE ca.archived_at IS NULL
      AND ca.status NOT IN :terminal
),
admin_email AS (
    SELECT DISTINCT ON (hu.company_id)
           hu.company_id, p.email, p.full_name, p.role
    FROM public.hr_users hu
    JOIN public.profiles p
      ON p.id::text = hu.profile_id AND p.email IS NOT NULL
    ORDER BY hu.company_id, (p.role = 'admin') DESC, p.email
)
SELECT a.company_id,
       c.name  AS company_name,
       ae.email AS admin_email,
       ae.full_name AS admin_name
FROM active_co a
LEFT JOIN public.companies c  ON c.id::text = a.company_id
LEFT JOIN admin_email ae      ON ae.company_id = a.company_id
ORDER BY company_name NULLS LAST
"""


def list_active_companies() -> List[Dict[str, Any]]:
    """Active HR companies with their admin recipient. Safe-fails to ``[]``.

    Each row: ``{company_id, company_name, admin_email}`` (``admin_email`` may be
    ``None`` — those companies are skipped by the runner).
    """
    try:
        with _engine().connect() as conn:
            rows = (
                conn.execute(
                    _sql_text(_ACTIVE_COMPANIES_SQL).bindparams(
                        _bindparam("terminal", value=list(_TERMINAL_STATUSES), expanding=True)
                    )
                )
                .mappings()
                .all()
            )
        return [
            {
                "company_id": str(r["company_id"]),
                "company_name": r.get("company_name") or "Your company",
                "admin_email": r.get("admin_email"),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001 — degrade rather than raise
        log.exception("hr_mobility_briefing: list_active_companies failed")
        return []


def _assignments_by_status(company_id: str) -> List[Dict[str, Any]]:
    """``[{status, count}]`` for the company's active assignments (desc by count)."""
    sql = """
        SELECT ca.status AS status, COUNT(*) AS count
        FROM public.case_assignments ca
        JOIN public.hr_users hu ON hu.profile_id = ca.hr_user_id
        WHERE ca.archived_at IS NULL
          AND hu.company_id = :cid
        GROUP BY ca.status
        ORDER BY COUNT(*) DESC
    """
    try:
        with _engine().connect() as conn:
            rows = conn.execute(_sql_text(sql), {"cid": company_id}).mappings().all()
        return [{"status": r["status"] or "unknown", "count": int(r["count"])} for r in rows]
    except Exception:  # noqa: BLE001
        log.exception("hr_mobility_briefing: assignments_by_status failed cid=%s", company_id)
        return []


def _risk_flagged_assignments(company_id: str) -> List[Dict[str, Any]]:
    """Assignments whose ``risk_status`` is yellow/red — the always-on at-risk signal."""
    sql = """
        SELECT ca.id AS id,
               ca.case_id AS case_id,
               TRIM(COALESCE(ca.employee_first_name, '') || ' ' ||
                    COALESCE(ca.employee_last_name, '')) AS employee_name,
               ca.status AS status,
               ca.risk_status AS risk_status,
               ca.expected_start_date AS expected_start_date
        FROM public.case_assignments ca
        JOIN public.hr_users hu ON hu.profile_id = ca.hr_user_id
        WHERE ca.archived_at IS NULL
          AND hu.company_id = :cid
          AND ca.risk_status IN :risk
        ORDER BY ca.expected_start_date NULLS LAST
    """
    try:
        with _engine().connect() as conn:
            rows = (
                conn.execute(
                    _sql_text(sql).bindparams(
                        _bindparam("risk", value=list(_AT_RISK_STATUSES), expanding=True)
                    ),
                    {"cid": company_id},
                )
                .mappings()
                .all()
            )
        return [
            {
                "id": str(r["id"]),
                "case_id": str(r["case_id"]) if r.get("case_id") else None,
                "employee_name": (r.get("employee_name") or "").strip() or "Unnamed",
                "status": r.get("status"),
                "risk_status": r.get("risk_status"),
                "expected_start_date": str(r["expected_start_date"]) if r.get("expected_start_date") else None,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        log.exception("hr_mobility_briefing: risk_flagged_assignments failed cid=%s", company_id)
        return []


def _behind_schedule_cases(company_id: str) -> List[Dict[str, Any]]:
    """Reuse the tenant-scoped behind-schedule feed (AIQ-378d). Safe-fails to ``[]``."""
    try:
        from .case_health_scan import list_behind_cases_for_company
        return list_behind_cases_for_company(company_id) or []
    except Exception:  # noqa: BLE001
        log.exception("hr_mobility_briefing: behind_schedule_cases failed cid=%s", company_id)
        return []


def _upcoming_deadlines(company_id: str, window_days: int) -> List[Dict[str, Any]]:
    """``case_forms`` due within ``window_days`` for the company's active cases.

    Mirrors the deadline source in ``dossier_notifications.run_deadline_reminder_cron``
    (excludes already-submitted/approved/rejected forms), scoped to the company.
    """
    sql = """
        SELECT cf.id AS form_id,
               ft.name AS form_name,
               ft.authority_name AS authority_name,
               cf.deadline AS deadline,
               cf.status AS status
        FROM public.case_forms cf
        JOIN public.form_templates ft ON ft.id = cf.form_template_id
        JOIN public.case_assignments ca ON ca.case_id = cf.case_id::text
        JOIN public.hr_users hu ON hu.profile_id = ca.hr_user_id
        WHERE hu.company_id = :cid
          AND ca.archived_at IS NULL
          AND cf.deadline IS NOT NULL
          AND cf.deadline BETWEEN CURRENT_DATE AND CURRENT_DATE + :win
          AND cf.status NOT IN ('submitted', 'approved', 'rejected')
        ORDER BY cf.deadline
        LIMIT 50
    """
    try:
        with _engine().connect() as conn:
            rows = conn.execute(_sql_text(sql), {"cid": company_id, "win": window_days}).mappings().all()
        return [
            {
                "form_id": str(r["form_id"]),
                "form_name": r.get("form_name") or "Form",
                "authority_name": r.get("authority_name"),
                "deadline": str(r["deadline"]) if r.get("deadline") else None,
                "status": r.get("status"),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        log.exception("hr_mobility_briefing: upcoming_deadlines failed cid=%s", company_id)
        return []


# ---------------------------------------------------------------------------
# Payload composition
# ---------------------------------------------------------------------------

def build_company_briefing(
    company: Dict[str, Any],
    *,
    deadline_window_days: int = _DEFAULT_DEADLINE_WINDOW_DAYS,
) -> Dict[str, Any]:
    """Aggregate the three sections for one company and render subject/html/text.

    Pure composition over the data-source helpers above — no side effects, no
    network, no LLM. Returns a self-contained payload dict.
    """
    company_id = str(company["company_id"])
    company_name = company.get("company_name") or "Your company"

    by_status = _assignments_by_status(company_id)
    active_total = sum(s["count"] for s in by_status)

    risk_flagged = _risk_flagged_assignments(company_id)
    behind_schedule = _behind_schedule_cases(company_id)
    at_risk_count = len(risk_flagged) + len(behind_schedule)

    deadlines = _upcoming_deadlines(company_id, deadline_window_days)

    payload: Dict[str, Any] = {
        "company_id": company_id,
        "company_name": company_name,
        "admin_email": company.get("admin_email"),
        "active_assignments": {"total": active_total, "by_status": by_status},
        "at_risk": {
            "count": at_risk_count,
            "risk_flagged": risk_flagged,
            "behind_schedule": behind_schedule,
        },
        "upcoming_deadlines": {
            "count": len(deadlines),
            "window_days": deadline_window_days,
            "items": deadlines,
        },
    }
    payload["subject"] = f"Weekly mobility briefing — {company_name}"
    payload["html"] = _render_html(payload)
    payload["text"] = _render_text(payload)
    return payload


def _render_text(p: Dict[str, Any]) -> str:
    lines: List[str] = [f"Weekly mobility briefing — {p['company_name']}", ""]

    aa = p["active_assignments"]
    lines.append(f"ACTIVE ASSIGNMENTS: {aa['total']}")
    for s in aa["by_status"]:
        lines.append(f"  - {s['status']}: {s['count']}")
    if not aa["by_status"]:
        lines.append("  - No active assignments.")
    lines.append("")

    ar = p["at_risk"]
    lines.append(f"AT-RISK RELOCATIONS: {ar['count']}")
    for r in ar["risk_flagged"]:
        eta = r.get("expected_start_date") or "n/a"
        lines.append(f"  - {r['employee_name']} ({r['risk_status']}, status {r['status']}, start {eta})")
    for b in ar["behind_schedule"]:
        lines.append(
            f"  - Case {b.get('case_id')}: stage {b.get('stage')} "
            f"{b.get('days_behind')} day(s) behind"
        )
    if not ar["count"]:
        lines.append("  - None flagged.")
    lines.append("")

    dl = p["upcoming_deadlines"]
    lines.append(f"UPCOMING COMPLIANCE DEADLINES (next {dl['window_days']} days): {dl['count']}")
    for d in dl["items"]:
        auth = f" — {d['authority_name']}" if d.get("authority_name") else ""
        lines.append(f"  - {d['deadline']}: {d['form_name']}{auth}")
    if not dl["count"]:
        lines.append("  - No deadlines in the window.")

    return "\n".join(lines)


_HTML_SHELL = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f8fafc;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr><td style="background:#0b2b43;padding:24px 32px;">
          <span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:-0.3px;">ReloPass</span>
        </td></tr>
        <tr><td style="padding:32px;">
          <p style="margin:0 0 4px;font-size:22px;font-weight:700;color:#0b2b43;">Weekly mobility briefing</p>
          <p style="margin:0 0 24px;font-size:14px;color:#64748b;">{company_name}</p>
          {sections}
        </td></tr>
        <tr><td style="padding:16px 32px 24px;border-top:1px solid #f1f5f9;">
          <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.5;">
            You are receiving this weekly summary as the HR administrator for {company_name} on ReloPass.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _section(title: str, count_label: str, items_html: str) -> str:
    return (
        '<div style="margin:0 0 24px;">'
        f'<p style="margin:0 0 8px;font-size:15px;font-weight:700;color:#0b2b43;">{title}</p>'
        f'<p style="margin:0 0 8px;font-size:13px;color:#1f8e8b;font-weight:600;">{count_label}</p>'
        f'{items_html}'
        "</div>"
    )


def _ul(items: List[str]) -> str:
    if not items:
        return '<p style="margin:0;font-size:13px;color:#94a3b8;">Nothing to report.</p>'
    lis = "".join(
        f'<li style="margin:0 0 4px;font-size:13px;color:#334155;line-height:1.5;">{i}</li>'
        for i in items
    )
    return f'<ul style="margin:0;padding-left:18px;">{lis}</ul>'


def _esc(v: Any) -> str:
    s = "" if v is None else str(v)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_html(p: Dict[str, Any]) -> str:
    aa = p["active_assignments"]
    aa_items = [f"{_esc(s['status'])}: <strong>{s['count']}</strong>" for s in aa["by_status"]]
    sec_active = _section(
        "Active assignments", f"{aa['total']} active", _ul(aa_items)
    )

    ar = p["at_risk"]
    ar_items = [
        f"{_esc(r['employee_name'])} — {_esc(r['risk_status'])}, status "
        f"{_esc(r['status'])}, start {_esc(r.get('expected_start_date') or 'n/a')}"
        for r in ar["risk_flagged"]
    ] + [
        f"Case {_esc(b.get('case_id'))} — stage {_esc(b.get('stage'))}, "
        f"{_esc(b.get('days_behind'))} day(s) behind"
        for b in ar["behind_schedule"]
    ]
    sec_risk = _section(
        "At-risk relocations", f"{ar['count']} flagged", _ul(ar_items)
    )

    dl = p["upcoming_deadlines"]
    dl_items = [
        f"{_esc(d['deadline'])} — {_esc(d['form_name'])}"
        + (f" ({_esc(d['authority_name'])})" if d.get("authority_name") else "")
        for d in dl["items"]
    ]
    sec_dl = _section(
        f"Upcoming compliance deadlines (next {dl['window_days']} days)",
        f"{dl['count']} due",
        _ul(dl_items),
    )

    return _HTML_SHELL.format(
        company_name=_esc(p["company_name"]),
        sections=sec_active + sec_risk + sec_dl,
    )


# ---------------------------------------------------------------------------
# Email delivery — mirrors dossier_notifications._send_email (Resend + log fallback)
# ---------------------------------------------------------------------------

def _deliver(to: str, subject: str, html: str, text: str) -> bool:
    """Send one briefing email via Resend. Returns True on send/log, False on error.

    Falls back to INFO logging when ``RESEND_API_KEY`` is unset (dev), exactly
    like ``dossier_notifications._send_email``.
    """
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("EMAIL_FROM", "noreply@relopass.com")
    try:
        if resend_key:
            resp = http_requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                json={"from": from_addr, "to": [to], "subject": subject, "text": text, "html": html},
                timeout=10,
            )
            if not resp.ok:
                log.error("hr_mobility_briefing: email delivery failed %s %s", resp.status_code, resp.text[:200])
                return False
            return True
        log.info("HR BRIEFING EMAIL (no RESEND_API_KEY): to=%s subject=%r\n%s", to, subject, text)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("hr_mobility_briefing: email send error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Cron runner
# ---------------------------------------------------------------------------

def run_hr_mobility_briefing(
    *,
    dry_run: bool = False,
    only_company_id: Optional[str] = None,
    to_override: Optional[str] = None,
    deadline_window_days: int = _DEFAULT_DEADLINE_WINDOW_DAYS,
) -> Dict[str, Any]:
    """Compose and (unless ``dry_run``) email the weekly briefing per active company.

    Safety params for a targeted beta test:
      * ``dry_run`` — compose payloads and return them under ``previews`` WITHOUT
        sending any email.
      * ``only_company_id`` — restrict to a single company.
      * ``to_override`` — send every composed briefing to this one address instead
        of each company's admin (lands the real content in a tester's inbox).

    Returns ``{companies, emails_sent, skipped, errors, dry_run, previews}``.
    Never raises — one company's failure is counted and the run continues.
    """
    companies = list_active_companies()
    if only_company_id:
        companies = [c for c in companies if str(c["company_id"]) == str(only_company_id)]

    emails_sent = 0
    skipped = 0
    errors = 0
    previews: List[Dict[str, Any]] = []

    for company in companies:
        try:
            payload = build_company_briefing(company, deadline_window_days=deadline_window_days)
        except Exception:  # noqa: BLE001 — one bad company must not abort the run
            log.exception("hr_mobility_briefing: build failed for company=%s", company.get("company_id"))
            errors += 1
            continue

        recipient = to_override or payload.get("admin_email")
        if not recipient:
            skipped += 1
            continue

        if dry_run:
            previews.append(
                {
                    "company_id": payload["company_id"],
                    "company_name": payload["company_name"],
                    "to": recipient,
                    "subject": payload["subject"],
                    "active_total": payload["active_assignments"]["total"],
                    "at_risk_count": payload["at_risk"]["count"],
                    "deadline_count": payload["upcoming_deadlines"]["count"],
                    "text": payload["text"],
                }
            )
            continue

        ok = _deliver(recipient, payload["subject"], payload["html"], payload["text"])
        if ok:
            emails_sent += 1
        else:
            errors += 1

    log.info(
        "hr_mobility_briefing: companies=%d sent=%d skipped=%d errors=%d dry_run=%s",
        len(companies), emails_sent, skipped, errors, dry_run,
    )
    return {
        "companies": len(companies),
        "emails_sent": emails_sent,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
        "previews": previews,
    }
