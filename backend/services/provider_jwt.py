"""
Provider JWT — limited-scope access tokens for relocation service providers.

Providers receive a magic link via email. Clicking it gives them a JWT that
grants SELECT + UPDATE access to their own provider_tasks rows via Supabase
RLS JWT-claim policies (provider_tasks_jwt_select / provider_tasks_jwt_update).

Wire format:
  Standard JWT signed with HS256 using SUPABASE_JWT_SECRET (same secret
  Supabase uses to sign auth tokens — RLS can read these claims via
  auth.jwt() or current_setting('request.jwt.claims')).

Required claims (Supabase-compatible):
  {
    "sub":         "<provider_id>",       # used as auth.uid() in RLS
    "iss":         "supabase",
    "aud":         "authenticated",
    "role":        "authenticated",       # Supabase expects this for RLS
    "app_role":    "provider",            # application-level role check
    "provider_id": "<uuid>",             # scopes RLS row access
    "org_id":      "<text>",
    "case_id":     "<text>",
    "email":       "<provider email>",
    "iat":         <unix timestamp>,
    "exp":         <unix timestamp>
  }

Env vars required:
  SUPABASE_JWT_SECRET  — Supabase Dashboard → Settings → API → JWT Secret

Usage:
  from backend.services.provider_jwt import generate_provider_token, verify_provider_token

  token = generate_provider_token("uuid", "org-1", "case-abc", "provider@example.com")
  claims = verify_provider_token(token)  # raises on invalid/expired
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict

log = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_DEFAULT_EXPIRY_DAYS = 7


def _load_secret() -> str:
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise EnvironmentError(
            "SUPABASE_JWT_SECRET is not set. "
            "Find it in: Supabase Dashboard → Settings → API → JWT Secret."
        )
    return secret


def generate_provider_token(
    provider_id: str,
    org_id: str,
    case_id: str,
    email: str,
    expires_days: int = _DEFAULT_EXPIRY_DAYS,
) -> str:
    """
    Generate a Supabase-compatible JWT for a provider.

    Returns the signed JWT string. The token is valid for `expires_days` days
    and can be used directly as a Bearer token against the Supabase client.
    """
    try:
        import jwt  # PyJWT
    except ImportError as exc:
        raise ImportError(
            "PyJWT is required for provider tokens. "
            "Install with: pip install PyJWT"
        ) from exc

    now = int(time.time())
    payload: Dict[str, Any] = {
        # Supabase-required claims
        "sub": provider_id,          # auth.uid() in RLS
        "iss": "supabase",
        "aud": "authenticated",
        "role": "authenticated",
        # Application claims
        "app_role": "provider",
        "provider_id": provider_id,
        "org_id": org_id,
        "case_id": case_id,
        "email": email,
        # Timing
        "iat": now,
        "exp": now + (expires_days * 86400),
    }
    return jwt.encode(payload, _load_secret(), algorithm=_ALGORITHM)


def verify_provider_token(token: str) -> Dict[str, Any]:
    """
    Validate and decode a provider JWT.

    Returns the decoded claims dict on success.
    Raises jwt.ExpiredSignatureError if expired.
    Raises jwt.InvalidTokenError for any other validation failure.
    """
    try:
        import jwt  # PyJWT
    except ImportError as exc:
        raise ImportError("PyJWT is required. pip install PyJWT") from exc

    claims = jwt.decode(
        token,
        _load_secret(),
        algorithms=[_ALGORITHM],
        audience="authenticated",
    )

    # Verify this is a provider token, not a user auth token
    if claims.get("app_role") != "provider":
        raise jwt.InvalidTokenError("Token is not a provider token.")
    if not claims.get("provider_id"):
        raise jwt.InvalidTokenError("Token missing provider_id claim.")

    return claims


def hash_token(token: str) -> str:
    """Return a SHA-256 hex digest of the token for storage in provider_invites."""
    return hashlib.sha256(token.encode()).hexdigest()
