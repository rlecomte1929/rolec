"""
PostHog analytics client — instance-based singleton.

Initialize once at startup via init_posthog(), then capture events from any
module using get_posthog_client(). Skips all operations when the token is absent
or POSTHOG_DISABLED=true, so development/test environments that don't configure
PostHog are unaffected.
"""
import atexit
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

_client: Optional[object] = None  # posthog.Posthog instance


def init_posthog() -> None:
    """Create the PostHog client. Call once inside the app lifespan startup."""
    global _client
    token = os.environ.get("POSTHOG_PROJECT_TOKEN", "").strip()
    disabled = os.environ.get("POSTHOG_DISABLED", "").lower() in ("1", "true", "yes")
    if disabled or not token:
        log.info("PostHog disabled or token missing — analytics will not be sent.")
        return
    host = os.environ.get("POSTHOG_HOST", "https://eu.i.posthog.com").strip()
    try:
        from posthog import Posthog
        _client = Posthog(
            project_api_key=token,
            host=host,
            # Exception autocapture is deliberately OFF: it ships server-side stack
            # traces and local variables (which can contain raw PII — SQL params,
            # request bodies, user data in locals) to PostHog, an external
            # sub-processor. That would bypass our data-minimisation controls
            # (GDPR Art. 28/44). Only the explicit, PII-free events captured via
            # ph.capture() below are sent. See docs/security/PRIV-004.
            enable_exception_autocapture=False,
        )
        atexit.register(_client.shutdown)
        log.info("PostHog client initialized (host=%s).", host)
    except Exception as exc:  # pragma: no cover
        log.warning("PostHog client init failed (non-fatal): %s", exc)


def shutdown_posthog() -> None:
    """Flush and shut down the PostHog client. Call inside the app lifespan teardown."""
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass


def get_posthog_client():
    """Return the active Posthog instance, or None if PostHog is not configured."""
    return _client
