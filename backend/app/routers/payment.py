"""
Per-move roadmap paywall — Stripe Checkout (TEST MODE).

Exposes:
  POST /api/payment/checkout   — create a Stripe Checkout session for the
                                 €800 roadmap unlock, return { checkoutUrl }.

Contract mirrors the Audos reference package
(`docs/stripe-relopass-package/03-backend/relopass-payments.routes.ts`) adapted
to FastAPI: the client posts { assignmentId, tier }, the server prices the
session server-side (€800 = 80000 cents EUR — never trust a client price) and
returns the Stripe-hosted checkout URL. The frontend (`RoadmapPaywallGate`)
redirects the browser there; on return `?payment=success` lands on the employee
dashboard and the roadmap unlocks (see `frontend/src/utils/paymentStatus.ts`).

Keys are read from the environment (`STRIPE_SECRET_KEY`, sk_test_… in this
phase) — never committed, never logged. No webhook signature verification lives
here (that is the portable-webhook work, deliberately untouched).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from ..auth_deps import require_assignment_visibility, require_case_access, require_hr_or_employee
from ..db import SessionLocal
from ..services.pii_masker import safe_log_text
from ..services.roadmap_entitlement import (
    PAID_TIERS,
    resolve_entitlement,
    roadmap_paywall_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment", tags=["payment"])

# Authoritative roadmap price. Mirrors the €800 shown in RoadmapPaywallGate and
# `PRICE_ROADMAP_CENTS` in the reference package — keep the two in sync.
ROADMAP_AMOUNT_CENTS = 80000
CURRENCY = "eur"
STRIPE_CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"

_TRUTHY = {"1", "true", "yes", "on"}


def _stripe_enabled() -> bool:
    """Master kill switch — mirrors the webhook. Checkout 503s when off (spec §7)."""
    return os.getenv("RELOPASS_STRIPE_ENABLED", "false").strip().lower() in _TRUTHY


def _resolve_billable_case_id(assignment: Dict[str, Any]) -> Optional[str]:
    """The canonical relocation_cases.id this assignment bills against — the value the
    webhook's fulfilment brain flips access_tier on (it keys on metadata.case_id, matched
    as relocation_cases.id::text). Prefer canonical_case_id, else case_id; return whichever
    actually exists in relocation_cases so a completed payment is always fulfillable. None
    when neither resolves — checkout then refuses rather than taking un-fulfillable money.
    """
    candidates = [str(c).strip() for c in
                  (assignment.get("canonical_case_id"), assignment.get("case_id")) if c]
    if not candidates:
        return None
    with SessionLocal() as db:
        for cid in candidates:
            hit = db.execute(
                text("SELECT 1 FROM relocation_cases WHERE id::text = :cid LIMIT 1"),
                {"cid": cid},
            ).first()
            if hit:
                return cid
    return None


class CheckoutRequest(BaseModel):
    assignmentId: str
    tier: str = "roadmap"


def _app_base_url() -> str:
    # Same convention as providers.py / provider_portal.py — never invent a domain.
    return os.getenv("APP_BASE_URL", "https://app.relopass.com").rstrip("/")


@router.post("/checkout")
def create_checkout(
    body: CheckoutRequest,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> JSONResponse:
    # Master kill switch (spec §7) — no checkout session while payments are off.
    if not _stripe_enabled():
        return JSONResponse(status_code=503, content={"error": "Payments are not enabled."})

    if body.tier != "roadmap":
        return JSONResponse(
            status_code=400,
            content={"error": "Unsupported tier — only 'roadmap' is available."},
        )
    if not body.assignmentId.strip():
        return JSONResponse(status_code=400, content={"error": "assignmentId is required."})

    # Authorisation: the caller must be able to see this assignment/case. Without this,
    # the endpoint was unauthenticated — anyone could create a Stripe checkout session for
    # any assignmentId (unauthenticated resource consumption + IDOR). This rejects
    # unauthenticated callers (401 via the dependency) and cross-case access (403/404).
    assignment = require_assignment_visibility(body.assignmentId, user)

    # Resolve the relocation_cases id the webhook will fulfil against, and set it as
    # metadata.case_id. WITHOUT this the payment succeeds but the fulfilment brain (which
    # keys on metadata.case_id) can never find the case → paid-but-not-unlocked. If no
    # billable case resolves, refuse checkout rather than take un-fulfillable money.
    billable_case_id = _resolve_billable_case_id(assignment)
    if not billable_case_id:
        logger.error("checkout: no billable relocation_cases id for assignment %s",
                     safe_log_text(body.assignmentId))
        return JSONResponse(
            status_code=409,
            content={"error": "This case isn't set up for payment yet. Please contact support."},
        )

    secret_key = os.getenv("STRIPE_SECRET_KEY")
    if not secret_key:
        logger.error("STRIPE_SECRET_KEY is not configured — cannot create a checkout session.")
        return JSONResponse(
            status_code=500,
            content={"error": "Payments are not configured. Please contact support."},
        )

    app_base = _app_base_url()
    # Both return to the ROADMAP the user paid to unlock — NOT the dashboard, which bounces
    # a mid-journey case to /employee/welcome. By the time the page loads the webhook has
    # usually flipped access_tier; the page re-checks status on ?payment=success (short poll)
    # so it shows the roadmap rather than the paywall if the flip is a beat behind.
    success_url = f"{app_base}/employee/case/{body.assignmentId}/roadmap?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{app_base}/employee/case/{body.assignmentId}/roadmap?payment=cancelled"

    # Stripe's form-encoded API — pricing is fixed server-side (price_data), so a
    # forged client amount cannot change what Stripe charges.
    form = {
        "mode": "payment",
        "currency": CURRENCY,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": CURRENCY,
        "line_items[0][price_data][unit_amount]": str(ROADMAP_AMOUNT_CENTS),
        "line_items[0][price_data][product_data][name]": "ReloPass roadmap unlock",
        "metadata[case_id]": billable_case_id,   # what the webhook fulfils against
        "metadata[assignmentId]": body.assignmentId,
        "metadata[tier]": body.tier,
        "metadata[source]": "relopass_roadmap",
    }

    try:
        resp = requests.post(
            STRIPE_CHECKOUT_URL,
            data=form,
            auth=(secret_key, ""),
            timeout=20,
        )
    except requests.RequestException:
        logger.exception("Stripe checkout request failed (transport).")
        return JSONResponse(
            status_code=502,
            content={"error": "Could not reach the payment provider. Please try again."},
        )

    if resp.status_code >= 400:
        # Stripe's error message is safe to log (no card data); do not surface it raw.
        logger.error("Stripe checkout creation failed (%s): %s", resp.status_code, resp.text[:500])
        return JSONResponse(
            status_code=502,
            content={"error": "Could not start checkout. Please try again."},
        )

    checkout_url = resp.json().get("url")
    if not checkout_url:
        logger.error("Stripe returned no checkout URL.")
        return JSONResponse(
            status_code=502,
            content={"error": "Could not start checkout. Please try again."},
        )

    return JSONResponse(content={"checkoutUrl": checkout_url})


@router.get("/status/{case_id}")
def payment_status(
    case_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> JSONResponse:
    """Server-side entitlement for a case's roadmap — the replacement for the
    client-trusted localStorage unlock. The frontend reads THIS, never a local flag.

    Visibility-scoped (require_case_access → 404/403). `roadmap_unlocked` is the single
    boolean the UI should gate on; it is True while the paywall flag is off (default) so
    nothing changes for existing users until payments go live.
    """
    require_case_access(case_id, user)
    ent = resolve_entitlement(case_id)
    tier = (ent or {}).get("access_tier") or "free"
    unlocked = (not roadmap_paywall_enabled()) or ent is None or tier in PAID_TIERS
    return JSONResponse(content={
        "case_id": case_id,
        "access_tier": tier,
        "payment_status": (ent or {}).get("payment_status") or "unpaid",
        "roadmap_unlocked": unlocked,
    })
