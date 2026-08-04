"""Test-Drive campaign email fan-out (AIQ-1424 / TD-6; AIQ-1433 / TD-12).

On survey submit: send exactly ONE Resend email — notify Romain of the completion with
the pitch-relevant details. Reuses the shared Resend path (`assignment_invite_email.
_resend_send`) — no new provider. Never raises; dry-runs to status 'logged' when
RESEND_API_KEY is unset.

The tester thank-you is no longer auto-sent by the platform (TD-12). Instead the notify
email and the /admin/test-drive dashboard each expose a client-side ``mailto:`` deep link
that opens Romain's own mail client with the thank-you prefilled — so it genuinely comes
from his mailbox, and Resend usage drops 2 → 1 per completion.

Addresses (Resend authenticates by the verified relopass.com domain — no mailbox access):
  * notify → RELOPASS_TEST_DRIVE_NOTIFY_EMAIL (default romain.lecomte@relopass.com),
    reply-to = the tester (so a reply reaches them directly).

Referral PII is included in the notify email ONLY when the tester consented (referral_consent).
"""
from __future__ import annotations

import logging
import os
from html import escape as _esc
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .assignment_invite_email import _resend_send

log = logging.getLogger(__name__)

_DEFAULT_NOTIFY = "romain.lecomte@relopass.com"


def _notify_email() -> str:
    return os.getenv("RELOPASS_TEST_DRIVE_NOTIFY_EMAIL", _DEFAULT_NOTIFY)


def _lines_to_html(lines: List[str]) -> str:
    body = "".join(f"<p style='margin:2px 0'>{_esc(ln)}</p>" if ln else "<br>" for ln in lines)
    return f"<div style='font-family:sans-serif;color:#0b2b43'>{body}</div>"


def _pilot_line(pilot_interest: Optional[str], pilot_note: Optional[str]) -> str:
    if not pilot_interest:
        return "Pilot interest: —"
    note = f" — {pilot_note}" if pilot_note else ""
    return f"Pilot interest: {pilot_interest.upper()}{note}"


def normalize_referrals(
    referrals: Optional[List[Dict[str, Any]]] = None,
    *,
    referral_name: Optional[str] = None,
    referral_company_role: Optional[str] = None,
    referral_contact: Optional[str] = None,
    referral_consent: bool = False,
) -> List[Dict[str, Any]]:
    """Every referral on one survey, whichever shape the caller passed.

    A survey stores its full list in ``survey_responses.referrals`` and mirrors ``referrals[0]``
    into the legacy scalar columns, so a caller may supply either. When the list is absent or
    empty the legacy scalars are wrapped into a 1-element list — the mirror guarantees this
    never double-counts. Entries with neither a name nor a contact are dropped (a company/role
    alone is not a reachable person), matching the survey writer and the admin panel.

    Shared by the in-app notification and the notify email so the two can never disagree about
    who was referred. Consent is per entry and is NOT filtered here — the caller decides, since
    the admin list shows unconsented people (flagged) while the outreach paths must not.
    """
    items = [
        r for r in (referrals or [])
        if isinstance(r, dict) and ((r.get("name") or "").strip() or (r.get("contact") or "").strip())
    ]
    if items:
        return items
    if (referral_name or "").strip() or (referral_contact or "").strip():
        return [{
            "name": referral_name,
            "company_role": referral_company_role,
            "contact": referral_contact,
            "consent": bool(referral_consent),
        }]
    return []


def render_notify_email(
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
    referrals: Optional[List[Dict[str, Any]]] = None,
) -> "tuple[str, str, str]":
    who = tester_name or "A tester"
    pilot_flag = " · PILOT" if pilot_interest in ("yes", "maybe") else ""
    subject = f"Test-drive complete: {who} · {corridor_id or campaign or 'test-drive'}{pilot_flag}"

    lines: List[str] = [
        f"{who} just finished a test-drive.",
        "",
        f"Corridor: {corridor_id or '—'}",
        f"Segment: {tester_segment or '—'}",
        f"Company / role: {company_role or '—'}",
        f"Sector: {sector or '—'}",
        f"Email: {tester_email or '—'}",
        "",
        "── Pilot ──",
        _pilot_line(pilot_interest, pilot_note),
        "",
        "── Survey ──",
        f"Q1 overall (1-5): {q1_overall if q1_overall is not None else '—'}",
        f"Q2 friction: {q2_friction or '—'}",
        f"Q3 problem fit: {q3_problem_fit or '—'}",
        f"Q4 one change: {q4_change or '—'}",
        "",
        f"Testimonial: {testimonial or '—'}",
    ]

    # A tester can leave several intros, each with its own consent. Consent is checked PER
    # PERSON — a row-level check would leak an unconsented #2 riding on a consented #1.
    all_referrals = normalize_referrals(
        referrals, referral_name=referral_name, referral_company_role=referral_company_role,
        referral_contact=referral_contact, referral_consent=referral_consent,
    )
    consented = [r for r in all_referrals if r.get("consent")]
    if all_referrals:
        if consented:
            header = "── Referral (consented) ──" if len(consented) == 1 else \
                f"── Referrals (consented: {len(consented)}) ──"
            lines += ["", header]
            for ref in consented:
                lines += [
                    f"Name: {ref.get('name') or '—'}",
                    f"Company / role: {ref.get('company_role') or '—'}",
                    f"Contact: {ref.get('contact') or '—'}",
                    "",
                ]
            lines.pop()  # trailing spacer from the last entry
        withheld = len(all_referrals) - len(consented)
        if withheld:
            lines += ["", "── Referral ──"] if not consented else [""]
            lines.append(f"{withheld} referral(s) given, consent not granted — do not contact.")

    # TD-12: one-click thank-you from Romain's own mailbox (client-side mailto, no Resend send).
    mailto = _thank_you_mailto(tester_email, tester_name)
    if mailto:
        lines += ["", "── Thank-you (one click) ──", "Send the tester a thank-you from your own mailbox:"]

    plain = "\n".join(lines)
    html = _lines_to_html(lines)
    if mailto:
        plain += f"\n{mailto}"  # raw mailto stays clickable in plain-text clients
        who_label = tester_name or "the tester"
        html += (
            f"<div style='margin-top:12px'><a href='{_esc(mailto)}' "
            "style='display:inline-block;background:#0b2b43;color:#fff;text-decoration:none;"
            "font-family:sans-serif;font-weight:600;font-size:13px;border-radius:8px;padding:10px 18px'>"
            f"Send thank-you to {_esc(who_label)}</a></div>"
        )
    return subject, plain, html


# TD-12: the tester thank-you is now a client-side mailto (opened from Romain's mailbox),
# not a Resend send. This copy is the single source of truth for that prefill — the
# frontend button (TestDriveTab.tsx `thankYouMailto`) mirrors it and must stay in sync.
_THANK_YOU_SUBJECT = "Thank you — that really helps"


def _thank_you_copy(tester_name: Optional[str] = None) -> "tuple[str, str]":
    """Prefilled thank-you (subject, plain body). Kept short — long mailto bodies get
    truncated by some mail clients."""
    who = tester_name or "there"
    body = (
        f"Hi {who},\n\n"
        "Thanks for test-driving ReloPass — running a full relocation and telling me where "
        "it held and where it broke is genuinely useful. I'll act on what you flagged.\n\n"
        "— Romain"
    )
    return _THANK_YOU_SUBJECT, body


def _thank_you_mailto(tester_email: Optional[str], tester_name: Optional[str] = None) -> str:
    """``mailto:`` deep link that opens the sender's mail client with the thank-you
    prefilled. Empty string when there is no valid address."""
    if not tester_email or "@" not in tester_email:
        return ""
    subject, body = _thank_you_copy(tester_name)
    return f"mailto:{tester_email}?subject={quote(subject)}&body={quote(body)}"


def _status(res: Dict[str, Any]) -> str:
    # Preserve the public contract: the no-RESEND_API_KEY dev path reports 'logged'.
    return "logged" if res.get("status") == "no_key" else res.get("status", "error")


def send_test_drive_survey_emails(
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
    referrals: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """Send the single notify email best-effort. Returns {notify, thank_you} statuses.
    Never raises. TD-12: the tester thank-you is no longer a Resend send — it's a
    client-side mailto in the notify email + admin dashboard — so 'thank_you' is always
    'skipped' here (kept for a stable return shape; the caller ignores it)."""
    out: Dict[str, str] = {}

    # 1) Notify Romain — reply-to the tester. This is the ONLY Resend send (TD-12).
    try:
        subject, plain, html = render_notify_email(
            tester_name=tester_name, tester_email=tester_email, campaign=campaign, corridor_id=corridor_id,
            tester_segment=tester_segment, company_role=company_role, sector=sector, q1_overall=q1_overall,
            q2_friction=q2_friction, q3_problem_fit=q3_problem_fit, q4_change=q4_change,
            pilot_interest=pilot_interest, pilot_note=pilot_note, testimonial=testimonial,
            referral_name=referral_name, referral_company_role=referral_company_role,
            referral_contact=referral_contact, referral_consent=referral_consent,
            referrals=referrals,
        )
        res = _resend_send(
            to_email=_notify_email(), subject=subject, plain=plain, html=html,
            reply_to=(tester_email or None), context="test-drive notify",
        )
        out["notify"] = _status(res)
    except Exception:  # noqa: BLE001
        log.warning("test-drive notify email failed (suppressed)")
        out["notify"] = "error"

    # 2) Tester thank-you is now a client-side mailto (see render_notify_email / the
    #    admin dashboard) — no Resend send here. Kept as 'skipped' for a stable contract.
    out["thank_you"] = "skipped"

    return out
