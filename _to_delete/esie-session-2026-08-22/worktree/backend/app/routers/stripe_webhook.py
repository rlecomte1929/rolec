"""Stripe webhook — Path A (direct Stripe → Render). Portable-webhook spec §4.

The only transport wired today. Path B (the Audos relay) forwards the same raw bytes
into this exact route, so there is nothing Audos-specific here — this endpoint verifies
the Stripe signature itself and never trusts the relay.

Non-negotiables baked in (spec §4):
  * signature verification runs on the RAW request bytes — if FastAPI parsed the JSON and
    we re-serialised it, the bytes would change and every signature would fail;
  * `STRIPE_WEBHOOK_SECRET` is a COMMA-SEPARATED list (one signing secret per registered
    Stripe endpoint) so Render + Audos can run at once during cutover, verification tries
    each in turn — switching transports is a Stripe-dashboard change, not a redeploy;
  * only a genuinely invalid signature is a 400; duplicate / ignored / applied are ALL
    200, or Stripe retries forever;
  * `RELOPASS_STRIPE_ENABLED` is a kill switch — off → 503, fulfil nothing;
  * verification uses the SDK's `construct_event` (timing-safe HMAC + timestamp
    tolerance) — never a hand-rolled HMAC.

⚠️ Registered in BOTH backend/app/main.py AND backend/main.py, and exempted from the
SEC-004 rate limiter (Stripe bursts + retries must not be throttled). See the spec §4.1.
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..db import SessionLocal
from ..services.stripe_fulfillment import fulfil_stripe_event

try:
    # The SDK is the mandated verifier (spec §4). Guard the import so that if the
    # dependency is ever missing this ONE route degrades to 503 (same bucket as the
    # kill switch) instead of crashing app import — this router is registered in the
    # monolith that serves ALL traffic.
    import stripe
except Exception:  # pragma: no cover - defensive
    stripe = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return os.getenv("RELOPASS_STRIPE_ENABLED", "false").strip().lower() in _TRUTHY


def _webhook_secrets() -> List[str]:
    raw = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _verify(raw: bytes, sig: str, secrets: List[str]) -> Optional[dict]:
    """Return the verified event dict, or None if no configured secret validates it.

    Tries each secret (dual-endpoint cutover). We parse the *already-authenticated* raw
    bytes with json.loads so the fulfilment brain gets a plain dict with normal .get()
    semantics — construct_event only proves authenticity; the payload is the same bytes.
    """
    for secret in secrets:
        try:
            stripe.Webhook.construct_event(raw, sig, secret)
            return json.loads(raw)
        except Exception:
            continue
    return None


@router.post("/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    # Kill switch / SDK absent → 503, fulfil nothing (spec §7).
    if not _enabled() or stripe is None:
        return JSONResponse(status_code=503, content={"error": "payments disabled"})

    secrets = _webhook_secrets()
    if not secrets:
        logger.error("stripe_webhook: STRIPE_WEBHOOK_SECRET is not configured")
        return JSONResponse(status_code=503, content={"error": "payments not configured"})

    raw = await request.body()  # RAW bytes first — before anything can re-serialise them.
    sig = request.headers.get("Stripe-Signature", "")
    event = _verify(raw, sig, secrets)
    if event is None:
        # 400 ONLY here — an invalid signature is the one genuine client error. Anything
        # else (duplicate, unknown type, missing metadata) is a 200 below.
        return JSONResponse(status_code=400, content={"error": "invalid signature"})

    with SessionLocal() as db:
        result = fulfil_stripe_event(db, event)
    # applied | duplicate | ignored → all 200 so Stripe's retry logic stops (spec §4).
    return JSONResponse(status_code=200, content=result)
