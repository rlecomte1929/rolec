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
  - AI **and ADMIN** routes key on the authenticated principal (``user_key_func``)
    instead of IP so one tenant can't exhaust a shared NAT/proxy IP bucket, and so
    cost/quota is attributed per user. Uploads stay IP-keyed.
  - The ADMIN bucket is ONE bucket spanning every ``/api/admin/*`` route, so its
    ceiling has to cover a whole admin page-load (several calls) plus the sidebar
    notification poll — not a single endpoint's traffic. See AIQ-1564.

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
# AIQ-1564: was 20/minute, keyed by IP. One bucket covers EVERY /api/admin/* route, so an
# admin browsing normally (6 pages in ~43s, each firing its own admin calls) drained it and
# got 429s — the executive dashboard then rendered every tile as "unavailable". 60/minute
# per authenticated admin fits real navigation while still bounding a stolen-token scrape;
# these routes are already behind require_admin, so this bucket is defence-in-depth.
ADMIN_LIMIT = "60/minute"
AI_LIMIT = "20/minute"
# Parker-I document translation (DeepL/NLLB-backed, per-character billed). Keyed per
# authenticated user so one tenant can't drain a shared NAT/proxy IP bucket.
TRANSLATE_LIMIT = "60/minute"


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


# ── Path-scoped buckets (UPLOAD / ADMIN / AI) ────────────────────────────────
# Enforced by a middleware in backend.main rather than per-route @limiter.limit
# decorators: slowapi 0.1.9 requires the decorated function to declare a parameter
# literally named "request", but most of these routes name it "req" (or, for the
# ~66 admin routes, omit it). Defining the policy here — free of any app/DB import —
# keeps it unit-testable in isolation. Uses slowapi's own `limits` backend.
import re as _re

from limits import parse as _parse_limit
from limits.storage import MemoryStorage as _MemoryStorage
from limits.strategies import FixedWindowRateLimiter as _FixedWindowRateLimiter

RETRY_AFTER_SECONDS = 60  # every named bucket is a 1-minute window

ADMIN_RATE_LIMIT_ITEM = _parse_limit(ADMIN_LIMIT)
UPLOAD_RATE_LIMIT_ITEM = _parse_limit(UPLOAD_LIMIT)
AI_RATE_LIMIT_ITEM = _parse_limit(AI_LIMIT)
TRANSLATE_RATE_LIMIT_ITEM = _parse_limit(TRANSLATE_LIMIT)

_path_rl_storage = _MemoryStorage()
_path_rate_limiter = _FixedWindowRateLimiter(_path_rl_storage)

# Exact-match file-upload routes (UPLOAD bucket, keyed by IP).
UPLOAD_PATHS = frozenset({
    "/api/hr/policies/upload",
    "/api/hr/policy-documents/upload",
    "/api/admin/policies/upload",
    "/api/company-policies/upload",
})
# LLM-backed routes (AI bucket, keyed per authenticated user via user_key_func).
AI_PATHS = frozenset({
    "/api/employee/policy-assistant/query",
    "/api/hr/policy-assistant/query",
    "/api/policy-assistant/rag-query",
    "/api/guidance/generate",
})
_AI_PATH_PATTERNS = (
    _re.compile(r"^/api/admin/policies/[^/]+/extract$"),
    _re.compile(r"^/api/policies/[^/]+/extract$"),
    _re.compile(r"^/api/policies/[^/]+/extract-preview$"),
)


def is_ai_path(path: str) -> bool:
    return path in AI_PATHS or any(p.match(path) for p in _AI_PATH_PATTERNS)


def path_limit(path: str, ip: str, user_key: str):
    """
    Apply the stricter SEC-004 buckets by path, most specific first:
    AI (per user) > uploads (per IP) > admin (per IP). Returns the exceeded limit
    as a string, or None when the request is allowed. Pure + synchronous so it can
    be unit-tested directly without standing up the app.
    """
    if is_ai_path(path):
        if not _path_rate_limiter.hit(AI_RATE_LIMIT_ITEM, "sec004-ai", user_key):
            return str(AI_RATE_LIMIT_ITEM)
        return None
    if path == "/api/translate":
        if not _path_rate_limiter.hit(TRANSLATE_RATE_LIMIT_ITEM, "parker-translate", user_key):
            return str(TRANSLATE_RATE_LIMIT_ITEM)
        return None
    if path in UPLOAD_PATHS:
        if not _path_rate_limiter.hit(UPLOAD_RATE_LIMIT_ITEM, "sec004-upload", ip):
            return str(UPLOAD_RATE_LIMIT_ITEM)
        return None
    if path.startswith("/api/admin/"):
        # AIQ-1564: keyed on the authenticated admin, not the IP — same rationale the AI
        # bucket already uses above. Keying by IP put every admin behind a shared office
        # NAT/proxy into ONE 60/min bucket, so colleagues throttled each other.
        if not _path_rate_limiter.hit(ADMIN_RATE_LIMIT_ITEM, "sec004-admin", user_key):
            return str(ADMIN_RATE_LIMIT_ITEM)
        return None
    return None


def reset_path_limit_storage() -> None:
    """Clear all path-bucket counters. For tests only."""
    global _path_rl_storage, _path_rate_limiter
    _path_rl_storage = _MemoryStorage()
    _path_rate_limiter = _FixedWindowRateLimiter(_path_rl_storage)


def rate_limit_payload(retry: int = RETRY_AFTER_SECONDS) -> dict:
    """Canonical 429 JSON body (SEC-004). `detail`/`request_id` kept for back-compat."""
    return {
        "error": "rate_limit_exceeded",
        "message": f"Too many requests. Retry after {retry}s.",
        "retry_after": retry,
        "detail": "Too many requests. Wait a moment before trying again.",
    }


def rate_limit_headers(retry: int = RETRY_AFTER_SECONDS) -> dict:
    """Canonical 429 headers (SEC-004)."""
    return {"Retry-After": str(retry)}
