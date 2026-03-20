"""Normalized keys for matching HR-entered identifiers to employee contacts (no auth)."""
from __future__ import annotations


def normalize_invite_key(identifier: str | None) -> str:
    """Lowercase trimmed string used for invite/claim matching (email or username)."""
    if not identifier:
        return ""
    return str(identifier).strip().lower()


def email_normalized_from_identifier(identifier: str | None) -> str | None:
    """If identifier looks like an email, return normalize_invite_key; else None."""
    s = normalize_invite_key(identifier)
    if "@" in s:
        return s
    return None
