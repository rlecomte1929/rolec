"""Test-Drive campaign email fan-out (AIQ-1424 / TD-6).

On survey submit: (1) notify Romain of a completion with the pitch-relevant details,
(2) send the tester a warm thank-you "from Romain". Reuses the shared Resend path
(`assignment_invite_email._resend_send`) — no new provider. Never raises; dry-runs to
status 'logged' when RESEND_API_KEY is unset.

Addresses (Resend authenticates by the verified relopass.com domain — no mailbox access):
  * notify → RELOPASS_TEST_DRIVE_NOTIFY_EMAIL (default romain.lecomte@relopass.com),
    reply-to = the tester (so a reply reaches them directly).
  * thank-you → the tester, from "Romain Lecomte <romain.lecomte@relopass.com>",
    reply-to = Romain (so tester replies reach him).

Referral PII is included in the notify email ONLY when the tester consented (referral_consent).
"""
from __future__ import annotations

import logging
import os
from html import escape as _esc
from typing import Any, Dict, List, Optional

from .assignment_invite_email import _resend_send

log = logging.getLogger(__name__)

_DEFAULT_NOTIFY = "romain.lecomte@relopass.com"
_DEFAULT_FROM = "Romain Lecomte <romain.lecomte@relopass.com>"


def _notify_email() -> str:
    return os.getenv("RELOPASS_TEST_DRIVE_NOTIFY_EMAIL", _DEFAULT_NOTIFY)


def _td_from() -> str:
    return os.getenv("RELOPASS_TEST_DRIVE_FROM", _DEFAULT_FROM)


def _lines_to_html(lines: List[str]) -> str:
    body = "".join(f"<p style='margin:2px 0'>{_esc(ln)}</p>" if ln else "<br>" for ln in lines)
    return f"<div style='font-family:sans-serif;color:#0b2b43'>{body}</div>"


def _pilot_line(pilot_interest: Optional[str], pilot_note: Optional[str]) -> str:
    if not pilot_interest:
        return "Pilot interest: —"
    note = f" — {pilot_note}" if pilot_note else ""
    return f"Pilot interest: {pilot_interest.upper()}{note}"


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

    if referral_name or referral_contact:
        if referral_consent:
            lines += [
                "",
                "── Referral (consented) ──",
                f"Name: {referral_name or '—'}",
                f"Company / role: {referral_company_role or '—'}",
                f"Contact: {referral_contact or '—'}",
            ]
        else:
            lines += ["", "── Referral ──", "Referral given, consent not granted — do not contact."]

    plain = "\n".join(lines)
    return subject, plain, _lines_to_html(lines)


def render_thank_you_email(
    *,
    tester_name: Optional[str] = None,
    pilot_interest: Optional[str] = None,
) -> "tuple[str, str, str]":
    who = tester_name or "there"
    subject = "Thanks for test-driving ReloPass"
    lines: List[str] = [
        f"Hi {who},",
        "",
        "Thanks for running a full relocation on ReloPass — genuinely useful.",
        "I'll act on what you flagged.",
    ]
    if pilot_interest in ("yes", "maybe"):
        lines += ["", "You mentioned possible interest in a pilot — I'll follow up personally, shortly."]
    lines += ["", "— Romain", "Romain Lecomte · ReloPass"]
    plain = "\n".join(lines)
    return subject, plain, _lines_to_html(lines)


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
) -> Dict[str, str]:
    """Fire both composers best-effort. Returns {notify, thank_you} statuses. Never raises."""
    out: Dict[str, str] = {}

    # 1) Notify Romain — reply-to the tester.
    try:
        subject, plain, html = render_notify_email(
            tester_name=tester_name, tester_email=tester_email, campaign=campaign, corridor_id=corridor_id,
            tester_segment=tester_segment, company_role=company_role, sector=sector, q1_overall=q1_overall,
            q2_friction=q2_friction, q3_problem_fit=q3_problem_fit, q4_change=q4_change,
            pilot_interest=pilot_interest, pilot_note=pilot_note, testimonial=testimonial,
            referral_name=referral_name, referral_company_role=referral_company_role,
            referral_contact=referral_contact, referral_consent=referral_consent,
        )
        res = _resend_send(
            to_email=_notify_email(), subject=subject, plain=plain, html=html,
            reply_to=(tester_email or None), context="test-drive notify",
        )
        out["notify"] = _status(res)
    except Exception:  # noqa: BLE001
        log.warning("test-drive notify email failed (suppressed)")
        out["notify"] = "error"

    # 2) Thank the tester — from Romain, reply-to Romain.
    if tester_email and "@" in tester_email:
        try:
            subject, plain, html = render_thank_you_email(tester_name=tester_name, pilot_interest=pilot_interest)
            res = _resend_send(
                to_email=tester_email, subject=subject, plain=plain, html=html,
                from_addr=_td_from(), reply_to=_notify_email(), context="test-drive thank-you",
            )
            out["thank_you"] = _status(res)
        except Exception:  # noqa: BLE001
            log.warning("test-drive thank-you email failed (suppressed)")
            out["thank_you"] = "error"
    else:
        out["thank_you"] = "skipped"

    return out
