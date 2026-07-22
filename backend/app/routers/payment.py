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
from typing import Any, Dict

import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth_deps import require_assignment_visibility, require_hr_or_employee

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment", tags=["payment"])

# Authoritative roadmap price. Mirrors the €800 shown in RoadmapPaywallGate and
# `PRICE_ROADMAP_CENTS` in the reference package — keep the two in sync.
ROADMAP_AMOUNT_CENTS = 80000
CURRENCY = "eur"
STRIPE_CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"


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
    require_assignment_visibility(body.assignmentId, user)

    secret_key = os.getenv("STRIPE_SECRET_KEY")
    if not secret_key:
        logger.error("STRIPE_SECRET_KEY is not configured — cannot create a checkout session.")
        return JSONResponse(
            status_code=500,
            content={"error": "Payments are not configured. Please contact support."},
        )

    app_base = _app_base_url()
    # success_url returns to the dashboard, which marks the roadmap unlocked and
    # strips the query params; cancel returns to the gated roadmap page.
    success_url = f"{app_base}/employee/dashboard?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
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
