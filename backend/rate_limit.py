"""
Shared rate-limiter instance so routers can decorate their endpoints without
importing from backend.main (which would circle back through route registration).

main.py is responsible for:
  - registering the @app.exception_handler(RateLimitExceeded)
  - setting app.state.limiter = limiter

Routers do:
  from backend.rate_limit import limiter
  @limiter.limit("10/minute")
  def some_endpoint(body: X, request: Request): ...

In-memory storage is fine for single-worker Render. To scale to multi-worker,
swap to Redis via slowapi's `storage_uri` kwarg — no route-code changes.
Rate limiting is disabled when RELOPASS_DISABLE_RATE_LIMITS=1 (tests set this
in conftest).
"""
from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Default limit applied to every undecorated route via SlowAPIMiddleware (SEC-004).
# Imported from app.rate_limits (the policy source of truth); that module imports
# nothing from here, so there is no import cycle.
from backend.app.rate_limits import STANDARD_LIMIT

# Default limit applied to every undecorated route via SlowAPIMiddleware (SEC-004).
# Imported from app.rate_limits (the policy source of truth); that module imports
# nothing from here, so there is no import cycle.
from backend.app.rate_limits import STANDARD_LIMIT


def _real_remote_address(request: Request) -> str:
    """
    Client IP for rate-limit keying. Prefers X-Forwarded-For's first hop so
    Render/Cloudflare proxies don't collapse all users into one bucket.
    Safe on Render because the only ingress path appends to XFF.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        first = xff.split(",", 1)[0].strip()
        if first:
            return first
    return get_remote_address(request)


_RATE_LIMITS_ENABLED = os.getenv("RELOPASS_DISABLE_RATE_LIMITS", "").lower() not in ("1", "true", "yes")

limiter = Limiter(
    key_func=_real_remote_address,
    enabled=_RATE_LIMITS_ENABLED,
    default_limits=[STANDARD_LIMIT],
)
