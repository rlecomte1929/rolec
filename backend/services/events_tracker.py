"""
events_tracker.py — server-side analytics event writer for FOUNDATION-1A schema.

Writes structured events to the `public.events` table in Supabase using the
service-role client (bypasses RLS). This is the Python counterpart of the
frontend's `lib/analytics.ts → capture-event` edge function.

Usage (fire-and-forget; never raises):
    from backend.services.events_tracker import track

    track(
        event_type="assignment.created",
        entity_type="assignment",
        entity_id=assignment_id,
        user_id=hr_user["id"],        # will be SHA-256 hashed before write
        company_id=company_id,
        properties={"case_id": case_id},
        source="api",
    )

All calls are best-effort: failures are logged at WARNING level and swallowed
so they never break the calling endpoint.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ─── Lazy Supabase client ─────────────────────────────────────────────────────

_client_lock = threading.Lock()
_supabase_client: Any = None


def _get_client() -> Any:
    """Lazily initialise the Supabase service-role client."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    with _client_lock:
        if _supabase_client is not None:
            return _supabase_client
        try:
            from .supabase_client import get_supabase_admin_client
            _supabase_client = get_supabase_admin_client()
        except Exception as exc:
            log.debug("events_tracker: Supabase client unavailable (%s); events will be dropped.", exc)
            _supabase_client = None
    return _supabase_client


# ─── Privacy helper ───────────────────────────────────────────────────────────

def _hash_user_id(raw: Optional[str]) -> Optional[str]:
    """SHA-256 hash of a user ID so no raw PII is stored in the events table."""
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ─── Public API ───────────────────────────────────────────────────────────────

def track(
    event_type: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    company_id: Optional[str] = None,
    session_id: Optional[str] = None,
    source: str = "api",
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Fire-and-forget: write one event row to public.events.

    Never raises — all errors are caught and logged at WARNING level.
    Hashes user_id before write so no raw PII is persisted.
    """
    client = _get_client()
    if client is None:
        return  # Supabase not available (e.g. local SQLite dev)

    row: Dict[str, Any] = {
        "event_type":  event_type,
        "entity_type": entity_type,
        "entity_id":   str(entity_id) if entity_id else None,
        "user_id":     _hash_user_id(user_id),
        "company_id":  str(company_id) if company_id else None,
        "session_id":  session_id,
        "source":      source,
        "properties":  properties or {},
    }

    def _write() -> None:
        try:
            client.table("events").insert(row).execute()
        except Exception as exc:
            log.warning("events_tracker: failed to write event=%s error=%s", event_type, exc)

    # Write in a background thread so it never adds latency to the API response
    threading.Thread(target=_write, daemon=True).start()
