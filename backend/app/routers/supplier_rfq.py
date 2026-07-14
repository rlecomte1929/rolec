"""AIQ-1521 — the supplier side of an RFQ, reachable by magic link and NO account.

THE RISK SPIKE. The employee-led model assumes a supplier will answer an RFQ from a company
they have never heard of. Nothing in the product tests that assumption, and if it is false the
whole model is worth nothing. These routes exist to find out.

Why not the existing vendor route: POST /api/vendor/rfqs/{id}/quotes is guarded by
require_vendor, which resolves the caller through `vendor_users` — a table that has never had a
single INSERT. Suppliers will not register to give us a price, so that route is structurally
unreachable. This is a parallel, token-scoped path that needs no account.

Every request re-reads the invite row and enforces revoked / expired / already-submitted. The
provider magic-link does NOT do this (its JWT is stateless, so a revoked link keeps working for
its full life) — submitting a quote is a financial write and does not get that treatment.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from ...database import db
from ..auth_deps import require_admin_or_hr
from ..services.rfq_brief import RESPONSE_EXPECTATIONS, RESPONSE_WINDOW_DAYS, render_brief_lines, respond_by
from ..services.supplier_jwt import expires_at, generate_supplier_token, hash_token, verify_supplier_token

router = APIRouter(prefix="/api/supplier", tags=["supplier-rfq"])
# The HR/admin side: minting and sending the links. Same module, because the two halves are one
# feature and reading them apart hides the contract.
hr_router = APIRouter(prefix="/api/hr", tags=["supplier-rfq"])
log = logging.getLogger(__name__)

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://relopass.com")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@relopass.com")


class SupplierQuoteLine(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    amount: float


class SupplierQuotePayload(BaseModel):
    currency: str = Field(..., min_length=3, max_length=8)
    total_amount: float
    valid_until: Optional[str] = None
    quote_lines: List[SupplierQuoteLine] = Field(default_factory=list)


def require_supplier_link(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Resolve a supplier magic-link token to its rfq_recipients row.

    Unlike require_provider_jwt (stateless — it never touches the DB), this hits the invite row
    on EVERY request, so revocation and single-submission are actually enforced rather than
    merely recorded.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="This link is missing its token.")
    token = authorization[len("Bearer "):].strip()

    try:
        claims = verify_supplier_token(token)
    except Exception:
        # Covers expiry, a wrong secret, a tampered token, and a provider/user token replayed here.
        raise HTTPException(status_code=401, detail="This link is no longer valid.")

    with db.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, rfq_id, vendor_id, status, revoked_at, expires_at, quote_submitted_at, "
                "invited_email FROM rfq_recipients WHERE token_hash = :h"
            ),
            {"h": hash_token(token)},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="This link is no longer valid.")
    if row.get("revoked_at"):
        raise HTTPException(status_code=403, detail="This request has been withdrawn.")
    if row.get("quote_submitted_at"):
        raise HTTPException(status_code=409, detail="You have already sent a quote for this request.")

    exp = row.get("expires_at")
    if exp and _as_utc(exp) < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=403, detail="This request has expired.")

    if str(row["rfq_id"]) != str(claims["rfq_id"]):
        # The token is scoped to one RFQ. A mismatch means it was tampered with.
        raise HTTPException(status_code=401, detail="This link is no longer valid.")

    return dict(row)


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)


@router.get("/rfq")
def get_supplier_rfq(recipient: Dict[str, Any] = Depends(require_supplier_link)):
    """What the supplier is being asked to price. No account, no login."""
    rfq = db.get_rfq(str(recipient["rfq_id"]))
    if not rfq:
        raise HTTPException(status_code=404, detail="This request no longer exists.")

    # First open -> 'viewed'. This is half the funnel the spike measures: did they even look?
    if not recipient.get("first_viewed_at"):
        try:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE rfq_recipients SET first_viewed_at = :now, status = 'viewed', "
                        "last_activity_at = :now WHERE id = :id AND first_viewed_at IS NULL"
                    ),
                    {"now": datetime.now(tz=timezone.utc).isoformat(), "id": str(recipient["id"])},
                )
        except Exception:
            log.warning("supplier_rfq: could not mark viewed recipient=%s", recipient["id"], exc_info=True)

    # The vendor gets a real brief, not a service name and a shrug: the facts we hold, the gaps
    # marked "Not specified" rather than guessed, and an explicit statement of what a good answer
    # looks like. Without this they cannot price the job — and a vendor who cannot price does not
    # reply, which would look like "suppliers don't respond" when it is "we asked badly".
    return {
        "rfq_ref": rfq.get("rfq_ref"),
        "items": [
            {
                "service_key": i.get("service_key"),
                "brief": render_brief_lines(i.get("requirements") or {}),
            }
            for i in (rfq.get("items") or [])
        ],
        "expectations": RESPONSE_EXPECTATIONS,
        "respond_by": _respond_by_for(recipient),
        "already_quoted": bool(recipient.get("quote_submitted_at")),
    }


def _respond_by_for(recipient: Dict[str, Any]) -> str:
    """A concrete date, not "soon". Anchored to when the link was sent."""
    invited = recipient.get("invited_at")
    try:
        base = _as_utc(invited) if invited else datetime.now(tz=timezone.utc)
    except Exception:
        base = datetime.now(tz=timezone.utc)
    return (base + timedelta(days=RESPONSE_WINDOW_DAYS)).date().isoformat()


@router.post("/rfq/quote")
def submit_supplier_quote(
    payload: SupplierQuotePayload,
    recipient: Dict[str, Any] = Depends(require_supplier_link),
):
    """The supplier gives a price. This is the event the whole spike is waiting for."""
    if payload.total_amount <= 0:
        raise HTTPException(status_code=422, detail="The total must be greater than zero.")

    quote = db.create_quote(
        rfq_id=str(recipient["rfq_id"]),
        vendor_id=str(recipient["vendor_id"]),
        currency=payload.currency.upper(),
        total_amount=payload.total_amount,
        valid_until=payload.valid_until,
        quote_lines=[{"label": ln.label, "amount": ln.amount} for ln in payload.quote_lines],
        # No user id: the supplier has no account. The column is Optional and that is the point.
        created_by_user_id=None,
    )

    now = datetime.now(tz=timezone.utc).isoformat()
    with db.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE rfq_recipients SET quote_submitted_at = :now, status = 'replied', "
                "last_activity_at = :now WHERE id = :id"
            ),
            {"now": now, "id": str(recipient["id"])},
        )

    log.info(
        "AIQ-1521 SUPPLIER QUOTED rfq=%s vendor=%s total=%s %s",
        recipient["rfq_id"], recipient["vendor_id"], payload.total_amount, payload.currency,
    )
    return {"ok": True, "quote_id": quote.get("id")}


# ─────────────────────────────────────────────────────────────────────────────
# HR / admin: mint the links and send them.
# ─────────────────────────────────────────────────────────────────────────────


class SupplierLinkTarget(BaseModel):
    """Who to send to. The address is explicit BECAUSE suppliers.contact_email is NULL for all
    90 suppliers in the catalog — there is nothing to look up. Until supplier contact data
    exists, the sender supplies it."""
    recipient_id: str
    email: EmailStr
    supplier_name: Optional[str] = None


class SendSupplierLinksPayload(BaseModel):
    targets: List[SupplierLinkTarget]
    # Default OFF. Minting a link is harmless; emailing a real company is not. The caller has to
    # ask for the send, explicitly.
    send_email: bool = False


def _rfq_email_html(supplier_name: str, link: str, brief_rows: List[Dict[str, str]], deadline: str) -> str:
    """The vendor must be able to judge the job BEFORE clicking.

    The first version said only "a company would like a quote" — a vendor could not tell the
    route, the date, or the scope without clicking, so there was no reason to. The brief goes in
    the email, and so does what we expect back.

    SECURITY: every interpolated value is HTML-escaped. The brief carries EMPLOYEE free text
    (special_items, property_size, notes) and supplier_name is HR input — this HTML is sent from
    our own domain to an EXTERNAL company, so an unescaped value would let a user inject markup,
    including a link, into mail that appears to come from us. That is a phishing vector, not a
    rendering bug. `escape(quote=True)` also closes attribute breakout on the href.
    """
    rows = "".join(
        f"""<tr>
              <td style="padding:4px 12px 4px 0;color:#64748b;white-space:nowrap">{escape(r['label'])}</td>
              <td style="padding:4px 0;color:#0b2b43;font-weight:600">{escape(r['value'])}</td>
            </tr>"""
        for r in brief_rows
    )
    asks = "".join(f"<li style='margin-bottom:4px'>{escape(e)}</li>" for e in RESPONSE_EXPECTATIONS)
    safe_name = escape(supplier_name or "")
    safe_link = escape(link, quote=True)
    safe_deadline = escape(deadline)
    return f"""
      <div style="font-family:Inter,Arial,sans-serif;color:#0b2b43;line-height:1.5;max-width:560px">
        <p>Hello{(' ' + safe_name) if safe_name else ''},</p>
        <p>A company is relocating an employee and would like a quote from you for the move below.</p>

        <table style="border-collapse:collapse;margin:16px 0;font-size:14px">{rows}</table>

        <p style="margin-bottom:6px"><strong>What we need back by {safe_deadline}:</strong></p>
        <ul style="margin-top:0;padding-left:18px;font-size:14px;color:#334155">{asks}</ul>

        <p><a href="{safe_link}"
              style="display:inline-block;background:#1f8e8b;color:#fff;padding:12px 20px;
                     border-radius:8px;text-decoration:none;font-weight:600">
             Send your quote
           </a></p>
        <p style="color:#64748b;font-size:13px">
          No account to create and nothing to install. The link is unique to you and expires in 14 days.
        </p>
        <p style="color:#64748b;font-size:13px">ReloPass</p>
      </div>
    """


def _subject_for(brief_rows: List[Dict[str, str]]) -> str:
    """A vendor triages on the subject line alone. Put the route in it, so they can tell at a
    glance whether this is a job they even cover."""
    by = {r["label"]: r["value"] for r in brief_rows}
    frm, to = by.get("Move from"), by.get("Move to")
    if frm and to and frm != "Not specified" and to != "Not specified":
        return f"Quote request: household move, {frm} → {to}"
    return "Quote request from a company relocating an employee"


@hr_router.post("/rfqs/{rfq_id}/supplier-links")
def send_supplier_links(
    rfq_id: str,
    payload: SendSupplierLinksPayload,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
):
    """AIQ-1521: mint one magic link per recipient, and (optionally) email it.

    Sending is OPT-IN (`send_email`), and with no RESEND_API_KEY set nothing is sent at all —
    the links are returned instead. Both are deliberate: this feature's whole purpose is to
    email real companies who have never heard of us, and that must never happen by accident.
    """
    rfq = db.get_rfq(rfq_id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    # The brief goes IN the email. A vendor who cannot see the route, the date and the scope
    # without clicking has no reason to click.
    brief_rows: List[Dict[str, str]] = []
    for item in rfq.get("items") or []:
        brief_rows.extend(render_brief_lines(item.get("requirements") or {}))
    deadline = respond_by()

    resend_key = os.getenv("RESEND_API_KEY")
    results: List[Dict[str, Any]] = []

    for target in payload.targets:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, vendor_id FROM rfq_recipients WHERE id = :id AND rfq_id = :rfq"),
                {"id": target.recipient_id, "rfq": rfq_id},
            ).mappings().first()
        if not row:
            results.append({"recipient_id": target.recipient_id, "ok": False, "error": "not a recipient of this RFQ"})
            continue

        token = generate_supplier_token(
            recipient_id=str(row["id"]),
            rfq_id=rfq_id,
            vendor_id=str(row["vendor_id"]),
            email=str(target.email),
        )
        link = f"{APP_BASE_URL}/supplier/quote?token={token}"

        with db.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE rfq_recipients SET token_hash = :h, invited_email = :e, invited_at = :now, "
                    "expires_at = :exp, revoked_at = NULL, status = 'sent', last_activity_at = :now "
                    "WHERE id = :id"
                ),
                {
                    "h": hash_token(token),
                    "e": str(target.email),
                    "now": datetime.now(tz=timezone.utc).isoformat(),
                    "exp": expires_at().isoformat(),
                    "id": str(row["id"]),
                },
            )

        sent = False
        error: Optional[str] = None
        if payload.send_email and resend_key:
            try:
                r = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": EMAIL_FROM,
                        "to": [str(target.email)],
                        "subject": _subject_for(brief_rows),
                        "html": _rfq_email_html(target.supplier_name or "", link, brief_rows, deadline),
                    },
                    timeout=15,
                )
                sent = r.status_code < 300
                if not sent:
                    error = f"resend {r.status_code}: {r.text[:160]}"
            except Exception as e:  # never let a mail failure lose the minted link
                error = str(e)[:160]
        elif payload.send_email and not resend_key:
            error = "RESEND_API_KEY not set — nothing was sent; use the link below"

        results.append({
            "recipient_id": str(row["id"]),
            "email": str(target.email),
            "ok": True,
            "sent": sent,
            "error": error,
            # Returned so a human can review, or open it themselves, before anything goes out.
            "link": link,
        })

    log.info("AIQ-1521 supplier links minted rfq=%s count=%s sent=%s",
             rfq_id, len(results), sum(1 for r in results if r.get("sent")))
    return {"ok": True, "rfq_ref": rfq.get("rfq_ref"), "results": results}
