"""AIQ-1521 — mint a supplier magic link and (optionally) email it.

Lifted out of `routers/supplier_rfq.py` so the EMPLOYEE can dispatch their own RFQ. That is the
whole point of the employee-led model: HR pre-approves *who* and *how much*, then the employee
runs the RFQ themselves. Routing dispatch through an HR-only endpoint put HR right back in the
middle of the step we set out to remove them from.

Two callers, one path:
  - POST /api/rfqs                       (employee or HR — dispatch on create)
  - POST /api/hr/rfqs/{id}/supplier-links (HR/admin — explicit, can override the address)

SAFETY. Emailing a real company that has never heard of us must never happen by accident. Three
independent guards, and ALL must hold before a message goes out:
  1. `send_email` is False by default at every call site.
  2. An address is only ever taken from `suppliers.contact_email`. A supplier with no address on
     record is not an error and not a guess — it is reported, honestly, as not contacted.
  3. The SENDER must not be a test persona. If the acting user's email is on a synthetic seeder
     domain (`@probe.test` / `@testco.com`), the real email is suppressed unconditionally — even
     with the flag on and `RESEND_API_KEY` set. The token still mints and the link is returned, so
     the test flow stays fully functional, but nothing leaves the platform. This is the hard guard
     that lets QA run RFQ flows against the real (now partly contactable) catalog with zero risk of
     a test persona mailing a real mover.
Guards 1 and 2 are not feature flags; the flag (SUPPLIER_RFQ_DISPATCH_ENABLED) sits above them at
the RFQ-create call site. A mail failure never raises: the RFQ and the minted link survive it.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import text

from ...database import db
from ...db.test_data_filter import looks_like_test_email
from .rfq_brief import RESPONSE_EXPECTATIONS, render_brief_lines, respond_by
from .supplier_jwt import expires_at, generate_supplier_token, hash_token

log = logging.getLogger(__name__)

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://relopass.com")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@relopass.com")

NO_ADDRESS = "no contact email on record"
# AIQ-1533 — a catalog address is only dispatchable once its provenance is verified.
# The employee's RFQ carries their move details (route, dates, household); sending that to an
# unverified, scraped address is a data-protection problem, not just a bounce. HR's explicit
# override sets verified=True at the call site — a human taking responsibility for the address.
UNVERIFIED_ADDRESS = "supplier contact not verified"
# Personal / webmail domains that should never appear as a supplier contact.
# These indicate a placeholder was entered during catalog setup. Update the
# catalog row with the supplier's actual business address instead.
_PERSONAL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com",
    "hotmail.com", "hotmail.fr", "hotmail.co.uk",
    "outlook.com", "live.com", "msn.com",
    "yahoo.com", "yahoo.fr", "yahoo.co.uk",
    "icloud.com", "me.com", "mac.com",
    "protonmail.com", "pm.me",
})


def rfq_email_html(
    supplier_name: str,
    link: str,
    brief_rows: Optional[List[Dict[str, str]]] = None,
    deadline: Optional[str] = None,
) -> str:
    """The vendor must be able to judge the job BEFORE clicking.

    This used to say only "a company would like a quote" — a vendor could not tell the route, the
    date or the scope without clicking, so there was no reason to click. The brief goes IN the
    mail, and so does what we expect back. A vendor who cannot price does not reply, and their
    silence would read as "suppliers don't respond" when the truth is "we asked badly".

    Escape before interpolating. `supplier_name` is NOT trusted (the catalog is partly
    crowd-sourced and partly LLM-scraped) and the brief now carries EMPLOYEE free text
    (special_items, notes). This HTML is sent from our domain to an external company, so an
    unescaped value would let a user inject markup — including a link — into mail that appears to
    come from us. That is a phishing vector, not a rendering bug.
    """
    safe_name = escape(supplier_name or "")
    safe_link = escape(link, quote=True)
    rows = "".join(
        f"""<tr>
              <td style="padding:4px 12px 4px 0;color:#64748b;white-space:nowrap">{escape(r['label'])}</td>
              <td style="padding:4px 0;color:#0b2b43;font-weight:600">{escape(r['value'])}</td>
            </tr>"""
        for r in (brief_rows or [])
    )
    brief_html = (
        f'<table style="border-collapse:collapse;margin:16px 0;font-size:14px">{rows}</table>'
        if rows else ""
    )
    asks_html = ""
    if deadline:
        asks = "".join(f"<li style='margin-bottom:4px'>{escape(e)}</li>" for e in RESPONSE_EXPECTATIONS)
        asks_html = (
            f'<p style="margin-bottom:6px"><strong>What we need back by {escape(deadline)}:</strong></p>'
            f'<ul style="margin-top:0;padding-left:18px;font-size:14px;color:#334155">{asks}</ul>'
        )
    return f"""
      <div style="font-family:Inter,Arial,sans-serif;color:#0b2b43;line-height:1.5;max-width:560px">
        <p>Hello{(' ' + safe_name) if safe_name else ''},</p>
        <p>A company is relocating an employee and would like a quote from you for the move below.</p>
        {brief_html}
        {asks_html}
        <p><a href="{safe_link}"
              style="display:inline-block;background:#1f8e8b;color:#fff;padding:12px 20px;
                     border-radius:8px;text-decoration:none;font-weight:600">
             Send your quote
           </a></p>
        <p style="color:#64748b;font-size:13px">
          There is no account to create and nothing to install. The link is unique to you and
          expires in 14 days.
        </p>
        <p style="color:#64748b;font-size:13px">ReloPass</p>
      </div>
    """


def rfq_email_subject(brief_rows: Optional[List[Dict[str, str]]] = None) -> str:
    """A vendor triages on the subject line alone. Put the route in it, so they can tell at a
    glance whether this is even a job they cover."""
    by = {r["label"]: r["value"] for r in (brief_rows or [])}
    frm, to = by.get("Move from"), by.get("Move to")
    if frm and to and frm != "Not specified" and to != "Not specified":
        return f"Quote request: household move, {frm} → {to}"
    return "A relocation company would like a quote from you"


def resolve_rfq_targets(rfq_id: str) -> List[Dict[str, Any]]:
    """Every recipient of this RFQ, with the address we hold for them (or None).

    The address comes from `suppliers.contact_email`. It is NULL for most of the catalog, so a
    None here is the normal case, not a fault — the caller reports it rather than dropping it.
    """
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT r.id AS recipient_id, r.vendor_id, s.name AS supplier_name, "
                "       s.contact_email, s.verified "
                "  FROM rfq_recipients r "
                "  LEFT JOIN suppliers s ON s.id = r.vendor_id "
                " WHERE r.rfq_id = :rfq"
            ),
            {"rfq": str(rfq_id)},
        ).mappings().all()

    return [
        {
            "recipient_id": str(r["recipient_id"]),
            "vendor_id": str(r["vendor_id"]),
            "supplier_name": r["supplier_name"] or str(r["vendor_id"]),
            "email": (r["contact_email"] or "").strip() or None,
            "verified": bool(r["verified"]),
        }
        for r in rows
    ]


def dispatch_supplier_links(
    *,
    rfq_id: str,
    targets: List[Dict[str, Any]],
    send_email: bool = False,
    actor_email: Optional[str] = None,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Mint one link per target, persist it, and email it if asked to.

    Each target: {recipient_id, vendor_id, supplier_name, email|None}. A target with no email is
    skipped with `ok: False, error: NO_ADDRESS` — we never invent an address, and we never
    silently drop a supplier the employee chose.

    `actor_email` is the email of the user triggering the dispatch. If it is a test persona
    (`@probe.test` / `@testco.com`), the real email is suppressed unconditionally (guard 3 in the
    module docstring) — the token still mints and the link is returned, but nothing is emailed.
    Every real call site MUST pass it; a missing/unknown actor is treated as non-test (fail-open on
    the identity so a legitimate HR send is never silently swallowed — the flag + address guards
    still gate real sends).

    Returns one result per target. Never raises.
    """
    resend_key = os.getenv("RESEND_API_KEY")
    # Guard 3: a test persona can never trigger a real send, even with the flag on and a key set.
    actor_is_test = looks_like_test_email(actor_email)
    if actor_is_test and send_email:
        log.warning(
            "AIQ-1521 dispatch: test-persona sender (%s) — real email SUPPRESSED for rfq=%s "
            "(tokens still minted; links returned). request_id=%s",
            actor_email, rfq_id, request_id,
        )
    results: List[Dict[str, Any]] = []

    # The brief goes IN the email. A vendor who cannot see the route, the date and the scope
    # without clicking has no reason to click — and their silence would be misread as
    # "suppliers don't respond" when it is really "we asked badly".
    brief_rows: List[Dict[str, str]] = []
    try:
        rfq = db.get_rfq(rfq_id) or {}
        for item in rfq.get("items") or []:
            brief_rows.extend(render_brief_lines(item.get("requirements") or {}))
    except Exception:
        log.warning("AIQ-1521 could not build the brief for rfq=%s — sending without it", rfq_id)
    deadline = respond_by()
    subject = rfq_email_subject(brief_rows)

    for target in targets:
        email = (target.get("email") or "").strip()
        name = target.get("supplier_name") or ""
        if not email:
            results.append({
                "recipient_id": target.get("recipient_id"),
                "supplier_name": name,
                "ok": False,
                "sent": False,
                "error": NO_ADDRESS,
            })
            continue
        # Guard: personal/webmail domains are placeholders, not business contacts.
        # A supplier with a @gmail.com address was set up with a test value.
        # Null out the catalog row and retry — do not send to a personal inbox.
        _domain = email.split("@")[-1].lower() if "@" in email else ""
        if _domain in _PERSONAL_DOMAINS:
            log.error(
                "AIQ-1533 dispatch blocked — personal domain in catalog "
                "rfq=%s recipient=%s email_domain=%s",
                rfq_id, target.get("recipient_id"), _domain,
            )
            results.append({
                "recipient_id": target.get("recipient_id"),
                "supplier_name": name,
                "ok": False,
                "sent": False,
                "error": f"placeholder email detected (@{_domain}); update the supplier catalog",
            })
            continue
        # Guard: an address is only dispatchable once its provenance is verified. A scraped or
        # crowd-sourced address with verified=False stays uncontacted — an honest gap the UI already
        # surfaces (AIQ-1521 not_contacted) rather than a guess we mail the employee's details to.
        if not target.get("verified"):
            log.warning(
                "AIQ-1533 dispatch skipped — unverified supplier address "
                "rfq=%s recipient=%s", rfq_id, target.get("recipient_id"),
            )
            results.append({
                "recipient_id": target.get("recipient_id"),
                "supplier_name": name,
                "ok": False,
                "sent": False,
                "error": UNVERIFIED_ADDRESS,
            })
            continue

        try:
            token = generate_supplier_token(
                recipient_id=str(target["recipient_id"]),
                rfq_id=str(rfq_id),
                vendor_id=str(target["vendor_id"]),
                email=email,
            )
            link = f"{APP_BASE_URL}/supplier/quote?token={token}"

            now = datetime.now(tz=timezone.utc).isoformat()
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE rfq_recipients SET token_hash = :h, invited_email = :e, "
                        "invited_at = :now, expires_at = :exp, revoked_at = NULL, status = 'sent', "
                        "last_activity_at = :now WHERE id = :id"
                    ),
                    {
                        "h": hash_token(token),
                        "e": email,
                        "now": now,
                        "exp": expires_at().isoformat(),
                        "id": str(target["recipient_id"]),
                    },
                )
        except Exception as e:
            # Minting/persisting failed for this one supplier. Say so; carry on with the rest.
            log.warning(
                "AIQ-1521 could not mint link rfq=%s recipient=%s request_id=%s error=%s",
                rfq_id, target.get("recipient_id"), request_id, e, exc_info=True,
            )
            results.append({
                "recipient_id": target.get("recipient_id"),
                "supplier_name": name,
                "ok": False,
                "sent": False,
                "error": "could not create the link",
            })
            continue

        sent = False
        error: Optional[str] = None
        if send_email and actor_is_test:
            # Guard 3 (hard): the sender is a test persona — never email a real supplier.
            # The link is already minted and returned below, so the QA flow works end-to-end
            # virtually; this only stops the outbound message.
            error = "test-persona sender — real email suppressed (safeguard)"
        elif send_email and resend_key:
            try:
                r = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": EMAIL_FROM,
                        "to": [email],
                        "subject": subject,
                        "html": rfq_email_html(name, link, brief_rows, deadline),
                    },
                    timeout=15,
                )
                sent = r.status_code < 300
                if not sent:
                    error = f"resend {r.status_code}: {r.text[:160]}"
            except Exception as e:  # a mail failure must never lose the minted link
                error = str(e)[:160]
        elif send_email and not resend_key:
            error = "RESEND_API_KEY not set — nothing was sent; use the link below"

        results.append({
            "recipient_id": str(target["recipient_id"]),
            "supplier_name": name,
            "email": email,
            "ok": True,
            "sent": sent,
            "error": error,
            # Returned so a human can review it, or open it themselves, before anything goes out.
            "link": link,
        })

    log.info(
        "AIQ-1521 dispatch rfq=%s targets=%s minted=%s emailed=%s no_address=%s "
        "actor_is_test=%s request_id=%s",
        rfq_id, len(targets),
        sum(1 for r in results if r.get("ok")),
        sum(1 for r in results if r.get("sent")),
        sum(1 for r in results if r.get("error") == NO_ADDRESS),
        actor_is_test,
        request_id,
    )
    return results
