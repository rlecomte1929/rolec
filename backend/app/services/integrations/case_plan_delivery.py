"""I-4 — email a case's relocation plan + build an .ics of its deadlines.

Two product actions, both server-side (provider keys never leave the backend):
  * email_case_plan(case_id, to)  — renders the deterministic roadmap +
    upcoming milestones into a transactional email via the existing Resend
    sender (app.services.dossier_notifications._send_email).
  * build_case_ics(case_id, ...)  — emits an RFC-5545 VCALENDAR of the case's
    dated milestones, anchored at 09:00 in the subject's timezone, so any
    calendar app (Google / Apple / Outlook) imports real events — not deep links.

Deliberately uses the *deterministic* roadmap builder (roadmap_builder) and the
immigration_milestones table; it never touches the RAG/retrieval pipeline.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# app/services/integrations/ → backend is four levels up (....database = backend/database.py)
from ....database import db

# Human labels for the immigration_milestones.milestone_type enum.
_MILESTONE_LABELS: Dict[str, str] = {
    "preflight_check": "Pre-flight eligibility check",
    "dossier_assembly": "Assemble document dossier",
    "criminal_record_ordered": "Order criminal-record certificate",
    "application_filed": "File immigration application",
    "biometric_appointment": "Biometric appointment",
    "visa_decision": "Visa decision expected",
    "visa_issued": "Visa issued",
    "arrival": "Arrival in destination",
    "local_registration": "Local registration",
    "work_permit_issued": "Work permit issued",
    "permit_renewal_reminder": "Permit renewal reminder",
}

# Milestone states that are no longer actionable → excluded from the calendar.
_DONE_STATES = {"completed", "not_applicable"}


def milestone_label(milestone_type: str) -> str:
    return _MILESTONE_LABELS.get(
        milestone_type, (milestone_type or "Milestone").replace("_", " ").title()
    )


# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------

def resolve_timezone(user_id: Optional[str]) -> str:
    """Return the user's IANA timezone from profiles.timezone, else 'UTC'."""
    if not user_id:
        return "UTC"
    try:
        with db.engine.begin() as conn:
            from sqlalchemy import text
            row = conn.execute(
                text("SELECT timezone FROM public.profiles WHERE id = :uid"),
                {"uid": str(user_id)},
            ).first()
    except Exception:
        return "UTC"
    tz = (row[0] if row else None) or "UTC"
    # Validate; fall back to UTC on an unknown/garbage value.
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"
    return tz


# ---------------------------------------------------------------------------
# Calendar events
# ---------------------------------------------------------------------------

def gather_case_milestones(case_id: str) -> List[Dict[str, Any]]:
    """Dated, still-actionable milestones for a case (oldest target_date first).

    Each item: {id, title, date (datetime.date), status, milestone_type}.
    """
    from sqlalchemy import text
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, milestone_type, status, target_date "
                "FROM public.immigration_milestones "
                "WHERE case_id = :cid AND target_date IS NOT NULL "
                "ORDER BY target_date ASC"
            ),
            {"cid": str(case_id)},
        ).mappings().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        if str(r["status"] or "").lower() in _DONE_STATES:
            continue
        td = r["target_date"]
        if isinstance(td, str):
            try:
                td = _dt.date.fromisoformat(td[:10])
            except ValueError:
                continue
        out.append(
            {
                "id": str(r["id"]),
                "title": milestone_label(r["milestone_type"]),
                "date": td,
                "status": r["status"],
                "milestone_type": r["milestone_type"],
            }
        )
    return out


def _ics_escape(text_value: str) -> str:
    """Escape per RFC 5545 §3.3.11 (backslash, semicolon, comma, newline)."""
    return (
        (text_value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _utc_stamp(dt: _dt.datetime) -> str:
    return dt.astimezone(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(
    events: List[Dict[str, Any]],
    tz_name: str = "UTC",
    *,
    case_id: str = "",
    now: Optional[_dt.datetime] = None,
) -> str:
    """Build an RFC-5545 VCALENDAR string from dated events.

    Each event {id, title, date, description?} becomes a 1-hour VEVENT at 09:00
    in ``tz_name`` (emitted in UTC so the instant is unambiguous), with a
    1-day-prior VALARM. Pure + deterministic given ``now`` — no DB/IO.
    """
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    dtstamp = _utc_stamp(now or _dt.datetime.now(_dt.timezone.utc))

    lines: List[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ReloPass//Relocation Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for ev in events:
        d: _dt.date = ev["date"]
        start_local = _dt.datetime(d.year, d.month, d.day, 9, 0, 0, tzinfo=tz)
        end_local = start_local + _dt.timedelta(hours=1)
        uid = f"{ev.get('id') or d.isoformat()}@relopass.com"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{_utc_stamp(start_local)}",
            f"DTEND:{_utc_stamp(end_local)}",
            f"SUMMARY:{_ics_escape('ReloPass — ' + str(ev.get('title') or 'Milestone'))}",
        ]
        if ev.get("description"):
            lines.append(f"DESCRIPTION:{_ics_escape(str(ev['description']))}")
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-P1D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_ics_escape('Reminder: ' + str(ev.get('title') or 'Milestone'))}",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # RFC 5545 mandates CRLF line breaks.
    return "\r\n".join(lines) + "\r\n"


def build_case_ics(case_id: str, user_id: Optional[str] = None) -> str:
    """Gather a case's milestones and render them as an .ics in the user's tz."""
    events = gather_case_milestones(case_id)
    tz = resolve_timezone(user_id)
    return build_ics(events, tz, case_id=case_id)


# ---------------------------------------------------------------------------
# Email the plan
# ---------------------------------------------------------------------------

def _render_plan_body(roadmap: Dict[str, Any], milestones: List[Dict[str, Any]]) -> str:
    """Plain-ish HTML fragment summarising the roadmap tracks + key dates."""
    parts: List[str] = []
    totals = roadmap.get("totals") or {}
    if totals:
        parts.append(
            "<strong>Overview:</strong> "
            + " · ".join(
                str(totals[k]) for k in ("time", "cost", "employerCovers") if totals.get(k)
            )
        )
    for track in roadmap.get("tracks") or []:
        steps = track.get("steps") or []
        if not steps:
            continue
        step_titles = ", ".join(str(s.get("title")) for s in steps[:6] if s.get("title"))
        parts.append(f"<strong>{track.get('name')}:</strong> {step_titles}")
    if milestones:
        date_lines = "; ".join(
            f"{m['title']} — {m['date'].isoformat()}" for m in milestones[:8]
        )
        parts.append(f"<strong>Key dates:</strong> {date_lines}")
    return "<br/><br/>".join(parts) or "Your relocation plan is being prepared."


def build_case_plan_email(case_id: str) -> Dict[str, str]:
    """Return {subject, title, body} for a case's plan email. No email IO."""
    import json as _json
    from ..roadmap_builder import derive_roadmap   # app/services/roadmap_builder.py
    from ...db import SessionLocal                 # app/db.py
    from ... import crud                           # app/crud.py

    with SessionLocal() as session:
        case = crud.get_case(session, case_id)
        draft = _json.loads(getattr(case, "draft_json", None) or "{}") if case else {}
        status = getattr(case, "status", None) if case else None

    roadmap = derive_roadmap({"id": case_id, "status": status, "draft": draft})
    milestones = gather_case_milestones(case_id)
    return {
        "subject": "Your ReloPass relocation plan",
        "title": "Your relocation plan",
        "body": _render_plan_body(roadmap, milestones),
    }


def email_case_plan(case_id: str, to_email: str, cta_url: Optional[str] = None) -> Dict[str, Any]:
    """Render + send the plan email via the existing Resend transactional sender."""
    content = build_case_plan_email(case_id)
    from ..dossier_notifications import _send_email
    _send_email(
        to=to_email,
        subject=content["subject"],
        title=content["title"],
        body=content["body"],
        cta_url=cta_url,
    )
    return {"emailed_to": to_email, "subject": content["subject"]}
