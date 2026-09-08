"""
AIQ-571 / AI-W1.1 — Langfuse EU Cloud trace emission for llm_client (v4 SDK).

Plug-and-play + FAIL-SOFT. Every LLM call routed through llm_client is recorded
as a Langfuse "generation" — but ONLY when LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY
are set and the ``langfuse`` package is installed. When unconfigured, missing, or
erroring, tracing is a silent no-op: it must NEVER break, slow, or change an LLM call.

Decision record: audit/AI_AGENT_STRATEGY.md §5 (Langfuse EU Cloud).
Host defaults to the EU region (https://cloud.langfuse.com); override via LANGFUSE_HOST
(e.g. https://us.cloud.langfuse.com for the US region).
"""
from __future__ import annotations

import functools
import logging
import os
import time
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_EU_HOST = "https://cloud.langfuse.com"
_client: Optional[Any] = None
_init_done = False


def _get_client() -> Optional[Any]:
    """Return the Langfuse v4 client singleton, or None if unconfigured/unavailable."""
    global _client, _init_done
    if _init_done:
        return _client
    _init_done = True
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        return None  # not configured → tracing off (the common dev/test case)
    try:
        from langfuse import get_client as _langfuse_get_client  # type: ignore
        _client = _langfuse_get_client()
        log.info("langfuse tracing enabled (host=%s)", os.environ.get("LANGFUSE_HOST", _EU_HOST))
    except Exception as exc:  # missing package, bad keys, network — never fatal
        log.warning("langfuse init failed; tracing disabled: %s", exc)
        _client = None
    return _client


def langfuse_enabled() -> bool:
    return _get_client() is not None


def _truncate(value: Any, limit: int = 8000) -> str:
    s = value if isinstance(value, str) else str(value)
    return s if len(s) <= limit else s[:limit] + "…[truncated]"


def traced_generation(provider: str) -> Callable:
    """Decorator for an async llm_client entry point: emit a Langfuse v4 generation span.

    Applies @observe(as_type="generation") at decoration time so the function
    body runs inside an active span context. Input/output/model metadata are
    patched onto the span via update_current_generation(). Fail-soft throughout.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def traced_fn(*args: Any, **kwargs: Any) -> Any:
            client = _get_client()
            if client is not None:
                try:
                    client.update_current_generation(
                        model=kwargs.get("model"),
                        input={
                            "system": _truncate(kwargs.get("system", "")),
                            "user": _truncate(kwargs.get("user", "")),
                        },
                        metadata={"provider": provider, "ts": time.time()},
                    )
                except Exception:
                    pass

            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                if client is not None:
                    try:
                        client.update_current_generation(
                            level="ERROR",
                            status_message=_truncate(str(exc), 1000),
                        )
                        client.flush()
                    except Exception:
                        pass
                raise

            if client is not None:
                try:
                    client.update_current_generation(output=_truncate(result))
                    client.flush()
                except Exception:
                    pass
            return result

        # Wrap traced_fn with @observe so it creates a generation span context;
        # fall back silently if the langfuse package is not installed or wrong version.
        try:
            from langfuse import observe as _observe  # type: ignore
            return _observe(as_type="generation", name=f"llm_client.{fn.__name__}")(traced_fn)
        except Exception:
            return traced_fn

    return decorator
