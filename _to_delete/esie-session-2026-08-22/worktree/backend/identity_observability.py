"""
Structured identity / assignment lifecycle logs for verification and ops.

Log line format: ``identity_obs {"event":"...","request_id":"...",...}``
Search in aggregators: ``identity_obs`` or event prefix ``identity.``.

Common assignment-linking events: ``identity.assignments.overview`` (linked/pending counts),
``identity.claim.manual`` / ``identity.claim.manual.failed``, ``identity.claim.pending_explicit`` /
``identity.claim.pending_explicit.failed``.

**Privacy:** raw emails are never logged. Use ``principal_fingerprint`` (SHA-256 prefix) for correlation.
IDs (assignment_id, employee_contact_id, company_id, auth_user_id) are logged in full for traceability in secured logs.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from .identity_normalize import normalize_invite_key

_log = logging.getLogger(__name__)


def principal_fingerprint_from_login_identifier(identifier: str) -> Optional[str]:
    """Derive privacy-safe fingerprint from login `identifier` (email or username)."""
    s = (identifier or "").strip()
    if not s:
        return None
    if "@" in s.lower():
        return principal_fingerprint(s, None)
    return principal_fingerprint(None, s)


def principal_fingerprint(email: Optional[str], username: Optional[str]) -> Optional[str]:
    """Stable 16-hex prefix for correlating signup/login/claim without storing raw email."""
    parts: list[str] = []
    if email and str(email).strip():
        parts.append(normalize_invite_key(email))
    if username and str(username).strip():
        parts.append("u:" + normalize_invite_key(username))
    if not parts:
        return None
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def identity_event(event: str, **kwargs: Any) -> None:
    """Emit one JSON object prefixed with ``identity_obs`` for easy grep."""
    payload: Dict[str, Any] = {"event": event}
    for k, v in kwargs.items():
        if v is None:
            continue
        if v == "":
            continue
        payload[k] = v
    try:
        line = json.dumps(payload, default=str, separators=(",", ":"))
    except (TypeError, ValueError):
        payload = {"event": event, "serialization_error": True}
        line = json.dumps(payload, separators=(",", ":"))
    _log.info("identity_obs %s", line)
