"""AIQ-1607: EU address-autocomplete via Geoapify, proxied server-side.

The employee's typed address is PII, so it is geocoded through the ReloPass
backend (the Geoapify key never reaches the client) via Geoapify (EU/Germany,
DPA-backed). **Disabled-until-keyed**: with no ``GEOAPIFY_API_KEY`` set,
``autocomplete()`` returns ``[]`` and the caller degrades to a plain input — no
address leaves the platform until the DPA is signed and the key is configured.
Never raises; never logs the raw query.
"""
import logging
import os
from typing import Any, Dict, List

log = logging.getLogger(__name__)

_GEOAPIFY_AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"


def is_enabled() -> bool:
    """True only when a Geoapify key is configured (i.e. the DPA is in place)."""
    return bool((os.getenv("GEOAPIFY_API_KEY") or "").strip())


def autocomplete(query: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    """Address suggestions for a partial ``query``.

    Returns ``[]`` when disabled (no key), when the query is too short, or on any
    error — fail-soft, never raises, so a geocode problem never breaks intake.
    """
    api_key = (os.getenv("GEOAPIFY_API_KEY") or "").strip()
    query = (query or "").strip()
    if not api_key or len(query) < 3:
        return []
    try:
        import requests  # lazy: keep import cost off the disabled path

        resp = requests.get(
            _GEOAPIFY_AUTOCOMPLETE_URL,
            params={
                "text": query,
                "apiKey": api_key,
                "format": "json",
                "limit": max(1, min(limit, 10)),
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception:  # noqa: BLE001 — a geocode problem must never break intake
        log.warning("geoapify autocomplete failed (suppressed)")
        return []

    out: List[Dict[str, Any]] = []
    for r in (data.get("results", []) or [])[:limit]:
        formatted = (r.get("formatted") or "").strip()
        if formatted:
            out.append({"formatted": formatted})
    return out
