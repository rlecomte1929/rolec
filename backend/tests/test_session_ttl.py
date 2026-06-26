"""SEC-FE-1 (AIQ-1168): ReloPass session tokens must expire.

Tokens live in localStorage (JS-readable), so a bounded absolute TTL caps the
window a stolen token is usable. Expiry is derived from the session's created_at
(created_at + SESSION_TTL_DAYS) and checked by `_session_is_expired`, which the
token-validation path (`get_user_by_token` / `get_user_context_by_token`) calls.
"""
from datetime import datetime, timedelta

from backend.db.auth import _session_is_expired, SESSION_TTL_DAYS


def test_fresh_session_is_not_expired():
    assert _session_is_expired(datetime.utcnow().isoformat()) is False


def test_session_just_within_ttl_is_not_expired():
    recent = (datetime.utcnow() - timedelta(days=SESSION_TTL_DAYS - 1)).isoformat()
    assert _session_is_expired(recent) is False


def test_session_past_ttl_is_expired():
    old = (datetime.utcnow() - timedelta(days=SESSION_TTL_DAYS + 1)).isoformat()
    assert _session_is_expired(old) is True


def test_missing_or_garbage_created_at_is_fail_closed():
    # No usable timestamp → treat as expired (never leave a session valid by accident).
    assert _session_is_expired(None) is True
    assert _session_is_expired("") is True
    assert _session_is_expired("not-a-date") is True


def test_iso_with_z_suffix_is_parsed():
    assert _session_is_expired(datetime.utcnow().isoformat() + "Z") is False


def test_ttl_is_bounded_not_immortal():
    # Regression guard for the original finding: sessions are no longer immortal.
    assert 0 < SESSION_TTL_DAYS <= 30
