"""AIQ-1521 — mint a supplier magic link and (optionally) email it.

Lifted out of `routers/supplier_rfq.py` so the EMPLOYEE can dispatch their own RFQ. That is the
whole point of the employee-led model: HR pre-approves *who* and *how much*, then the employee
runs the RFQ themselves. Routing dispatch through an HR-only endpoint put HR right back in the
middle of the step we set out to remove them from.

Two callers, one path:
  - POST /api/rfqs                       (employee or HR — dispatch on create)
  - POST /api/hr/rfqs/{id}/supplier-links (HR/admin — explicit, can override the address)

SAFETY. Emailing a real company that has never heard of us must never happen by accident. Two
independent guards, and BOTH must hold before a message goes out:
  1. `send_email` is False by default at every call site.
  2. An address is only ever taken from `suppliers.contact_email`. A supplier with no address on
     record is not an error and not a guess — it is reported, honestly, as not contacted.
Neither guard is a feature flag; the flag (SUPPLIER_RFQ_DISPATCH_ENABLED) sits above them at the
RFQ-create call site. A mail failure never raises: the RFQ and the minted link survive it.
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
from .supplier_jwt import expires_at, generate_supplier_token, hash_token

log = logging.getLogger(__name__)

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://relopass.com")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@relopass.com")

NO_ADDRESS = "no contact email on record"


def rfq_email_html(supplier_name: str, link: str) -> str:
    # Escape before interpolating. `supplier_name` is NOT trusted input: the catalog is partly
    # crowd-sourced (HR vendor-curation) and partly LLM-scraped, so a name can carry markup. The
    # blast radius is small — the mail goes to that supplier — but an unescaped f-string into an
    # HTML body is how this stops being small later.
    safe_name = escape(supplier_name or "")
    safe_link = escape(link, quote=True)
    return f"""
      <div style="font-family:Inter,Arial,sans-serif;color:#0b2b43;line-height:1.5">
        <p>Hello{(' ' + safe_name) if safe_name else ''},</p>
        <p>A company relocating an employee would like a quote from you.</p>
        <p>You can see what they need and send your price here — there is no account to create
           and nothing to install:</p>
        <p><a href="{safe_link}"
              style="display:inline-block;background:#1f8e8b;color:#fff;padding:12px 20px;
                     border-radius:8px;text-decoration:none;font-weight:600">
             View the request and quote
           </a></p>
        <p style="color:#64748b;font-size:13px">The link is unique to you and expires in 14 days.</p>
        <p style="color:#64748b;font-size:13px">ReloPass</p>
      </div>
    """


def resolve_rfq_targets(rfq_id: str) -> List[Dict[str, Any]]:
    """Every recipient of this RFQ, with the address we hold for them (or None).

    The address comes from `suppliers.contact_email`. It is NULL for most of the catalog, so a
    None here is the normal case, not a fault — the caller reports it rather than dropping it.
    """
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT r.id AS recipient_id, r.vendor_id, s.name AS supplier_name, "
                "       s.contact_email "
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
        }
        for r in rows
    ]


def dispatch_supplier_links(
    *,
    rfq_id: str,
    targets: List[Dict[str, Any]],
    send_email: bool = False,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Mint one link per target, persist it, and email it if asked to.

    Each target: {recipient_id, vendor_id, supplier_name, email|None}. A target with no email is
    skipped with `ok: False, error: NO_ADDRESS` — we never invent an address, and we never
    silently drop a supplier the employee chose.

    Returns one result per target. Never raises.
    """
    resend_key = os.getenv("RESEND_API_KEY")
    results: List[Dict[str, Any]] = []

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
        if send_email and resend_key:
            try:
                r = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": EMAIL_FROM,
                        "to": [email],
                        "subject": "A relocation company would like a quote from you",
                        "html": rfq_email_html(name, link),
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
        "AIQ-1521 dispatch rfq=%s targets=%s minted=%s emailed=%s no_address=%s request_id=%s",
        rfq_id, len(targets),
        sum(1 for r in results if r.get("ok")),
        sum(1 for r in results if r.get("sent")),
        sum(1 for r in results if r.get("error") == NO_ADDRESS),
        request_id,
    )
    return results
