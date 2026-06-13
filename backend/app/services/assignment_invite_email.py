"""
Transactional invite email — sent when HR assigns a relocation case to an employee.

Closes the golden-path gap where assigning a case only created a DB pending-claim
token (the "case code") and an in-app pending entry, with **no active notification**
to the employee. HR previously had to tell people out-of-band.

Email service: Resend (``RESEND_API_KEY``) — the same mechanism as
``prescreening_notification.py``. When the key is unset (local/dev), the rendered
email is logged at INFO so nothing is silently dropped. This module **never
raises**: assignment creation must not be rolled back by an email failure
(the caller wraps it too, defense in depth).

Account-state logic:
- ``account_exists=False`` (no resolved user for the email) → link to
  ``/auth?mode=register`` so the employee creates an account; their case then
  auto-surfaces under "Cases waiting to be accepted".
- ``account_exists=True`` → link to ``/auth?mode=login``.
Either way the email also carries the ``invite_token`` (case code) as a fallback
for the manual "Link case" path.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests as http_requests

log = logging.getLogger(__name__)

# Public web app base (where /auth lives). Distinct from APP_BASE_URL
# (app.relopass.com) used by the HR-facing prescreening email.
_WEB_BASE = os.getenv("APP_WEB_BASE_URL", "https://relopass.com")


def _auth_link(mode: str, email: str) -> str:
    """Build /auth?mode=…&email=… ; the email param pre-fills the form."""
    base = _WEB_BASE.rstrip("/")
    if email:
        return f"{base}/auth?mode={mode}&email={quote(email, safe='')}"
    return f"{base}/auth?mode={mode}"


def render_assignment_invite_email(
    *,
    to_email: str,
    employee_name: Optional[str],
    hr_name: Optional[str],
    company_name: Optional[str],
    invite_token: Optional[str],
    account_exists: bool,
):
    """Return (subject, plain_text, html). Pure — no I/O."""
    company = (company_name or "").strip() or "your company"
    name = (employee_name or "").strip() or (to_email.split("@")[0] if to_email else "there")
    hr = (hr_name or "").strip() or "your HR team"
    mode = "login" if account_exists else "register"
    link = _auth_link(mode, to_email or "")
    cta_label = "Sign in to continue" if account_exists else "Create your account"
    code = (invite_token or "").strip()

    subject = f"Your relocation with {company} has started"
    lead = (
        f"{hr} at {company} has assigned you a new relocation case in ReloPass."
        if account_exists
        else f"{hr} at {company} has set up your relocation case in ReloPass."
    )

    plain = (
        f"Hi {name},\n\n"
        f"{lead}\n\n"
        f"{cta_label}: {link}\n\n"
        + (
            "If your case doesn't appear automatically, you can link it manually "
            f"with this case code:\n{code}\n\n"
            if code
            else ""
        )
        + "— The ReloPass team\n"
    )

    code_block = (
        f'<p style="margin:24px 0 4px;color:#475569;font-size:13px">'
        f"If your case doesn&rsquo;t appear automatically, link it manually with this case code:</p>"
        f'<p style="margin:0;font-family:monospace;font-size:13px;color:#0b2b43;'
        f'background:#f1f5f9;padding:8px 12px;border-radius:6px;word-break:break-all">{code}</p>'
        if code
        else ""
    )
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        f'max-width:520px;margin:0 auto;color:#0f172a">'
        f'<p style="font-size:16px;margin:0 0 12px">Hi {name},</p>'
        f'<p style="font-size:15px;line-height:1.5;color:#334155;margin:0 0 24px">{lead}</p>'
        f'<a href="{link}" style="display:inline-block;background:#1f8e8b;color:#fff;'
        f'text-decoration:none;font-weight:600;font-size:15px;padding:12px 22px;border-radius:8px">'
        f"{cta_label}</a>"
        f"{code_block}"
        f'<p style="margin:28px 0 0;color:#94a3b8;font-size:12px">— The ReloPass team</p>'
        f"</div>"
    )
    return subject, plain, html


def _resend_send(
    *,
    to_email: str,
    subject: str,
    plain: str,
    html: Optional[str] = None,
    request_id: Optional[str] = None,
    context: str = "email",
) -> Dict[str, Any]:
    """
    The single Resend delivery path, shared by the HR invite and the admin
    smoke test so both exercise the identical env/provider/POST. Never raises.

    Returns status: no_key (RESEND_API_KEY absent — logged, not sent) | sent |
    failed (Resend non-2xx) | error (exception, suppressed). Includes ``from``.
    """
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("EMAIL_FROM", "noreply@relopass.com")
    if not resend_key:
        log.info("%s (no RESEND_API_KEY — logged, not sent): to=%s subject=%r\n\n%s", context, to_email, subject, plain)
        return {"status": "no_key", "from": from_addr}
    try:
        resp = http_requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={"from": from_addr, "to": [to_email], "subject": subject, "text": plain, "html": html},
            timeout=10,
        )
        if resp.ok:
            log.info("%s sent to=%s request_id=%s", context, to_email, request_id)
            return {"status": "sent", "from": from_addr}
        log.error("%s delivery failed: %s %s", context, resp.status_code, resp.text[:200])
        return {"status": "failed", "http_status": resp.status_code, "from": from_addr}
    except Exception as exc:  # noqa: BLE001 — delivery must never break the caller
        log.error("%s send error (suppressed) to=%s: %s", context, to_email, exc)
        return {"status": "error", "from": from_addr}


def send_assignment_invite_email(
    *,
    to_email: str,
    employee_name: Optional[str] = None,
    hr_name: Optional[str] = None,
    company_name: Optional[str] = None,
    invite_token: Optional[str] = None,
    account_exists: bool = False,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send the assignment invite email. Best-effort: returns a status dict and
    never raises.

    status: skipped (no/invalid email) | logged (no RESEND_API_KEY — dev) |
            sent | failed (Resend non-2xx) | error (exception, suppressed)
    """
    if not to_email or "@" not in to_email:
        return {"status": "skipped", "reason": "no_email"}
    mode = "login" if account_exists else "register"
    try:
        subject, plain, html = render_assignment_invite_email(
            to_email=to_email,
            employee_name=employee_name,
            hr_name=hr_name,
            company_name=company_name,
            invite_token=invite_token,
            account_exists=account_exists,
        )
    except Exception as exc:  # noqa: BLE001 — email must never break assignment
        log.error("assignment invite render error (suppressed) to=%s: %s", to_email, exc)
        return {"status": "error", "mode": mode}

    res = _resend_send(
        to_email=to_email,
        subject=subject,
        plain=plain,
        html=html,
        request_id=request_id,
        context="assignment invite email",
    )
    # Preserve the public contract: the no-RESEND_API_KEY dev path reports "logged".
    out: Dict[str, Any] = {
        "status": "logged" if res["status"] == "no_key" else res["status"],
        "mode": mode,
    }
    if "http_status" in res:
        out["http_status"] = res["http_status"]
    return out


def send_smoke_test_email(to_email: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a minimal test email via the SAME Resend path as the HR invite
    (``_resend_send`` — same RESEND_API_KEY/EMAIL_FROM/provider). Used by the
    admin email-smoke-test endpoint to confirm live delivery. Never raises.

    Returns the raw _resend_send status: no_key | sent | failed | error.
    """
    if not to_email or "@" not in to_email:
        return {"status": "skipped", "reason": "no_email"}
    subject = "ReloPass email smoke test"
    plain = (
        "This is a ReloPass email delivery smoke test.\n\n"
        "If you received this, the Resend integration (RESEND_API_KEY + EMAIL_FROM) "
        "is configured correctly and HR invite emails will be delivered.\n\n— ReloPass"
    )
    html = (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a">'
        "<p>This is a <strong>ReloPass email delivery smoke test</strong>.</p>"
        "<p>If you received this, the Resend integration is configured correctly and "
        "HR invite emails will be delivered.</p>"
        '<p style="color:#94a3b8;font-size:12px">— ReloPass</p></div>'
    )
    return _resend_send(
        to_email=to_email,
        subject=subject,
        plain=plain,
        html=html,
        request_id=request_id,
        context="email smoke test",
    )
