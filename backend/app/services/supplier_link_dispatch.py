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
import uuid
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


def _mint_link(rfq_id: str, target: Dict[str, Any], email: str) -> str:
    """Generate a supplier token, persist its hash on the recipient row, and return the magic link.

    Shared by both dispatch modes. `email` may be "" in inbox mode (no address on record): the
    token carries the address only as an unchecked claim, and the invite row stores NULL rather
    than a blank string when we hold no address.
    """
    token = generate_supplier_token(
        recipient_id=str(target["recipient_id"]),
        rfq_id=str(rfq_id),
        vendor_id=str(target["vendor_id"]),
        email=email or "",
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
                "e": email or None,
                "now": now,
                "exp": expires_at().isoformat(),
                "id": str(target["recipient_id"]),
            },
        )
    return link


def _post_inbox_message(rfq_id: str, supplier_name: str, link: str) -> None:
    """Surface the supplier magic link in the in-app inbox (INBOX dispatch mode).

    The employee's inbox reads `quote_conversations` + `quote_messages` (InboxV2Page ->
    list_quote_threads_for_employee). `db.create_rfq` already opened one conversation per RFQ; here
    we add a message carrying the working link, so the loop is runnable end to end with NO email
    leaving the building.

    `quote_messages.sender_user_id` FKs `auth.users(id)`, so the notice must be attributed to a real
    Supabase auth user — there is no system user, and the RFQ creator id is frequently a legacy TEXT
    value (e.g. "seed-emp-testingapril") that is neither a uuid nor in auth.users. We resolve the
    creator's auth uuid by email (the same direct-SELECT pattern supabase_auth_sync uses — GoTrue has
    no get-by-email) and attribute the notice to them: it is their RFQ and their thread.

    Best-effort: a missing conversation, an unresolvable sender, or any write error is swallowed by
    the caller — the minted token stands on its own and the HR RFQ read surfaces the recipient
    regardless.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT qc.id AS conv_id, u.email AS creator_email "
                "FROM quote_conversations qc "
                "JOIN rfqs r ON r.id = qc.rfq_id "
                "LEFT JOIN users u ON u.id = r.created_by_user_id "
                "WHERE qc.rfq_id = :rfq ORDER BY qc.created_at LIMIT 1"
            ),
            {"rfq": str(rfq_id)},
        ).mappings().first()
        if not row or not row.get("conv_id"):
            return
        email = (row.get("creator_email") or "").strip().lower()
        if not email:
            return
        sender = conn.execute(
            text("SELECT id FROM auth.users WHERE lower(email) = :e ORDER BY created_at LIMIT 1"),
            {"e": email},
        ).scalar()
        if not sender:
            return
        body = (
            f"Quote request ready for {supplier_name}. They can open it and reply with a price — "
            f"no account needed: {link}"
        )
        conn.execute(
            text(
                "INSERT INTO quote_messages (id, conversation_id, sender_user_id, body, created_at) "
                "VALUES (:id, :cid, :sender, :body, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "cid": str(row["conv_id"]),
                "sender": str(sender),
                "body": body,
                "now": now,
            },
        )


def dispatch_supplier_links(
    *,
    rfq_id: str,
    targets: List[Dict[str, Any]],
    send_email: bool = False,
    dispatch_mode: str = "inbox",
    actor_email: Optional[str] = None,
    request_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Mint one link per target and deliver it according to `dispatch_mode`.

    Two modes, one seam:
      * ``"inbox"`` (default): mint the token for EVERY recipient and surface the working link in
        the in-app inbox. No address is required, and the verified / personal-domain guards do NOT
        apply — those exist only to protect email egress, and inbox mode emails no one. Resend is
        never called. This is what makes the loop live without spending a single email. The future
        go-live on email is one config flip (`dispatch_mode="email"`), not a rewrite.
      * ``"email"``: the address-and-provenance guards apply (no address / unverified /
        personal-domain -> not contacted, no token minted), then the link is emailed via Resend
        when ``send_email`` is set — unless the acting user is a test persona (guard 3).

    Each target: {recipient_id, vendor_id, supplier_name, email|None, verified}.

    `actor_email` is the email of the user triggering the dispatch (email mode only). If it is a
    test persona (`@probe.test` / `@testco.com`), the real email is suppressed unconditionally
    (guard 3) — the token still mints and the link is returned, but nothing is emailed. A
    missing/unknown actor is treated as non-test (fail-open on identity).

    Returns one result per target. Never raises.
    """
    mode = "email" if dispatch_mode == "email" else "inbox"
    resend_key = os.getenv("RESEND_API_KEY")
    # Guard 3: a test persona can never trigger a real send, even with the flag on and a key set.
    actor_is_test = looks_like_test_email(actor_email)
    if mode == "email" and actor_is_test and send_email:
        log.warning(
            "AIQ-1521 dispatch: test-persona sender (%s) — real email SUPPRESSED for rfq=%s "
            "(tokens still minted; links returned). request_id=%s",
            actor_email, rfq_id, request_id,
        )
    results: List[Dict[str, Any]] = []

    # The brief goes IN the email. Only needed for the email body, so skip it in inbox mode (the
    # link is carried by the inbox message, not by a rendered email).
    brief_rows: List[Dict[str, str]] = []
    deadline = respond_by()
    subject = ""
    if mode == "email":
        try:
            rfq = db.get_rfq(rfq_id) or {}
            for item in rfq.get("items") or []:
                brief_rows.extend(render_brief_lines(item.get("requirements") or {}))
        except Exception:
            log.warning("AIQ-1521 could not build the brief for rfq=%s — sending without it", rfq_id)
        subject = rfq_email_subject(brief_rows)

    for target in targets:
        email = (target.get("email") or "").strip()
        name = target.get("supplier_name") or ""

        # ── INBOX mode ────────────────────────────────────────────────────────────────────────
        # No email leaves the building, so the deliverability guards do not apply: mint for every
        # recipient the employee chose — address or not, verified or not — and surface the link
        # in-app. This is precisely why the addressless catalog (schools, most movers) can still
        # run the loop; the "token_hash for all recipients" outcome is only reachable here.
        if mode == "inbox":
            try:
                link = _mint_link(rfq_id, target, email)
            except Exception as e:
                log.warning(
                    "inbox dispatch could not mint link rfq=%s recipient=%s request_id=%s error=%s",
                    rfq_id, target.get("recipient_id"), request_id, e, exc_info=True,
                )
                results.append({
                    "recipient_id": target.get("recipient_id"),
                    "supplier_name": name,
                    "ok": False, "sent": False, "mode": "inbox",
                    "error": "could not create the link",
                })
                continue
            try:
                _post_inbox_message(rfq_id, name, link)
            except Exception:
                # The token is minted and returned; a failed inbox write must not lose it.
                log.warning(
                    "inbox dispatch could not post inbox message rfq=%s recipient=%s",
                    rfq_id, target.get("recipient_id"), exc_info=True,
                )
            results.append({
                "recipient_id": str(target["recipient_id"]),
                "supplier_name": name,
                "email": email or None,
                "ok": True, "sent": False, "mode": "inbox",
                "error": None, "queued_inbox": True,
                "link": link,
            })
            continue

        # ── EMAIL mode ────────────────────────────────────────────────────────────────────────
        if not email:
            results.append({
                "recipient_id": target.get("recipient_id"),
                "supplier_name": name,
                "ok": False, "sent": False, "mode": "email",
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
                "ok": False, "sent": False, "mode": "email",
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
                "ok": False, "sent": False, "mode": "email",
                "error": UNVERIFIED_ADDRESS,
            })
            continue

        try:
            link = _mint_link(rfq_id, target, email)
        except Exception as e:
            # Minting/persisting failed for this one supplier. Say so; carry on with the rest.
            log.warning(
                "AIQ-1521 could not mint link rfq=%s recipient=%s request_id=%s error=%s",
                rfq_id, target.get("recipient_id"), request_id, e, exc_info=True,
            )
            results.append({
                "recipient_id": target.get("recipient_id"),
                "supplier_name": name,
                "ok": False, "sent": False, "mode": "email",
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
            "ok": True, "sent": sent, "mode": "email",
            "error": error,
            # Returned so a human can review it, or open it themselves, before anything goes out.
            "link": link,
        })

    log.info(
        "AIQ-1521 dispatch rfq=%s mode=%s targets=%s minted=%s emailed=%s no_address=%s "
        "actor_is_test=%s request_id=%s",
        rfq_id, mode, len(targets),
        sum(1 for r in results if r.get("ok")),
        sum(1 for r in results if r.get("sent")),
        sum(1 for r in results if r.get("error") == NO_ADDRESS),
        actor_is_test,
        request_id,
    )
    return results
