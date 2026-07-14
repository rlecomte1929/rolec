"""AIQ-1521 — supplier magic-link tokens.

A supplier answers an RFQ with NO account. `vendor_users` has never had a single INSERT and
never will: a moving company is not going to register to give us a price.

Deliberately a SIBLING of provider_jwt.py, not a reuse of it:

  * `verify_provider_token` hard-asserts `app_role == "provider"` and a `provider_id` claim.
    Overloading `provider_id` to carry a vendor id would make every /api/provider/* route
    accept a supplier token and then query provider_tasks with a vendor id. Different
    audience, different claims, different verifier.

  * The provider token is STATELESS — verify never touches the DB — so `revoked_at` is honoured
    only at redemption and a revoked link keeps working for its full 7-day life. Submitting a
    quote is a FINANCIAL write. We do not copy that. `resolve_supplier_token` below returns the
    recipient row, and the caller enforces revoked / expired / already-submitted on EVERY
    request (see routers/supplier_rfq.py).

Signed with SUPABASE_JWT_SECRET / HS256, the same as provider_jwt.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

_ALGORITHM = "HS256"
_DEFAULT_EXPIRY_DAYS = 14  # a supplier needs longer than a provider: they have to price the job
APP_ROLE = "supplier"


def _load_secret() -> str:
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise EnvironmentError("SUPABASE_JWT_SECRET is not set — cannot mint supplier tokens")
    return secret


def generate_supplier_token(
    *,
    recipient_id: str,
    rfq_id: str,
    vendor_id: str,
    email: str,
    expires_days: int = _DEFAULT_EXPIRY_DAYS,
) -> str:
    """Mint a magic-link token for ONE rfq_recipients row.

    The token is scoped to a single (rfq, supplier) pair — it can never be replayed against
    another RFQ, and it carries no user identity at all.
    """
    now = datetime.now(tz=timezone.utc)
    claims: Dict[str, Any] = {
        "app_role": APP_ROLE,
        "recipient_id": str(recipient_id),
        "rfq_id": str(rfq_id),
        "vendor_id": str(vendor_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=expires_days)).timestamp()),
    }
    return jwt.encode(claims, _load_secret(), algorithm=_ALGORITHM)


def verify_supplier_token(token: str) -> Dict[str, Any]:
    """Decode + validate. Raises on anything that is not a supplier token."""
    claims = jwt.decode(token, _load_secret(), algorithms=[_ALGORITHM])
    if claims.get("app_role") != APP_ROLE:
        raise ValueError("not a supplier token")
    if not claims.get("recipient_id") or not claims.get("rfq_id"):
        raise ValueError("supplier token is missing its recipient/rfq scope")
    return claims


def hash_token(token: str) -> str:
    """sha256 of the raw token. The raw token is NEVER stored — only this."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expires_at(days: int = _DEFAULT_EXPIRY_DAYS) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=days)
