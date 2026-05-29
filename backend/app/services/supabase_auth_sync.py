"""
Provision Supabase Auth users for ReloPass accounts that use email + password.

The app stores credentials in its own DB; Supabase Auth is used by the frontend for
token refresh and RLS-backed features. Without this sync, signInWithPassword fails
with 400 after backend login/register.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import secrets
from typing import Any, Optional

log = logging.getLogger(__name__)

try:
    from .supabase_client import get_supabase_admin_client
except Exception:  # pragma: no cover - shadowed supabase package / missing deps
    get_supabase_admin_client = None  # type: ignore[misc, assignment]


# Per-call wallclock cap for Supabase admin API requests. supabase-py 2.5 does
# not expose a portable socket timeout for the gotrue admin client, so the call
# is dispatched to a worker thread and abandoned (logged) if it overruns. This
# stops a wedged Supabase from holding any caller past the configured budget.
_SUPABASE_CALL_TIMEOUT_S = float(os.getenv("SUPABASE_AUTH_SYNC_TIMEOUT_SECONDS", "5"))
_call_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("SUPABASE_AUTH_SYNC_MAX_WORKERS", "8")),
    thread_name_prefix="supabase-call",
)


def _call_with_timeout(fn, *args, **kwargs):
    """Run a blocking Supabase admin call with a hard wallclock timeout.

    Raises concurrent.futures.TimeoutError if the call exceeds the budget;
    the worker thread is intentionally left running so a deadlocked socket
    does not stall caller threads.
    """
    fut = _call_executor.submit(fn, *args, **kwargs)
    return fut.result(timeout=_SUPABASE_CALL_TIMEOUT_S)


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


def _rate_limited_error(exc: BaseException) -> bool:
    """True when Supabase rejected an email-sending call for rate-limit reasons.

    Bulk HR onboarding (B7) trips Supabase's built-in SMTP cap after ~12 invite
    emails. admin.create_user (no email) is exempt, so callers fall back to it.
    """
    code = getattr(exc, "code", None)
    if code in ("over_email_send_rate_limit", "over_request_rate_limit"):
        return True
    msg = str(exc).lower()
    return "rate limit" in msg or "rate_limit" in msg


def _temp_password() -> str:
    """A strong random password for fallback-created accounts.

    The account is created already-confirmed; the user sets their own password
    later via the password-reset flow, so this value is never surfaced.
    """
    return secrets.token_urlsafe(24) + "9Az"


def provision_admin_created_user(
    email: str,
    *,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    redirect_to: Optional[str] = None,
) -> dict[str, Any]:
    """B7 fix: provision an HR-created account with a rate-limit-safe fallback.

    Hybrid strategy so bulk onboarding never stalls on Supabase's email cap:
      1. Try invite_user_by_email (preserves the B2 self-set-password UX).
      2. On over_email_send_rate_limit, fall back to admin.create_user
         (email_confirm=True, random password) — no email, no rate limit. The
         account is immediately usable; the user sets a password via reset.
      3. Duplicates are treated as success (account already exists).

    Returns ``{"status": ..., "invite_sent": bool}`` where status is one of
    ``invited`` | ``created_pending_invite`` | ``exists`` | ``error`` | ``noop``.
    Never raises.
    """
    if os.getenv("DISABLE_SUPABASE_AUTH_SYNC", "").lower() in ("1", "true", "yes"):
        return {"status": "noop", "invite_sent": False}
    e = (email or "").strip().lower()
    if not e:
        return {"status": "noop", "invite_sent": False}
    if get_supabase_admin_client is None:
        return {"status": "noop", "invite_sent": False}

    try:
        client = get_supabase_admin_client()
    except Exception as ex:
        log.debug("provision_admin_created_user: no admin client: %s", ex)
        return {"status": "noop", "invite_sent": False}

    admin = getattr(getattr(client, "auth", None), "admin", None)
    if admin is None:
        log.warning("provision_admin_created_user: no admin interface on supabase client")
        return {"status": "error", "invite_sent": False}

    meta: dict[str, Any] = {}
    if full_name and str(full_name).strip():
        meta["full_name"] = str(full_name).strip()
    if role:
        meta["role"] = role

    # 1. Preferred path: invite email (user picks their own password).
    invite_fn = getattr(admin, "invite_user_by_email", None)
    if invite_fn is not None:
        options: dict[str, Any] = {}
        if meta:
            options["data"] = meta
        if redirect_to:
            options["redirect_to"] = redirect_to
        try:
            _call_with_timeout(invite_fn, e, options)
            log.info("provision_admin_created_user: invite sent email=%s", e[:3] + "***")
            return {"status": "invited", "invite_sent": True}
        except concurrent.futures.TimeoutError:
            log.warning("provision_admin_created_user: invite timed_out email=%s", e[:3] + "***")
            return {"status": "error", "invite_sent": False}
        except Exception as ex:
            if _duplicate_user_error(ex):
                log.debug("provision_admin_created_user: already present email=%s", e[:3] + "***")
                return {"status": "exists", "invite_sent": False}
            if not _rate_limited_error(ex):
                log.warning("provision_admin_created_user: invite failed email=%s error=%s", e[:3] + "***", ex)
                return {"status": "error", "invite_sent": False}
            log.info(
                "provision_admin_created_user: invite rate-limited, falling back to admin.create_user email=%s",
                e[:3] + "***",
            )

    # 2. Fallback (rate-limited or no invite API): create a confirmed account
    #    with no email. The user sets a password via the reset flow later.
    attrs: dict[str, Any] = {
        "email": e,
        "password": _temp_password(),
        "email_confirm": True,
    }
    if meta:
        attrs["user_metadata"] = meta
    try:
        _call_with_timeout(client.auth.admin.create_user, attrs)  # type: ignore[union-attr]
        log.info("provision_admin_created_user: created via fallback (no email) email=%s", e[:3] + "***")
        return {"status": "created_pending_invite", "invite_sent": False}
    except concurrent.futures.TimeoutError:
        log.warning("provision_admin_created_user: fallback timed_out email=%s", e[:3] + "***")
        return {"status": "error", "invite_sent": False}
    except Exception as ex:
        if _duplicate_user_error(ex):
            log.debug("provision_admin_created_user: fallback found existing user email=%s", e[:3] + "***")
            return {"status": "exists", "invite_sent": False}
        log.warning("provision_admin_created_user: fallback failed email=%s error=%s", e[:3] + "***", ex)
        return {"status": "error", "invite_sent": False}


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
        _call_with_timeout(client.auth.admin.create_user, attrs)  # type: ignore[union-attr]
        log.info("supabase_auth_sync created auth user email=%s relopass_id=%s", e[:3] + "***", relopass_user_id[:8])
        return True
    except concurrent.futures.TimeoutError:
        log.warning(
            "supabase_auth_sync timed_out email=%s relopass_id=%s timeout_s=%s",
            e[:3] + "***",
            relopass_user_id[:8],
            _SUPABASE_CALL_TIMEOUT_S,
        )
        return False
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


def invite_admin_created_user(
    email: str,
    *,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    redirect_to: Optional[str] = None,
) -> bool:
    """B2 fix: send a Supabase Auth invite email for an admin-created account.

    Uses admin.invite_user_by_email which (a) creates the auth user if they
    don't exist yet and (b) sends them a "Set your password" email via
    Supabase's configured SMTP. Previously POST /api/admin/people only wrote
    the local profile row — users received a silent account they could not log
    into.

    Returns True on success, or when Supabase is not configured (no-op).
    Never raises — non-fatal if email delivery fails.
    """
    if os.getenv("DISABLE_SUPABASE_AUTH_SYNC", "").lower() in ("1", "true", "yes"):
        return True
    e = (email or "").strip().lower()
    if not e:
        return True
    if get_supabase_admin_client is None:
        return True

    try:
        client = get_supabase_admin_client()
    except Exception as ex:
        log.debug("invite_admin_created_user: no admin client: %s", ex)
        return True

    meta: dict[str, Any] = {}
    if full_name and str(full_name).strip():
        meta["full_name"] = str(full_name).strip()
    if role:
        meta["role"] = role

    options: dict[str, Any] = {}
    if meta:
        options["data"] = meta
    if redirect_to:
        options["redirect_to"] = redirect_to

    try:
        admin = getattr(getattr(client, "auth", None), "admin", None)
        if admin is None:
            log.warning("invite_admin_created_user: no admin interface on supabase client")
            return False
        fn = getattr(admin, "invite_user_by_email", None)
        if fn is None:
            log.warning("invite_admin_created_user: invite_user_by_email not available")
            return False
        _call_with_timeout(fn, e, options)
        log.info("invite_admin_created_user: invite sent email=%s", e[:3] + "***")
        return True
    except concurrent.futures.TimeoutError:
        log.warning(
            "invite_admin_created_user: timed_out email=%s timeout_s=%s",
            e[:3] + "***",
            _SUPABASE_CALL_TIMEOUT_S,
        )
        return False
    except Exception as ex:
        if _duplicate_user_error(ex):
            # User already invited / account already exists — treat as success.
            log.debug("invite_admin_created_user: user already present email=%s", e[:3] + "***")
            return True
        log.warning(
            "invite_admin_created_user: failed email=%s error=%s",
            e[:3] + "***",
            ex,
        )
        return False


def create_auth_user_with_id(
    user_id: str,
    email: str,
    password: str,
    *,
    full_name: Optional[str] = None,
) -> bool:
    """
    Create a Supabase Auth user with a *specific* UUID — used by seed_test_personas
    so that profiles.id FK (→ auth.users.id) is satisfied for fixed test UUIDs.
    Idempotent: silently succeeds if the user already exists.
    Never raises.
    """
    if os.getenv("DISABLE_SUPABASE_AUTH_SYNC", "").lower() in ("1", "true", "yes"):
        return True
    if not user_id or not email or not password:
        return False
    if get_supabase_admin_client is None:
        return False
    try:
        client = get_supabase_admin_client()
    except Exception as ex:
        log.debug("create_auth_user_with_id: no admin client: %s", ex)
        return False

    attrs: dict[str, Any] = {
        "id": user_id,
        "email": email.strip().lower(),
        "password": password,
        "email_confirm": True,
    }
    if full_name and str(full_name).strip():
        attrs["user_metadata"] = {"full_name": str(full_name).strip()}

    try:
        _call_with_timeout(client.auth.admin.create_user, attrs)  # type: ignore[union-attr]
        log.info("create_auth_user_with_id: created user_id=%s email=%s", user_id[:8], email[:3] + "***")
        return True
    except concurrent.futures.TimeoutError:
        log.warning("create_auth_user_with_id: timed_out user_id=%s", user_id[:8])
        return False
    except Exception as ex:
        if _duplicate_user_error(ex):
            log.debug("create_auth_user_with_id: already present user_id=%s", user_id[:8])
            return True
        log.warning("create_auth_user_with_id: failed user_id=%s error=%s", user_id[:8], ex)
        return False


def create_auth_user_and_get_id(
    email: str,
    *,
    full_name: Optional[str] = None,
) -> Optional[str]:
    """
    Create a Supabase Auth user (confirmed, no password) and return the UUID
    assigned by Supabase. Used by admin create_person so the profiles.id FK
    (→ auth.users.id) is satisfied before the local profile row is inserted.

    Returns the UUID string on success, or None when Supabase is not
    configured or on failure.  Never raises.
    """
    if os.getenv("DISABLE_SUPABASE_AUTH_SYNC", "").lower() in ("1", "true", "yes"):
        return None
    e = (email or "").strip().lower()
    if not e:
        return None
    if get_supabase_admin_client is None:
        return None
    try:
        client = get_supabase_admin_client()
    except Exception as ex:
        log.debug("create_auth_user_and_get_id: no admin client: %s", ex)
        return None

    attrs: dict[str, Any] = {
        "email": e,
        "email_confirm": False,  # invite flow sets the password later
    }
    if full_name and str(full_name).strip():
        attrs["user_metadata"] = {"full_name": str(full_name).strip()}

    try:
        resp = _call_with_timeout(client.auth.admin.create_user, attrs)  # type: ignore[union-attr]
        user = getattr(resp, "user", resp)
        uid = str(getattr(user, "id", None)) if user else None
        if uid and uid != "None":
            log.info("create_auth_user_and_get_id: created uid=%s email=%s", uid[:8], e[:3] + "***")
            return uid
        log.warning("create_auth_user_and_get_id: no id in response for email=%s", e[:3] + "***")
        return None
    except concurrent.futures.TimeoutError:
        log.warning("create_auth_user_and_get_id: timed_out email=%s", e[:3] + "***")
        return None
    except Exception as ex:
        if _duplicate_user_error(ex):
            # User already exists — try to fetch their UUID
            log.debug("create_auth_user_and_get_id: user already present, attempting lookup email=%s", e[:3] + "***")
            try:
                users_resp = _call_with_timeout(
                    client.auth.admin.list_users,  # type: ignore[union-attr]
                )
                users = getattr(users_resp, "users", users_resp) or []
                for u in users:
                    if (getattr(u, "email", "") or "").lower() == e:
                        uid = str(getattr(u, "id", None))
                        if uid and uid != "None":
                            return uid
            except Exception as le:
                log.debug("create_auth_user_and_get_id: lookup failed: %s", le)
            return None
        log.warning("create_auth_user_and_get_id: failed email=%s error=%s", e[:3] + "***", ex)
        return None


def revoke_supabase_session(access_token: str) -> bool:
    """
    Best-effort server-side Supabase sign-out. Called on logout so the
    Supabase JWT is invalidated alongside the legacy ReloPass session token
    — previously logout only killed the legacy side and the Supabase JWT
    stayed valid for its TTL (up to 1 hour).

    Never raises. Returns True on success, False on any failure
    (missing config, no SDK, admin API rejected the token, etc.).
    """
    if not access_token or not access_token.strip():
        return False
    if os.getenv("DISABLE_SUPABASE_AUTH_SYNC", "").lower() in ("1", "true", "yes"):
        return False
    if get_supabase_admin_client is None:
        return False
    try:
        client = get_supabase_admin_client()
    except Exception as ex:
        log.debug("revoke_supabase_session: no admin client: %s", ex)
        return False

    # supabase-py exposes sign_out on the admin auth surface. The method name
    # has varied across versions; try the documented one first and fall back
    # to the legacy path. Both receive a JWT and revoke the backing session.
    admin = getattr(getattr(client, "auth", None), "admin", None)
    if admin is None:
        return False
    for method_name in ("sign_out", "signOut"):
        fn = getattr(admin, method_name, None)
        if callable(fn):
            try:
                _call_with_timeout(fn, access_token)
                log.info("revoke_supabase_session ok via admin.%s", method_name)
                return True
            except concurrent.futures.TimeoutError:
                log.warning(
                    "revoke_supabase_session timed_out via admin.%s timeout_s=%s",
                    method_name,
                    _SUPABASE_CALL_TIMEOUT_S,
                )
                return False
            except Exception as ex:
                log.warning("revoke_supabase_session via admin.%s failed: %s", method_name, ex)
                return False
    log.debug("revoke_supabase_session: no sign_out method found on supabase admin client")
    return False
