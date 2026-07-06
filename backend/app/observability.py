"""
Langfuse v4 startup initialisation.

Call init_langfuse() once at app startup (backend/main.py) to pre-warm the
singleton client and emit a startup log line. No-op when LANGFUSE_* env vars
are absent — safe to leave always-enabled in production.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

_EU_HOST = "https://cloud.langfuse.com"


def init_langfuse() -> None:
    """Pre-warm the Langfuse v4 client singleton. Never raises."""
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        log.debug("langfuse: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set; tracing disabled")
        return
    try:
        from langfuse import get_client  # type: ignore
        get_client()
        log.info(
            "langfuse v4 client initialised (host=%s)",
            os.environ.get("LANGFUSE_HOST", _EU_HOST),
        )
    except Exception as exc:
        log.warning("langfuse startup init failed (tracing disabled): %s", exc)


def get_langfuse_client() -> Optional[Any]:
    """Return the active Langfuse client, or None if not configured."""
    try:
        from langfuse import get_client  # type: ignore
        return get_client()
    except Exception:
        return None
