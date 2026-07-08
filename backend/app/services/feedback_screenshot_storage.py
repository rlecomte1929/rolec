"""feedback_screenshot_storage.py — [AIQ-1480] store feedback screenshots in the private
`feedback-screenshots` Supabase Storage bucket + mint short-lived signed URLs for the admin.

A screenshot captures the reporter's page and can contain PII, so the bucket is private and
only the service-role backend reads/writes it. base64 in feedback.screenshot_data is the
fallback when a Storage upload fails, so a screenshot is never lost.
"""
from __future__ import annotations

import base64
import binascii
import logging
import re
import uuid
from typing import Optional, Tuple

log = logging.getLogger(__name__)

_BUCKET = "feedback-screenshots"
_SIGNED_URL_TTL = 3600  # 1h — admin views mint a fresh signed URL on each open
_DATA_URI = re.compile(r"^data:image/(png|jpeg|jpg);base64,", re.IGNORECASE)


def _decode(data_url_or_b64: str) -> Optional[Tuple[str, bytes]]:
    """Strip a data-URI prefix and decode → (content_type, bytes); None if not decodable."""
    payload = data_url_or_b64 or ""
    content_type = "image/png"
    m = _DATA_URI.match(payload)
    if m:
        ext = m.group(1).lower()
        content_type = "image/jpeg" if ext in ("jpeg", "jpg") else "image/png"
        payload = _DATA_URI.sub("", payload)
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        return None
    return (content_type, raw) if raw else None


def upload_screenshot(data_url_or_b64: str, *, key_hint: Optional[str] = None) -> Optional[str]:
    """Upload a base64 / data-URL screenshot to the private bucket. Returns the object path on
    success, or None on ANY failure (caller then falls back to base64 in screenshot_data)."""
    decoded = _decode(data_url_or_b64)
    if not decoded:
        return None
    content_type, raw = decoded
    ext = "jpg" if content_type == "image/jpeg" else "png"
    safe_hint = re.sub(r"[^A-Za-z0-9_-]", "", (key_hint or ""))[:40] or uuid.uuid4().hex
    path = f"{safe_hint}-{uuid.uuid4().hex[:8]}.{ext}"
    try:
        from .supabase_client import get_supabase_admin_client
        client = get_supabase_admin_client()
        client.storage.from_(_BUCKET).upload(path, raw, {"content-type": content_type})
        return path
    except Exception as exc:  # noqa: BLE001 — never fail the feedback submit on a storage hiccup
        log.warning("feedback screenshot upload failed (bucket=%s); base64 fallback: %s", _BUCKET, exc)
        return None


def signed_url(path: str, *, ttl: int = _SIGNED_URL_TTL) -> Optional[str]:
    """Mint a short-lived signed URL for a stored screenshot (admin read). None on failure."""
    if not path:
        return None
    try:
        from .supabase_client import get_supabase_admin_client
        client = get_supabase_admin_client()
        res = client.storage.from_(_BUCKET).create_signed_url(path, ttl)
        # supabase-py has used both "signedURL" and "signedUrl" across versions.
        return (res or {}).get("signedURL") or (res or {}).get("signedUrl")
    except Exception as exc:  # noqa: BLE001
        log.warning("feedback screenshot signed-url failed for %s: %s", path, exc)
        return None
