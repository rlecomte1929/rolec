"""[AIQ-2188] Deliver the colleague-invite accept link by email.

AIQ-2094 shipped the full invite lifecycle (HR raises → admin approves → colleague
accepts) but nothing delivered the accept link. ``admin_approve_company_invite`` mints
the raw token, returns it to the admin once, and stores only its sha256 — so until this
module an admin had to copy the token out of an API response and pass it to the colleague
by hand. This sends a working accept link to the invited address the moment the invite is
approved.

Security — this carries ST3's central property:
- The link embeds the RAW token, which exists only inside the approve handler's local
  scope. This module receives it as an argument, puts it in the email body, and keeps no
  copy. The raw token is NEVER logged (``log_body=False`` on the shared sender, so even
  the no-key dev path omits the body) — a leak of logs or the database still yields no
  working link, because only sha256(token) is persisted.
- Best-effort like ``assignment_invite_email``: it never raises. A delivery failure must
  not roll back a valid approval; the caller wraps this too (defense in depth).

Delivery reuses ``assignment_invite_email._resend_send`` — the single Resend path shared
by every transactional email — so env/provider/POST behaviour cannot drift between them.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .assignment_invite_email import _resend_send

log = logging.getLogger(__name__)

# Public web app base (where /invite lives). Same var the assignment invite uses.
_WEB_BASE = os.getenv("APP_WEB_BASE_URL", "https://relopass.com")


def build_invite_link(raw_token: str) -> str:
    """The accept link the colleague follows: /invite/<raw token>."""
    return f"{_WEB_BASE.rstrip('/')}/invite/{raw_token}"


def render_company_invite_email(*, to_email: str, company_name: Optional[str], raw_token: str):
    """Return (subject, plain_text, html). Pure — no I/O. The link carries the raw token."""
    company = (company_name or "").strip() or "a company"
    name = (to_email.split("@")[0] if to_email else "there")
    link = build_invite_link(raw_token)

    subject = f"You've been invited to join {company} on ReloPass"
    lead = (
        f"You've been invited to join {company} on ReloPass. Sign in — or create your "
        "account with the email address this invite was sent to — and you'll be added "
        "automatically."
    )
    plain = (
        f"Hi {name},\n\n"
        f"{lead}\n\n"
        f"Accept your invite: {link}\n\n"
        "This link is single-use and expires in 14 days. If it has expired, ask your "
        "administrator to send a new one.\n\n"
        "— The ReloPass team\n"
    )
    html = (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'max-width:520px;margin:0 auto;color:#0f172a">'
        f'<p style="font-size:16px;margin:0 0 12px">Hi {name},</p>'
        f'<p style="font-size:15px;line-height:1.5;color:#334155;margin:0 0 24px">{lead}</p>'
        f'<a href="{link}" style="display:inline-block;background:#1f8e8b;color:#fff;'
        'text-decoration:none;font-weight:600;font-size:15px;padding:12px 22px;border-radius:8px">'
        "Accept your invite</a>"
        '<p style="margin:28px 0 0;color:#94a3b8;font-size:12px">This link is single-use and '
        "expires in 14 days. If it has expired, ask your administrator to send a new one.</p>"
        '<p style="margin:12px 0 0;color:#94a3b8;font-size:12px">— The ReloPass team</p>'
        "</div>"
    )
    return subject, plain, html


def send_company_invite_email(
    *,
    to_email: str,
    company_name: Optional[str] = None,
    raw_token: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Email the colleague their accept link. Best-effort: returns a status dict, never raises.

    status: skipped (no email / no token) | logged (no RESEND_API_KEY — dev) |
            sent | failed (Resend non-2xx) | error (exception, suppressed)
    """
    if not to_email or "@" not in to_email:
        return {"status": "skipped", "reason": "no_email"}
    if not raw_token:
        return {"status": "skipped", "reason": "no_token"}
    try:
        subject, plain, html = render_company_invite_email(
            to_email=to_email, company_name=company_name, raw_token=raw_token
        )
    except Exception as exc:  # noqa: BLE001 — email must never break approval
        log.error("company invite render error (suppressed) to=%s: %s", to_email, exc)
        return {"status": "error"}

    # log_body=False: the body carries the raw token, so the no-key dev path must NOT
    # dump it to the log (ST3's property — the raw token lives in no persisted place).
    res = _resend_send(
        to_email=to_email,
        subject=subject,
        plain=plain,
        html=html,
        request_id=request_id,
        context="company invite email",
        log_body=False,
    )
    return {"status": "logged" if res["status"] == "no_key" else res["status"]}
