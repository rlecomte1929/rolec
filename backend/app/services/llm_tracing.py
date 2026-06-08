"""
AIQ-571 / AI-W1.1 — Langfuse EU Cloud trace emission for llm_client.

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
    """Lazily build a singleton Langfuse client, or None if unconfigured/unavailable."""
    global _client, _init_done
    if _init_done:
        return _client
    _init_done = True
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        return None  # not configured → tracing off (the common dev/test case)
    try:
        from langfuse import Langfuse  # type: ignore

        _client = Langfuse(
            public_key=pub,
            secret_key=sec,
            host=os.environ.get("LANGFUSE_HOST", _EU_HOST),
        )
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


def _safe_end(gen: Any, *, output: Any = None, level: Optional[str] = None,
              status_message: Optional[str] = None) -> None:
    """End a generation + best-effort flush. Every Langfuse call is guarded so an SDK
    API mismatch or network error degrades to a no-op rather than touching the caller."""
    if gen is None:
        return
    try:
        kwargs: dict = {}
        if output is not None:
            kwargs["output"] = output
        if level is not None:
            kwargs["level"] = level
        if status_message is not None:
            kwargs["status_message"] = status_message
        gen.end(**kwargs)
    except Exception:
        pass
    # Flush so short-lived sync wrappers (asyncio.run in *_sync) ship the event before exit.
    client = _client
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass


def traced_generation(provider: str) -> Callable:
    """Decorator for an async llm_client entry point: emit a Langfuse generation
    (input = system/user prompts, output = response, model, latency). Fail-soft."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = _get_client()
            if client is None:
                return await fn(*args, **kwargs)

            gen = None
            try:
                gen = client.generation(
                    name=f"llm_client.{fn.__name__}",
                    model=kwargs.get("model"),
                    input={
                        "system": _truncate(kwargs.get("system", "")),
                        "user": _truncate(kwargs.get("user", "")),
                    },
                    metadata={"provider": provider, "ts": time.time()},
                )
            except Exception:
                gen = None

            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                _safe_end(gen, level="ERROR", status_message=_truncate(str(exc), 1000))
                raise
            _safe_end(gen, output=_truncate(result))
            return result

        return wrapper

    return decorator
