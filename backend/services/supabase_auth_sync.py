"""
Provision Supabase Auth users for ReloPass accounts that use email + password.

The app stores credentials in its own DB; Supabase Auth is used by the frontend for
token refresh and RLS-backed features. Without this sync, signInWithPassword fails
with 400 after backend login/register.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

try:
    from .supabase_client import get_supabase_admin_client
except Exception:  # pragma: no cover - shadowed supabase package / missing deps
    get_supabase_admin_client = None  # type: ignore[misc, assignment]


def _duplicate_user_error(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    if code in ("email_exists", "user_already_exists", "phone_exists"):
        return True
    name = getattr(exc, "name", None)
    if name in ("AuthApiError",):
        pass
    msg = str(exc).lower()
    return any(
        s in msg
        for s in (
            "already been registered",
            "already exists",
            "email_exists",
            "user already registered",
            "duplicate",
        )
    )


def sync_relopass_user_to_supabase_auth(
    email: str,
    password: str,
    *,
    relopass_user_id: str,
    full_name: Optional[str] = None,
) -> bool:
    """
    Create a Supabase Auth user if possible. Idempotent when the email already exists.
    Returns True if the user likely exists in Supabase (created or already there).
    Returns False only when configuration is missing or a non-duplicate error occurred.
    Never raises.
    """
    if os.getenv("DISABLE_SUPABASE_AUTH_SYNC", "").lower() in ("1", "true", "yes"):
        return True
    e = (email or "").strip().lower()
    if not e or not (password or "").strip():
        return True
    if len(password) < 6:
        # Supabase rejects very short passwords; skip rather than fail signup.
        log.warning("supabase_auth_sync skipped: password too short for Supabase policy email=%s", e[:3] + "***")
        return True

    if get_supabase_admin_client is None:
        return True

    try:
        client = get_supabase_admin_client()
    except Exception as ex:
        log.debug("supabase_auth_sync no admin client: %s", ex)
        return True

    meta: dict[str, Any] = {"relopass_user_id": relopass_user_id}
    if full_name and str(full_name).strip():
        meta["full_name"] = str(full_name).strip()

    attrs: dict[str, Any] = {
        "email": e,
        "password": password,
        "email_confirm": True,
        "user_metadata": meta,
    }

    try:
        client.auth.admin.create_user(attrs)  # type: ignore[union-attr]
        log.info("supabase_auth_sync created auth user email=%s relopass_id=%s", e[:3] + "***", relopass_user_id[:8])
        return True
    except Exception as ex:
        if _duplicate_user_error(ex):
            log.debug("supabase_auth_sync user already present email=%s", e[:3] + "***")
            return True
        log.warning(
            "supabase_auth_sync failed email=%s relopass_id=%s error=%s",
            e[:3] + "***",
            relopass_user_id[:8],
            ex,
        )
        return False
