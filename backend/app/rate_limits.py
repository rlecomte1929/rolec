"""
Single source of truth for rate-limit policy (SEC-004).

Named limit buckets applied across the API surface. Import these constants and
pass them to ``@limiter.limit(...)`` rather than sprinkling bare strings — the
shared ``limiter`` instance lives in ``backend/rate_limit.py``.

Coverage model:
  - ``STANDARD_LIMIT`` is wired as the limiter's ``default_limits`` and applied
    to every undecorated route by ``SlowAPIMiddleware`` (see backend/main.py).
  - Sensitive groups carry stricter explicit decorators: AUTH on auth endpoints,
    UPLOAD on file uploads, ADMIN on admin endpoints, AI on LLM-backed routes.
  - AI routes key on the authenticated principal (``user_key_func``) instead of
    IP so one tenant can't exhaust a shared NAT/proxy IP bucket, and so cost is
    attributed per user.

Disabled wholesale when RELOPASS_DISABLE_RATE_LIMITS=1 (the limiter's
``enabled`` flag short-circuits both the decorators and the middleware).
"""
from __future__ import annotations

import hashlib

from fastapi import Request
from slowapi.util import get_remote_address

# ── Named limit buckets ──────────────────────────────────────────────────────
AUTH_LIMIT = "5/minute"
STANDARD_LIMIT = "100/minute"
UPLOAD_LIMIT = "10/minute"
ADMIN_LIMIT = "20/minute"
AI_LIMIT = "20/minute"


def _client_ip(request: Request) -> str:
    """
    Client IP for rate-limit keying. Mirrors ``rate_limit._real_remote_address``
    (kept as a local copy to avoid a circular import: rate_limit.py imports
    STANDARD_LIMIT from this module). Prefers X-Forwarded-For's first hop so
    Render/Cloudflare proxies don't collapse all users into one bucket.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        first = xff.split(",", 1)[0].strip()
        if first:
            return first
    return get_remote_address(request)


def user_key_func(request: Request) -> str:
    """
    Rate-limit key for cost-controlled AI endpoints: key on the authenticated
    principal so a single user can't drain a shared IP bucket and so per-user
    cost is enforced. ReloPass uses opaque bearer session tokens (not JWTs), so
    we key on a stable hash of the token; falls back to client IP when
    unauthenticated. Must never raise — a raising key_func would 500 the request.
    """
    try:
        authorization = request.headers.get("authorization", "")
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
                digest = hashlib.sha256(parts[1].encode("utf-8")).hexdigest()[:32]
                return f"user:{digest}"
    except Exception:  # pragma: no cover - defensive; fall back to IP
        pass
    return _client_ip(request)
