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
import re
from typing import Any, Dict, Optional

from sqlalchemy import text as _sql_text

log = logging.getLogger(__name__)

_STATUS_SENT = "sent"
_STATUS_NO_KEY = "no_key"
_STATUS_FAILED = "failed"
_STATUS_ERROR = "error"
_STATUS_UNREACHABLE = "unreachable"
# [AIQ-1609] No HR resolved, but an admin-allowlist recipient was emailed instead — so the
# notification reached someone actionable rather than being silently dropped.
_STATUS_FALLBACK = "fallback"
# [cost] A fixture case is not a send. Recorded, never delivered — so notified_at stays NULL
# and the row reads as "deliberately not mailed" rather than "successfully mailed".
_STATUS_SKIPPED_TEST = "skipped_test_fixture"

# The reserved synthetic domains the E2E provisioner mints. Kept in lockstep with
# scripts/e2e_purge.py TEST_EMAIL_DOMAINS. SUFFIX-matched, never substring: the
# @testcompany.com and @*-demo.com demo tenants are REAL accounts that must keep
# receiving mail, and "@testco.com" is a substring of neither.
_TEST_EMAIL_DOMAINS = ("@testco.com", "@probe.test")


def _engine():
    from ...database import db  # type: ignore[import]

    return db.engine


def _app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "https://app.relopass.com").rstrip("/")


# ── Recipient ────────────────────────────────────────────────────────────────────────

# An HR id (case_assignments.hr_user_id / hr_users.profile_id) can resolve an email from any
# of three id systems — legacy `users`, `profiles`, or Supabase `auth.users` — and which one
# holds it varies per HR (prod: 61 via users, 40 via profiles, 6 via auth, mostly disjoint).
# So every lookup COALESCEs across all three rather than betting on `users` alone.
_EMAIL_EXPR = (
    "COALESCE(NULLIF(TRIM(u.email), ''), NULLIF(TRIM(p.email), ''), NULLIF(TRIM(au.email), ''))"
)
_NAME_EXPR = (
    "COALESCE(NULLIF(TRIM(u.name), ''), NULLIF(TRIM(p.full_name), ''), "
    "NULLIF(TRIM(u.email), ''), NULLIF(TRIM(p.email), ''), NULLIF(TRIM(au.email), ''))"
)
_HR_EMAIL_JOINS = (
    "LEFT JOIN public.users u    ON u.id::text  = {hr}\n"
    "    LEFT JOIN public.profiles p ON p.id::text  = {hr}\n"
    "    LEFT JOIN auth.users au      ON au.id::text = {hr}"
)

# Tier 1 — the HR actually assigned to the case (matched on either id-space).
_ASSIGNED_HR_SQL = _sql_text(
    f"""
    SELECT {_EMAIL_EXPR} AS email,
           {_NAME_EXPR}  AS hr_name,
           TRIM(COALESCE(ca.employee_first_name, '') || ' ' ||
                COALESCE(ca.employee_last_name, '')) AS employee_name
    FROM public.case_assignments ca
    {_HR_EMAIL_JOINS.format(hr='ca.hr_user_id::text')}
    WHERE (ca.case_id::text = :cid OR ca.canonical_case_id::text = :cid)
      AND {_EMAIL_EXPR} IS NOT NULL
    ORDER BY ca.created_at
    LIMIT 1
    """
)

# Tier 2 — no assignment resolved an emailable HR: fall back to the case's COMPANY and its
# earliest-created HR who has an email. Deterministic (ORDER BY created_at) so ">1 HR" always
# picks the same person. Keyed on public.cases.id (the canonical/wizard case id).
_COMPANY_HR_SQL = _sql_text(
    f"""
    SELECT {_EMAIL_EXPR} AS email,
           {_NAME_EXPR}  AS hr_name,
           '' AS employee_name
    FROM public.cases c
    JOIN public.hr_users hu ON hu.company_id::text = c.company_id::text
    {_HR_EMAIL_JOINS.format(hr='hu.profile_id::text')}
    WHERE c.id::text = :cid
      AND {_EMAIL_EXPR} IS NOT NULL
    ORDER BY hu.created_at
    LIMIT 1
    """
)


def resolve_hr_recipient(case_id: str) -> Optional[Dict[str, Any]]:
    """The HR owner to email for a case, or None when nobody can be reached.

    Two tiers: (1) the HR assigned to the case; (2) failing that, the case's company's
    earliest-created HR with an email. Each tier resolves the email across users/profiles/
    auth.users. None is a real, expected answer — the caller records it as ``unreachable``
    so it shows up in the metrics instead of vanishing.
    """
    cid = str(case_id)
    try:
        with _engine().connect() as conn:
            row = conn.execute(_ASSIGNED_HR_SQL, {"cid": cid}).fetchone()
            if row is None:
                row = conn.execute(_COMPANY_HR_SQL, {"cid": cid}).fetchone()
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

    # AIQ-1605: roadmaps are released-by-default (AIQ-1377), so the employee is NOT blocked.
    # The email invites review — approve to confirm, or request changes — without falsely
    # claiming the employee is stuck until HR acts.
    plain = (
        f"{who}'s relocation plan has been generated and is now live for them.\n\n"
        f"Please review it — approve to confirm it, or request changes if something needs "
        f"fixing. {who} can keep preparing in the meantime.\n\n"
        f"Review the roadmap: {link}\n\n"
        f"— ReloPass"
    )
    html = (
        '<div style="font-family:Inter,Arial,sans-serif;color:#0b2b43;max-width:520px">'
        f'<h1 style="font-size:18px;margin:0 0 12px">Roadmap ready for your review</h1>'
        f'<p style="margin:0 0 14px;color:#475569;line-height:1.55">'
        f"<strong>{who}</strong>{where}&rsquo;s relocation plan has been generated and is now "
        f"live for them.</p>"
        f'<p style="margin:0 0 20px;color:#475569;line-height:1.55">'
        f"Please review it &mdash; approve to confirm it, or request changes if something "
        f"needs fixing. {who} can keep preparing in the meantime.</p>"
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
    delivered = status in (_STATUS_SENT, _STATUS_NO_KEY, _STATUS_FALLBACK)
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


# ── Fixture suppression ──────────────────────────────────────────────────────────────


def _is_test_recipient(email: Optional[str]) -> bool:
    """True for the provisioner's reserved domains. Suffix match, so the demo tenants pass."""
    if not email:
        return False
    addr = email.strip().lower()
    return any(addr.endswith(domain) for domain in _TEST_EMAIL_DOMAINS)


_TEST_CASE_SQL = _sql_text(
    """
    SELECT 1
    FROM public.companies co
    WHERE COALESCE(co.is_test, false)
      AND (co.id::text IN (SELECT company_id::text FROM public.cases
                            WHERE id::text = :cid)
        OR co.id::text IN (SELECT company_id::text FROM public.relocation_cases
                            WHERE id::text = :cid)
        OR co.id::text IN (SELECT company_id::text FROM public.case_assignments
                            WHERE case_id::text = :cid OR canonical_case_id::text = :cid))
    LIMIT 1
    """
)


def _is_test_case(case_id: str) -> bool:
    """Does this case belong to an E2E-provisioned (is_test) company?

    FAILS OPEN. If the lookup breaks we answer False and the mail goes out — mirroring
    ``_already_notified``'s stance that a missing real notification costs more than a
    duplicate. Over-blocking here would silently strand a live customer.
    """
    try:
        with _engine().connect() as conn:
            return conn.execute(_TEST_CASE_SQL, {"cid": str(case_id)}).fetchone() is not None
    except Exception as exc:  # noqa: BLE001
        log.warning("roadmap notify: is_test lookup failed for %s: %s", case_id, exc)
        return False


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
        # An is_test company's roadmap is a fixture, not a customer waiting on HR. Checked
        # before _already_notified so the admin-allowlist fallback below (which also mails)
        # can never fire for one.
        if _is_test_case(case_id):
            _record(case_id, _STATUS_SKIPPED_TEST, None)
            log.info("roadmap notify: case %s is an is_test fixture — no email sent", case_id)
            return {"status": _STATUS_SKIPPED_TEST, "case_id": case_id}

        if _already_notified(case_id):
            return {"status": "already_notified", "case_id": case_id}

        recipient = resolve_hr_recipient(case_id)
        if not recipient:
            # [AIQ-1609] No HR contact resolves for this case. Rather than silently drop the
            # notification (the employee is blocked with nobody told), fall back to the platform
            # admin allowlist so someone actionable is always reached. Only when there is no
            # admin recipient either do we record the truly-unreachable state.
            from .admin_notify import resolve_admin_emails

            admins = resolve_admin_emails()
            if admins:
                if dry_run:
                    return {
                        "status": "dry_run",
                        "case_id": case_id,
                        "would_send_to": admins,
                        "fallback": True,
                    }
                from .assignment_invite_email import _resend_send

                subject = "Roadmap awaiting HR review — no HR recipient resolved"
                # Low-PII body: identifiers only, no employee personal data.
                plain = (
                    "A relocation roadmap is held for HR review, but no HR contact could be "
                    "resolved for this case.\n\n"
                    f"Case: {case_id}\n"
                    f"Corridor: {_corridor(case_id)}\n\n"
                    "Please review it in the ReloPass command center and ensure the case has an "
                    "assigned HR owner.\n\n— ReloPass"
                )
                sent_any = False
                for addr in admins:
                    res = _resend_send(
                        to_email=addr,
                        subject=subject,
                        plain=plain,
                        request_id=request_id,
                        context="roadmap review fallback",
                    )
                    if str(res.get("status") or _STATUS_ERROR) in (_STATUS_SENT, _STATUS_NO_KEY):
                        sent_any = True
                if sent_any:
                    _record(case_id, _STATUS_FALLBACK, ", ".join(admins))
                    log.warning(
                        "roadmap notify: NO HR RECIPIENT for case %s — sent FALLBACK to admin "
                        "allowlist (%d recipient(s))", case_id, len(admins),
                    )
                    return {"status": _STATUS_FALLBACK, "case_id": case_id, "to": admins}

            # No HR and no admin recipient — record loudly; a silent skip is indistinguishable
            # from a successful send.
            _record(case_id, _STATUS_UNREACHABLE, None)
            log.warning(
                "roadmap notify: NO HR RECIPIENT for case %s — employee is blocked with "
                "nobody notified", case_id,
            )
            return {"status": _STATUS_UNREACHABLE, "case_id": case_id}

        to_email = to_override or recipient["email"]

        # The stronger of the two signals in practice: 806 of 814 delivered rows resolved to
        # one of these domains, including cases whose company carried no is_test flag. An
        # explicit to_override is an operator acting deliberately, so it is honoured.
        if not to_override and _is_test_recipient(to_email):
            _record(case_id, _STATUS_SKIPPED_TEST, to_email)
            log.info("roadmap notify: %s is a fixture address — no email sent", to_email)
            return {"status": _STATUS_SKIPPED_TEST, "case_id": case_id, "to": to_email}

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


# ── AIQ-1608: notify the EMPLOYEE when HR requests roadmap changes ─────────────────────
# Sibling of notify_hr_roadmap_pending, but the recipient is the employee. Email always;
# in-app is guarded because notifications.user_id is uuid until #1543 lands in prod, so a
# legacy-text employee id would 500 the insert (mirrors exception_requests._notify_...).

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Employee-keyed clone of the assigned-HR lookup: resolve the employee's email + id across
# users / profiles / auth.users (same COALESCE strategy as the HR recipient).
_EMPLOYEE_RECIPIENT_SQL = _sql_text(
    f"""
    SELECT {_EMAIL_EXPR} AS email,
           {_NAME_EXPR}  AS employee_name,
           ca.employee_user_id::text AS employee_user_id
    FROM public.case_assignments ca
    {_HR_EMAIL_JOINS.format(hr='ca.employee_user_id::text')}
    WHERE (ca.case_id::text = :cid OR ca.canonical_case_id::text = :cid)
    ORDER BY ca.created_at
    LIMIT 1
    """
)


def _resolve_employee_recipient(case_id: str) -> Optional[Dict[str, Any]]:
    try:
        with _engine().connect() as conn:
            row = conn.execute(_EMPLOYEE_RECIPIENT_SQL, {"cid": str(case_id)}).fetchone()
    except Exception as exc:  # noqa: BLE001
        log.warning("roadmap change-notify: employee lookup failed for %s: %s", case_id, exc)
        return None
    if not row:
        return None
    m = row._mapping
    return {
        "email": (m["email"] or "").strip() or None,
        "employee_name": (m["employee_name"] or "").strip() or "there",
        "employee_user_id": (m["employee_user_id"] or "").strip() or None,
    }


def _render_change_email(*, employee_name: str, corridor: str, notes: str, case_id: str) -> Dict[str, str]:
    where = f" ({corridor})" if corridor else ""
    link = f"{_app_base_url()}/employee/case/{case_id}/roadmap"
    subject = "Your relocation roadmap needs an update"
    plain = (
        f"Hi {employee_name},\n\n"
        f"Your HR team reviewed your relocation roadmap{where} and asked for some changes "
        f"before it's finalised.\n\n"
        f"What they noted:\n{notes}\n\n"
        f"Your roadmap stays visible in the meantime, marked \"Under HR review\" — keep "
        f"preparing, and we'll let you know when the updated version is ready.\n\n"
        f"View your roadmap: {link}\n"
    )
    return {"subject": subject, "plain": plain}


def notify_employee_roadmap_changes(
    case_id: str,
    notes: str,
    *,
    dry_run: bool = False,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Tell the employee HR requested roadmap changes, carrying the HR note. Email
    (Resend) + in-app (guarded). NEVER RAISES — a notification problem must never fail
    the HR decision. Does not log the raw note."""
    result: Dict[str, Any] = {"case_id": case_id, "email_status": "skipped", "inapp": "skipped"}
    try:
        recipient = _resolve_employee_recipient(case_id)
        if not recipient:
            log.info("roadmap change-notify: no employee recipient for %s", case_id)
            return {**result, "status": "unreachable"}

        # ── email ──
        if recipient["email"] and not dry_run:
            from .assignment_invite_email import _resend_send

            msg = _render_change_email(
                employee_name=recipient["employee_name"],
                corridor=_corridor(case_id),
                notes=notes,
                case_id=case_id,
            )
            res = _resend_send(
                to_email=recipient["email"],
                subject=msg["subject"],
                plain=msg["plain"],
                request_id=request_id,
                context="roadmap_changes_employee",
            )
            result["email_status"] = str(res.get("status", "error"))
        elif not recipient["email"]:
            result["email_status"] = "no_email"

        # ── in-app (guarded: notifications.user_id is uuid until #1543) ──
        emp_id = recipient["employee_user_id"]
        if emp_id and _UUID_RE.match(str(emp_id)):
            try:
                from ...database import db

                db.create_notification_with_preferences(
                    user_id=str(emp_id),
                    type_="roadmap_changes_requested",
                    title="Your HR team requested roadmap changes",
                    body=f"HR asked for changes to your relocation roadmap. Note: {notes}",
                    case_id=str(case_id),
                    metadata={"event": "roadmap_changes_requested"},
                )
                result["inapp"] = "written"
            except Exception:  # noqa: BLE001 — in-app must not fail the decision
                log.warning("roadmap change-notify: in-app write failed for %s (suppressed)", case_id)
                result["inapp"] = "error"
        elif emp_id:
            log.warning(
                "roadmap change-notify: EMPLOYEE IN-APP SKIPPED (legacy non-uuid id) case=%s — "
                "notifications.user_id is uuid until #1543",
                case_id,
            )
            result["inapp"] = "skipped_legacy_id"
        return {**result, "status": "ok"}
    except Exception as exc:  # noqa: BLE001 — must never fail the HR decision
        log.warning("roadmap change-notify failed for %s (suppressed): %s", case_id, exc)
        return {**result, "status": "error"}
