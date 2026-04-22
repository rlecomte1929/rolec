"""
Minimal JWT payload decoder. No signature verification — callers must trust
the token source (e.g. Supabase session tokens, already verified upstream).

Replaces `jose.jwt.get_unverified_claims` so the `python-jose` dep can be
dropped. python-jose had CVE-2024-33663 / CVE-2024-33664 (algorithm
confusion in signature verification) — not a risk for unverified decoding,
but removing the dep eliminates the concern entirely.
"""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Dict


class InvalidJWT(ValueError):
    """Raised when a string is not a parseable JWT."""


def get_unverified_claims(token: str) -> Dict[str, Any]:
    """
    Decode the claims (payload) segment of a JWT without verifying the signature.

    Matches the semantics of `jose.jwt.get_unverified_claims`: returns the
    decoded JSON object, raises on malformed input.
    """
    if not token or not isinstance(token, str):
        raise InvalidJWT("token is empty or not a string")
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidJWT("token does not have three segments")
    payload_b64 = parts[1]
    # base64url may omit padding; restore it.
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError) as exc:
        raise InvalidJWT(f"payload segment is not valid base64url: {exc}") from exc
    try:
        claims = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise InvalidJWT(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(claims, dict):
        raise InvalidJWT("payload is not a JSON object")
    return claims
