"""[AIQ-1526] Tell HR the moment a roadmap is waiting on their approval.

A generated roadmap is held (``roadmap_review_status.released_to_user = false``): the
employee can read their plan but cannot start tasks until HR approves it. Nothing told HR
the plan was waiting — they had to open the case by chance while the employee sat blocked.
This closes that loop.

Channel: EMAIL, via the shared ``_resend_send`` in ``assignment_invite_email``.

Why not the in-app notification? Because it does not work. ``GET /api/notifications`` and
``/api/notifications/unread-count`` both **500 in production** —
``invalid input syntax for type uuid: "seed-hr-testingapril"``: ``notifications.user_id``
is a ``uuid`` column but an HR user's legacy ReloPass id is text. 424 in-app notification
rows exist and not one is readable; the bell renders nothing. ``notification_outbox`` has
no consumer either (one row, ever). Resend is the only channel demonstrably delivering.

Recipient resolution: ``case_assignments.hr_user_id -> public.users.id -> users.email``.
This is the join that actually resolves in prod — the ``profiles``-based join used
elsewhere returns NULL for the HR persona.

**Unreachable is recorded, never swallowed.** 10 of the 47 cases with a roadmap resolve to
no HR email at all (7 have no ``case_assignments`` row; 3 have an HR id with no email). For
those, an employee could sit blocked with nobody told — a silent failure that looks exactly
like success. We write ``notify_status='unreachable'`` so the ops metrics can see it.

Never raises: a mail problem must not break roadmap generation.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)

_STATUS_SENT = "sent"
_STATUS_NO_KEY = "no_key"
_STATUS_FAILED = "failed"
_STATUS_ERROR = "error"
_STATUS_UNREACHABLE = "unreachable"


def _engine():
    from ...database import db  # type: ignore[import]

    return db.engine


def _app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "https://app.relopass.com").rstrip("/")


# ── Recipient ────────────────────────────────────────────────────────────────────────

_RECIPIENT_SQL = _sql_text(
    """
    SELECT u.email                                   AS email,
           COALESCE(NULLIF(TRIM(u.name), ''), u.email) AS hr_name,
           TRIM(COALESCE(ca.employee_first_name, '') || ' ' ||
                COALESCE(ca.employee_last_name, ''))   AS employee_name
    FROM public.case_assignments ca
    JOIN public.users u ON u.id::text = ca.hr_user_id::text
    WHERE ca.case_id::text = :cid
      AND COALESCE(NULLIF(TRIM(u.email), ''), NULL) IS NOT NULL
    LIMIT 1
    """
)


def resolve_hr_recipient(case_id: str) -> Optional[Dict[str, Any]]:
    """The HR owner to email for a case, or None when nobody can be reached.

    None is a real, expected answer — not an error. The caller records it as
    ``unreachable`` so it shows up in the metrics instead of vanishing.
    """
    try:
        with _engine().connect() as conn:
            row = conn.execute(_RECIPIENT_SQL, {"cid": str(case_id)}).fetchone()
    except Exception as exc:  # noqa: BLE001
        log.warning("roadmap notify: recipient lookup failed for %s: %s", case_id, exc)
        return None
    if not row:
        return None
    m = row._mapping
    return {
        "email": m["email"],
        "hr_name": m["hr_name"],
        "employee_name": (m["employee_name"] or "").strip() or "Your employee",
    }


def _corridor(case_id: str) -> str:
    """"FR → DE" when we know it, "" when we don't. Never guesses."""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                _sql_text(
                    "SELECT origin_country, dest_country FROM public.cases "
                    "WHERE id::text = :cid LIMIT 1"
                ),
                {"cid": str(case_id)},
            ).fetchone()
        if not row:
            return ""
        origin, dest = (row._mapping["origin_country"] or ""), (row._mapping["dest_country"] or "")
        if origin and dest:
            return f"{origin} → {dest}"
        return dest or ""
    except Exception:  # noqa: BLE001
        return ""


# ── Copy ─────────────────────────────────────────────────────────────────────────────


def render_email(*, case_id: str, employee_name: str, corridor: str) -> Dict[str, str]:
    """Say what is waiting, and what it costs to leave it waiting."""
    who = employee_name
    where = f" ({corridor})" if corridor else ""
    subject = f"Roadmap ready for your review — {who}{where}"
    link = f"{_app_base_url()}/hr/cases/{case_id}"

    plain = (
        f"{who}'s relocation plan is generated and waiting for your approval.\n\n"
        f"Until you approve it, {who} can explore the plan but cannot start any tasks.\n\n"
        f"Review the roadmap: {link}\n\n"
        f"— ReloPass"
    )
    html = (
        '<div style="font-family:Inter,Arial,sans-serif;color:#0b2b43;max-width:520px">'
        f'<h1 style="font-size:18px;margin:0 0 12px">Roadmap ready for your review</h1>'
        f'<p style="margin:0 0 14px;color:#475569;line-height:1.55">'
        f"<strong>{who}</strong>{where}&rsquo;s relocation plan is generated and waiting for "
        f"your approval.</p>"
        f'<p style="margin:0 0 20px;color:#475569;line-height:1.55">'
        f"Until you approve it, {who} can explore the plan but <strong>cannot start any "
        f"tasks</strong>.</p>"
        f'<a href="{link}" style="display:inline-block;background:#1f8e8b;color:#fff;'
        f'text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">'
        f"Review the roadmap</a>"
        f'<p style="margin:28px 0 0;color:#94a3b8;font-size:12px">— The ReloPass team</p>'
        "</div>"
    )
    return {"subject": subject, "plain": plain, "html": html}


# ── Outcome ──────────────────────────────────────────────────────────────────────────


def _record(case_id: str, status: str, to_email: Optional[str]) -> None:
    """Persist the send outcome. ``notified_at`` is set ONLY when HR was actually told.

    A failed send therefore stays visibly undelivered rather than being marked done — the
    metrics can tell "we reached HR" apart from "we tried and didn't".
    """
    delivered = status in (_STATUS_SENT, _STATUS_NO_KEY)
    try:
        with _engine().begin() as conn:
            conn.execute(
                _sql_text(
                    "UPDATE public.roadmap_review_status "
                    "SET notify_status = :st, notified_to = :to_email, "
                    "    notified_at = CASE WHEN :delivered THEN now() ELSE notified_at END "
                    "WHERE case_id::text = :cid"
                ),
                {"st": status, "to_email": to_email, "delivered": delivered, "cid": str(case_id)},
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("roadmap notify: could not record outcome for %s: %s", case_id, exc)


def _already_notified(case_id: str) -> bool:
    """Has HR already been told? Guards against a duplicate email."""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                _sql_text(
                    "SELECT notified_at FROM public.roadmap_review_status "
                    "WHERE case_id::text = :cid LIMIT 1"
                ),
                {"cid": str(case_id)},
            ).fetchone()
        return bool(row and row._mapping["notified_at"])
    except Exception:  # noqa: BLE001
        return False  # can't tell -> allow the send; a missing notification is worse than a repeat


# ── Entry point ──────────────────────────────────────────────────────────────────────


def notify_hr_roadmap_pending(
    case_id: str,
    *,
    dry_run: bool = False,
    to_override: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Email the case's HR owner that a roadmap is waiting on them.

    Idempotent: a case whose HR has already been notified is a no-op, so re-running the
    roadmap build never mails HR twice.

    NEVER RAISES. This runs inside the background task that builds the roadmap; an email
    problem must not cost the employee their plan.
    """
    try:
        if _already_notified(case_id):
            return {"status": "already_notified", "case_id": case_id}

        recipient = resolve_hr_recipient(case_id)
        if not recipient:
            # No HR contact resolves for this case. The employee is blocked and there is
            # nobody to tell. Record it loudly — a silent skip is indistinguishable from
            # a successful send.
            _record(case_id, _STATUS_UNREACHABLE, None)
            log.warning(
                "roadmap notify: NO HR RECIPIENT for case %s — employee is blocked with "
                "nobody notified", case_id,
            )
            return {"status": _STATUS_UNREACHABLE, "case_id": case_id}

        to_email = to_override or recipient["email"]
        email = render_email(
            case_id=case_id,
            employee_name=recipient["employee_name"],
            corridor=_corridor(case_id),
        )

        if dry_run:
            return {
                "status": "dry_run",
                "case_id": case_id,
                "would_send_to": to_email,
                "subject": email["subject"],
            }

        from .assignment_invite_email import _resend_send

        result = _resend_send(
            to_email=to_email,
            subject=email["subject"],
            plain=email["plain"],
            html=email["html"],
            request_id=request_id,
            context="roadmap review notification",
        )
        status = str(result.get("status") or _STATUS_ERROR)
        _record(case_id, status, to_email)
        return {"status": status, "case_id": case_id, "to": to_email}

    except Exception as exc:  # noqa: BLE001 — never break roadmap generation
        log.error("roadmap notify: unexpected failure for case %s: %s", case_id, exc, exc_info=True)
        _record(case_id, _STATUS_ERROR, None)
        return {"status": _STATUS_ERROR, "case_id": case_id}
