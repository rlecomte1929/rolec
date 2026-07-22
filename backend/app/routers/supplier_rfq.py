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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from ...database import db
from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..services.rfq_brief import RESPONSE_EXPECTATIONS, RESPONSE_WINDOW_DAYS, render_brief_lines
from ..services.supplier_jwt import hash_token, verify_supplier_token
from ..services.supplier_link_dispatch import dispatch_supplier_links, resolve_rfq_targets

router = APIRouter(prefix="/api/supplier", tags=["supplier-rfq"])
# The HR/admin side: minting and sending the links. Same module, because the two halves are one
# feature and reading them apart hides the contract.
hr_router = APIRouter(prefix="/api/hr", tags=["supplier-rfq"])
log = logging.getLogger(__name__)


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

    # The vendor gets a real BRIEF, not a service name and a shrug: the facts we hold, the gaps
    # marked "Not specified" rather than guessed, and an explicit statement of what a good answer
    # looks like. Without it they cannot price the job — and a vendor who cannot price does not
    # reply, which reads as "suppliers don't respond" when the truth is "we asked badly".
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
    """Who to send to.

    `email` is OPTIONAL: dispatch now reads the address from `suppliers.contact_email`. Supplying
    it here overrides that — the escape hatch for the (common) case where the catalog has no
    address for a supplier HR knows how to reach. Omit it and the stored address is used; if
    there is none either, that supplier is reported as not contacted rather than guessed at.
    """
    recipient_id: str
    email: Optional[EmailStr] = None
    supplier_name: Optional[str] = None


class SendSupplierLinksPayload(BaseModel):
    targets: List[SupplierLinkTarget]
    # Default OFF. Minting a link is harmless; emailing a real company is not. The caller has to
    # ask for the send, explicitly.
    send_email: bool = False


@hr_router.post("/rfqs/{rfq_id}/supplier-links")
def send_supplier_links(
    rfq_id: str,
    payload: SendSupplierLinksPayload,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
):
    """AIQ-1521: mint one magic link per recipient, and (optionally) email it.

    HR/admin path. The employee's own RFQ dispatches itself on create (POST /api/rfqs) — both go
    through the same `dispatch_supplier_links`, so there is one implementation to reason about.
    This route stays for the cases HR still owns: re-sending a link, or reaching a supplier whose
    address is not in the catalog.

    Sending is OPT-IN (`send_email`), and with no RESEND_API_KEY set nothing is sent at all — the
    links are returned instead. Both are deliberate: this feature exists to email real companies
    who have never heard of us, and that must never happen by accident.
    """
    rfq = db.get_rfq(rfq_id)
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    # AIQ-1672: company-scope this dispatch — the RFQ's case must belong to the caller's org.
    # Without it, any HR/admin could mint tokens (and, with send_email, email suppliers) on
    # ANOTHER company's RFQ by enumerating rfq_ids — a cross-tenant IDOR on an external-contact
    # action. Mirrors hr_coordination.dispatch_case_rfq. 404 (not 403) so RFQ existence is not
    # leaked across tenants, and we bail BEFORE resolving targets or dispatching anything.
    with db.engine.begin() as conn:
        owned = conn.execute(
            text(
                "SELECT 1 FROM rfqs r WHERE CAST(r.id AS TEXT) = :rid AND ("
                " EXISTS (SELECT 1 FROM relocation_cases c"
                "         WHERE CAST(c.id AS TEXT) = CAST(r.case_id AS TEXT) AND CAST(c.company_id AS TEXT) = :org)"
                " OR EXISTS (SELECT 1 FROM cases c"
                "            WHERE CAST(c.id AS TEXT) = CAST(r.case_id AS TEXT) AND CAST(c.company_id AS TEXT) = :org)"
                ") LIMIT 1"
            ),
            {"rid": rfq_id, "org": org_id},
        ).first()
    if not owned:
        raise HTTPException(status_code=404, detail="RFQ not found")

    # Recipients of THIS rfq, with the address we hold. Anything the caller names that is not a
    # recipient of this RFQ is rejected — the token is scoped to the RFQ, so accepting a foreign
    # recipient_id would mint a link into someone else's request.
    known = {t["recipient_id"]: t for t in resolve_rfq_targets(rfq_id)}

    targets: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    for target in payload.targets:
        base = known.get(str(target.recipient_id))
        if not base:
            results.append({
                "recipient_id": target.recipient_id,
                "ok": False,
                "sent": False,
                "error": "not a recipient of this RFQ",
            })
            continue
        targets.append({
            **base,
            # An explicitly supplied address wins over the catalog's. When HR types an address
            # here they are the human verification for it, so it clears the dispatch verified-gate
            # (AIQ-1533); falling back to the catalog keeps the catalog row's own verified flag.
            "email": str(target.email) if target.email else base.get("email"),
            "verified": True if target.email else base.get("verified", False),
            "supplier_name": target.supplier_name or base.get("supplier_name"),
        })

    results.extend(
        dispatch_supplier_links(
            rfq_id=rfq_id, targets=targets, send_email=payload.send_email,
            actor_email=user.get("email"),
        )
    )
    return {"ok": True, "rfq_ref": rfq.get("rfq_ref"), "results": results}
