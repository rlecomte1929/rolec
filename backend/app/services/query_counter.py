"""
Query counter — AUDIT-B7 / PERF-5
==================================

Per-request SQL query counter. Surfaces N+1 patterns hidden behind list
endpoints (e.g. "list 25 cases + per-case provider status fan-out") without
having to manually instrument every handler.

How it works
------------
1. A SQLAlchemy `before_cursor_execute` event listener increments a
   `ContextVar` every time a query starts.
2. A FastAPI middleware (`QueryCountMiddleware`) resets the ContextVar at
   the start of every request, snapshots it at the end, and logs:

       route=GET /api/cases route_count=15 threshold=10 status=OVER

3. When the snapshot exceeds the configured threshold (default 10), the log
   level is WARNING. Below threshold, it's DEBUG.

Why a ContextVar?
-----------------
FastAPI uses asyncio. Each request runs in its own task; ContextVar is
per-task by default — counts from one request never leak into another.

Wiring
------
Two steps in `backend/main.py`:

  1. Call `install_query_counter(engine)` once at module import, passing the
     SQLAlchemy engine instance.
  2. Add `QueryCountMiddleware` to the FastAPI app:

         app.add_middleware(QueryCountMiddleware, threshold=10)

Both are cheap; the listener adds ~one int increment per query, and the
middleware is a single contextvar reset + read per request.

Disabling
---------
Set the env var `RELOPASS_QUERY_COUNTER_OFF=1` to silence the listener
entirely (e.g. for synthetic load tests where you want zero observation
overhead). The middleware will still attach but report 0 for every request.

Threshold tuning
----------------
The default 10 is conservative — it's an empirically chosen "anything above
this for a single endpoint smells like an N+1." Per-route override via
env vars is intentionally NOT exposed; instead, the WARNING signal should
prompt the engineer to look at the endpoint and either fix the N+1 or add
a comment explaining why the count is intentionally high.
"""
from __future__ import annotations

import contextvars
import logging
import os
import time
from typing import Any

from sqlalchemy import event

log = logging.getLogger(__name__)

# Per-request query counter. The value is a single-element list (a "mutable box")
# so increments persist across the threadpool boundary FastAPI uses for sync
# handlers. ContextVar copies the reference to the box when a child task is
# spawned, and listing-mutations are visible to both parent and child. The
# middleware allocates a *new* box per request via `reset_count()`, so requests
# never share state — only the parent/child task pair of one request does.
_query_count: contextvars.ContextVar[list[int]] = contextvars.ContextVar(
    "relopass_query_count", default=[0]
)

# Flag set once `install_query_counter` has wired the listener — avoids double
# attachment if the engine is created twice (legacy + modular paths).
_LISTENER_INSTALLED = False

# Hard-off via env var. Set to "1" / "true" / "yes" to silence the listener.
def _is_disabled() -> bool:
    val = os.environ.get("RELOPASS_QUERY_COUNTER_OFF", "").strip().lower()
    return val in ("1", "true", "yes")


def install_query_counter(engine: Any) -> None:
    """Attach the SQLAlchemy listener exactly once per engine.

    Idempotent — calling this twice with the same engine (or two different
    engines that point at the same DB) leaves only one listener in place.
    """
    global _LISTENER_INSTALLED
    if _LISTENER_INSTALLED:
        return
    if _is_disabled():
        log.info("query_counter: disabled via RELOPASS_QUERY_COUNTER_OFF")
        _LISTENER_INSTALLED = True
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _increment(conn, cursor, statement, parameters, context, executemany) -> None:
        try:
            _query_count.get()[0] += 1
        except LookupError:
            # ContextVar not yet set for this task — initialise a new box.
            _query_count.set([1])

    _LISTENER_INSTALLED = True
    log.info("query_counter: SQLAlchemy listener attached")


def current_count() -> int:
    """Read the current request's query count. Returns 0 outside a request."""
    try:
        return _query_count.get()[0]
    except LookupError:
        return 0


def reset_count() -> None:
    """Allocate a *new* counter box. Called by the middleware at request start.

    Using a fresh list (not just `[0] = 0`) ensures the next request can't see
    a previous request's box even if the ContextVar happens to be set in an
    unexpected context.
    """
    _query_count.set([0])


class QueryCountMiddleware:
    """ASGI middleware that logs query count per request.

    Implemented as raw ASGI (not BaseHTTPMiddleware) so it runs in the SAME
    task as the handler. BaseHTTPMiddleware wraps the handler in
    `asyncio.create_task`, which copies the parent context — meaning any
    ContextVar increments inside the handler are invisible to the middleware
    when it reads back. Pure ASGI avoids that pitfall.

    - Resets the counter at request start.
    - Logs DEBUG when count <= threshold.
    - Logs WARNING when count > threshold (likely N+1).
    - Only acts on HTTP requests (lifespan / websocket pass straight through).
    """

    def __init__(self, app: Any, threshold: int = 10) -> None:
        self.app = app
        self.threshold = threshold

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        reset_count()
        t0 = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            count = current_count()
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            method = scope.get("method", "?")
            path = scope.get("path", "?")
            status = "OVER" if count > self.threshold else "OK"
            level = logging.WARNING if count > self.threshold else logging.DEBUG
            log.log(
                level,
                "query_count route=%s %s count=%d threshold=%d elapsed_ms=%d status=%s",
                method,
                path,
                count,
                self.threshold,
                elapsed_ms,
                status,
            )
