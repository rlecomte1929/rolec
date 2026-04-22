"""
Observability bootstrap — Sentry error tracking + structured JSON logging.

No-op when the env vars are absent (local dev, tests). Both pieces are
designed to be 100% safe to leave always-enabled in the code path — the
library is a thin wrapper that short-circuits when not configured.

Usage: call configure_observability() once at import time from backend.main,
before the FastAPI app is constructed. It's idempotent — repeated calls are
no-ops.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

_CONFIGURED = False


def _sentry_dsn() -> Optional[str]:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    return dsn or None


def _env_name() -> str:
    # Render injects RENDER env vars in prod. Fall back to explicit overrides.
    return (
        os.getenv("SENTRY_ENVIRONMENT")
        or os.getenv("RENDER_SERVICE_NAME")
        or os.getenv("ENV")
        or "development"
    )


def _release_tag() -> Optional[str]:
    # Use the Render git SHA if available; otherwise an explicit
    # SENTRY_RELEASE override; otherwise None (Sentry will infer).
    tag = os.getenv("SENTRY_RELEASE") or os.getenv("RENDER_GIT_COMMIT") or ""
    return tag.strip() or None


def _configure_sentry() -> None:
    dsn = _sentry_dsn()
    if not dsn:
        return
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.starlette import StarletteIntegration  # type: ignore
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore
    except ImportError:
        logging.getLogger(__name__).warning("sentry_sdk not installed; skipping Sentry setup")
        return

    # Do not send PII by default — HR + employee data includes passport /
    # nationality, we should never forward that to a third-party APM.
    # Stack traces, request paths, and headers (minus cookies / auth) are fine.
    sentry_sdk.init(
        dsn=dsn,
        environment=_env_name(),
        release=_release_tag(),
        send_default_pii=False,
        # 0.0 means zero perf sampling — overrideable via SENTRY_TRACES_SAMPLE_RATE.
        # Leave default off because perf monitoring is expensive per event.
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    logging.getLogger(__name__).info(
        "Sentry initialized: env=%s release=%s", _env_name(), _release_tag() or "(none)"
    )


def _configure_structured_logging() -> None:
    # Opt-in: set RELOPASS_JSON_LOGS=1 in prod. Leave as text logs in dev
    # so local tail -f stays readable.
    if os.getenv("RELOPASS_JSON_LOGS", "").lower() not in ("1", "true", "yes"):
        return
    try:
        from pythonjsonlogger import jsonlogger  # type: ignore
    except ImportError:
        logging.getLogger(__name__).warning(
            "python-json-logger not installed; falling back to text logs"
        )
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"levelname": "level", "asctime": "ts", "name": "logger"},
        )
    )
    # Replace any existing handlers on the root logger.
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger(__name__).info("Structured JSON logging enabled")


def configure_observability() -> None:
    """Called once at app startup (imported by backend/main.py)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _configure_structured_logging()
    _configure_sentry()
    _CONFIGURED = True
