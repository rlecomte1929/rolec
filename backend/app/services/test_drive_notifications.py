"""Test-Drive completion notification (AIQ-1547).

On survey completion, notify the admin(s) IN-APP — a row in ``public.notifications``
that surfaces in the admin Inbox / NotificationsBell — instead of a Resend email. A free
Resend tier won't survive a cohort, so the default channel is in-app and sends ZERO email.

Channel is gated by ``RELOPASS_TEST_DRIVE_NOTIFY_CHANNEL`` (inapp | email | both; default
inapp) so email can be re-enabled later without a code change.

Recipient id: the notifications read path (GET /api/notifications → NotificationsBell)
filters on the recipient's ``public.users.id`` — that's the id-space every existing
notification uses (verified: 394/426 rows key on users.id, 0 on the auth uuid). So we
resolve the admin's ``users.id`` from ``admin_allowlist`` by email and write that. The
write is a DIRECT INSERT into ``public.notifications`` — it never goes through the
email/outbox path, so no email is sent and no ``notification_outbox`` row is created.

Everything here is best-effort and NEVER raises into the survey submission.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ... import db_config
from ...database import db

log = logging.getLogger(__name__)

# AIQ-1547: the new in-app notification type. Mirrored in the frontend
# NOTIFICATION_TYPES (frontend/src/constants/notificationTypes.ts), whose
# getNotificationTarget() deep-links this type to /admin/test-drive.
NOTIFICATION_TYPE = "TEST_DRIVE_COMPLETED"

# Deep link carried in metadata (and hard-coded in the frontend target map).
_ADMIN_LINK = "/admin/test-drive"

_IS_SQLITE = (db_config.DATABASE_URL or "").startswith("sqlite")


def _channel() -> str:
    """inapp | email | both — default inapp (zero Resend). Unknown values fall back to inapp."""
    val = (os.getenv("RELOPASS_TEST_DRIVE_NOTIFY_CHANNEL") or "inapp").strip().lower()
    return val if val in ("inapp", "email", "both") else "inapp"


def _resolve_admin_user_ids() -> List[str]:
    """The admins to notify, as ``public.users.id`` (the id the Inbox read path filters on).

    Resolves enabled ``admin_allowlist`` rows to a users.id by email. Best-effort — returns
    [] on any error so a lookup failure never breaks the survey write."""
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT u.id AS user_id FROM admin_allowlist a "
                    "JOIN users u ON lower(u.email) = lower(a.email) "
                    "WHERE a.enabled = 1 AND u.id IS NOT NULL"
                )
            ).mappings().all()
        return [str(r["user_id"]) for r in rows if r.get("user_id")]
    except Exception:  # noqa: BLE001 — recipient lookup must never break the survey write
        log.warning("test-drive completion: admin recipient lookup failed (suppressed)")
        return []


def _build(
    *,
    tester_name: Optional[str],
    tester_email: Optional[str],
    corridor_id: Optional[str],
    campaign: Optional[str],
    tester_segment: Optional[str],
    company_role: Optional[str],
    sector: Optional[str],
    q1_overall: Optional[int],
    q3_problem_fit: Optional[str],
    pilot_interest: Optional[str],
    pilot_note: Optional[str],
    testimonial: Optional[str],
    referral_name: Optional[str],
    referral_company_role: Optional[str],
    referral_contact: Optional[str],
    referral_consent: bool,
    referrals: Optional[List[Dict[str, Any]]] = None,
) -> "tuple[str, str, Dict[str, Any]]":
    """Return (title, body, metadata) for the completion notification. Plain text, brand voice."""
    who = (tester_name or "").strip() or "A tester"
    where = corridor_id or campaign or "test-drive"
    title = f"Test-drive completed — {who} ({where})"

    parts: List[str] = []
    if q1_overall is not None:
        parts.append(f"Overall {q1_overall}/5")
    if q3_problem_fit:
        parts.append(f"problem fit: {q3_problem_fit}")
    if pilot_interest:
        parts.append(f"pilot: {pilot_interest}")
    if tester_segment:
        parts.append(tester_segment)
    if sector:
        parts.append(sector)
    body = " · ".join(parts) if parts else "Survey submitted."

    # From test_drive_emails — the single source of truth for the one-click thank-you prefill
    # and for how a survey's referrals are expanded (shared so the in-app notification and the
    # notify email can never disagree about who was referred).
    from .test_drive_emails import _thank_you_mailto, normalize_referrals

    all_referrals = normalize_referrals(
        referrals, referral_name=referral_name, referral_company_role=referral_company_role,
        referral_contact=referral_contact, referral_consent=referral_consent,
    )
    # Consent is per PERSON, not per survey — a row-level gate would leak an unconsented #2
    # behind a consented #1 (and hide a consented #2 behind an unconsented #1).
    consented = [r for r in all_referrals if r.get("consent")]

    metadata: Dict[str, Any] = {
        "tester_name": tester_name,
        "tester_email": tester_email,
        "corridor_id": corridor_id,
        "campaign": campaign,
        "tester_segment": tester_segment,
        "company_role": company_role,
        "sector": sector,
        "q1_overall": q1_overall,
        "q3_problem_fit": q3_problem_fit,
        "pilot_interest": pilot_interest,
        "pilot_note": pilot_note,
        "testimonial": testimonial,
        "referral_consent": bool(consented),
        # Counts are safe to show regardless of consent — they name nobody.
        "referral_count": len(all_referrals),
        "referral_consented_count": len(consented),
        "link": _ADMIN_LINK,
        "thank_you_mailto": _thank_you_mailto(tester_email, tester_name),
    }
    # Referral PII only for the people who consented (mirrors the email notify).
    if consented:
        metadata["referrals"] = [
            {
                "name": r.get("name"),
                "company_role": r.get("company_role"),
                "contact": r.get("contact"),
            }
            for r in consented
        ]
        # The first CONSENTED person also lands on the flat legacy keys, which existing
        # readers of this notification's metadata still use.
        first = consented[0]
        metadata["referral_name"] = first.get("name")
        metadata["referral_company_role"] = first.get("company_role")
        metadata["referral_contact"] = first.get("contact")

    return title, body, metadata


def _write_inapp(user_id: str, title: str, body: str, metadata: Dict[str, Any]) -> bool:
    """DIRECT INSERT of one in-app notification row (no email, no outbox). Returns True on
    success. Best-effort — a bad recipient (e.g. a non-uuid legacy users.id that fails the
    uuid cast) is logged and skipped, never raised."""
    uid_expr = ":user_id" if _IS_SQLITE else "CAST(:user_id AS uuid)"
    meta_expr = ":metadata" if _IS_SQLITE else "CAST(:metadata AS jsonb)"
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO notifications "
                    "(user_id, type, title, body, metadata, delivery_channel, source) "
                    f"VALUES ({uid_expr}, :type, :title, :body, {meta_expr}, 'in_app', 'test_drive')"
                ),
                {
                    "user_id": user_id,
                    "type": NOTIFICATION_TYPE,
                    "title": title,
                    "body": body,
                    "metadata": json.dumps(metadata, ensure_ascii=False),
                },
            )
        return True
    except Exception:  # noqa: BLE001 — a single bad recipient must never break the survey write
        log.warning("test-drive completion: in-app notification write failed (suppressed)")
        return False


def notify_test_drive_completion(
    *,
    tester_name: Optional[str] = None,
    tester_email: Optional[str] = None,
    campaign: Optional[str] = None,
    corridor_id: Optional[str] = None,
    tester_segment: Optional[str] = None,
    company_role: Optional[str] = None,
    sector: Optional[str] = None,
    q1_overall: Optional[int] = None,
    q2_friction: Optional[str] = None,
    q3_problem_fit: Optional[str] = None,
    q4_change: Optional[str] = None,
    pilot_interest: Optional[str] = None,
    pilot_note: Optional[str] = None,
    testimonial: Optional[str] = None,
    referral_name: Optional[str] = None,
    referral_company_role: Optional[str] = None,
    referral_contact: Optional[str] = None,
    referral_consent: bool = False,
    # Every referral the tester left. The legacy scalars above stay for backward
    # compatibility and are used only when this is absent/empty (they mirror referrals[0]).
    referrals: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Notify the admin of a completed test-drive on the configured channel(s).

    Default (RELOPASS_TEST_DRIVE_NOTIFY_CHANNEL unset → 'inapp'): write one in-app
    notification per admin, send ZERO email. 'email' or 'both' also/instead sends the
    existing Resend notify. Returns a small status dict. NEVER raises."""
    channel = _channel()
    out: Dict[str, Any] = {"channel": channel, "inapp": 0, "email": "skipped"}

    # In-app (default) — direct INSERT into public.notifications, one per admin recipient.
    if channel in ("inapp", "both"):
        try:
            title, body, metadata = _build(
                tester_name=tester_name, tester_email=tester_email, corridor_id=corridor_id,
                campaign=campaign, tester_segment=tester_segment, company_role=company_role,
                sector=sector, q1_overall=q1_overall, q3_problem_fit=q3_problem_fit,
                pilot_interest=pilot_interest, pilot_note=pilot_note, testimonial=testimonial,
                referral_name=referral_name, referral_company_role=referral_company_role,
                referral_contact=referral_contact, referral_consent=referral_consent,
                referrals=referrals,
            )
            written = 0
            for uid in _resolve_admin_user_ids():
                if _write_inapp(uid, title, body, metadata):
                    written += 1
            out["inapp"] = written
        except Exception:  # noqa: BLE001 — belt-and-braces: never break the survey write
            log.warning("test-drive completion: in-app notify failed (suppressed)")

    # Email — off by default; gated so it can be re-enabled without a code change.
    if channel in ("email", "both"):
        try:
            from .test_drive_emails import send_test_drive_survey_emails

            res = send_test_drive_survey_emails(
                tester_name=tester_name, tester_email=tester_email, campaign=campaign,
                corridor_id=corridor_id, tester_segment=tester_segment, company_role=company_role,
                sector=sector, q1_overall=q1_overall, q2_friction=q2_friction,
                q3_problem_fit=q3_problem_fit, q4_change=q4_change, pilot_interest=pilot_interest,
                pilot_note=pilot_note, testimonial=testimonial, referral_name=referral_name,
                referral_company_role=referral_company_role, referral_contact=referral_contact,
                referral_consent=referral_consent, referrals=referrals,
            )
            out["email"] = res.get("notify", "error")
        except Exception:  # noqa: BLE001
            log.warning("test-drive completion: email notify failed (suppressed)")
            out["email"] = "error"

    return out
