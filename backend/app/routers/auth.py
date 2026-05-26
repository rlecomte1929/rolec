"""
Authentication endpoints — /api/auth/register, /api/auth/login, /api/auth/logout.

Extracted from backend/main.py as the first slice of the main.py decomposition
tracked in docs/INDEX.md. Follow this file's shape when moving other domains
out of main.py:
  - imports come from backend.database / backend.schemas / backend.identity_* /
    backend.rate_limit / backend.services (NOT from backend.main)
  - shared auth helpers live in backend/app/auth_deps.py
  - the router is included by backend/main.py via app.include_router

NOTE: no `from __future__ import annotations` — FastAPI/Pydantic v2 forward-ref
resolution breaks on PEP 563 string-annotated body params unless every name is
in the router module's __globals__ at registration time.
"""

import concurrent.futures
import json as _json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Request
from passlib.context import CryptContext

from ...database import db
from ...identity_errors import IdentityErrorCode, err_detail
from ...identity_observability import (
    identity_event,
    principal_fingerprint,
    principal_fingerprint_from_login_identifier,
)
from ...rate_limit import limiter
from ...schemas import (
    LoginRequest,
    LoginResponse,
    PostSignupReconciliation,
    RegisterRequest,
    UserResponse,
    UserRole,
)
from ..services.assignment_claim_link_service import reconcile_pending_assignment_claims
from ..services.audit_log_service import (
    insert_audit_log,
    ACTION_INSERT,
    ACTION_DELETE,
    ACTOR_HUMAN,
)
from ..auth_deps import _is_admin_user

log = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Module-level CryptContext: building this is non-trivial (passlib inspects backends
# and compiles schemes on first construction). Previously rebuilt per request inside
# register/login — now reused across requests.
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

AUTH_PERF_DEBUG = os.getenv("AUTH_PERF_DEBUG", "").lower() in ("1", "true", "yes")

# Login must not block on the EMPLOYEE post-signin reconcile path. A slow or
# wedged query in reconcile previously held the request open until Cloudflare's
# 100s edge timeout. Cap reconcile to a strict budget; if it overruns, the
# login response still goes out and reconcile completes (or is abandoned) in
# the background thread.
_RECONCILE_TIMEOUT_SECONDS = float(os.getenv("AUTH_RECONCILE_TIMEOUT_SECONDS", "5"))
_reconcile_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("AUTH_RECONCILE_MAX_WORKERS", "4")),
    thread_name_prefix="auth-reconcile",
)

# Supabase Auth provisioning runs out-of-band: a slow or unreachable Supabase
# Auth admin API must never block the response on /api/auth/login or
# /api/auth/register. The sync is idempotent and best-effort — if it fails or
# is dropped, the next login retries it. The pool is intentionally small so a
# wedged Supabase cannot consume unbounded threads.
_supabase_sync_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("AUTH_SUPABASE_SYNC_MAX_WORKERS", "4")),
    thread_name_prefix="auth-supabase-sync",
)


def _audit_auth(
    *,
    entity_type: str,
    entity_id: str,
    action_type: str,
    actor_id: Optional[str] = None,
) -> None:
    """Write one audit_logs row; never raises."""
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action_type,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        log.exception(
            "audit: failed to log %s %s entity_id=%s",
            action_type, entity_type, entity_id,
        )


def _dispatch_supabase_sync(
    email: str,
    password: str,
    *,
    relopass_user_id: str,
    full_name: Optional[str],
) -> None:
    """Fire-and-forget Supabase auth-user provisioning.

    Replaces the previous in-request blocking call that could hold the login
    response past Cloudflare's 100s edge timeout and the frontend's 45s axios
    cap, surfacing as "Request timed out" to users.
    """
    from ..services.supabase_auth_sync import sync_relopass_user_to_supabase_auth

    try:
        future = _supabase_sync_executor.submit(
            sync_relopass_user_to_supabase_auth,
            email,
            password,
            relopass_user_id=relopass_user_id,
            full_name=full_name,
        )
    except RuntimeError as ex:
        log.warning("supabase_auth_sync dispatch failed user_id=%s error=%s", relopass_user_id[:8], ex)
        return

    def _log_outcome(fut: "concurrent.futures.Future[bool]") -> None:
        try:
            ok = fut.result()
            if not ok:
                log.warning(
                    "supabase_auth_sync background user_id=%s outcome=failed",
                    relopass_user_id[:8],
                )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning(
                "supabase_auth_sync background user_id=%s exception=%s",
                relopass_user_id[:8],
                exc,
            )

    future.add_done_callback(_log_outcome)


def _log_auth_perf(
    endpoint: str,
    request_id: Optional[str],
    user_id: Optional[str],
    total_duration_ms: float,
    status_code: int,
) -> None:
    """Structured JSON log for auth perf (when AUTH_PERF_DEBUG=1)."""
    if not AUTH_PERF_DEBUG:
        return
    log.info(
        "[auth-perf] %s",
        _json.dumps({
            "endpoint": endpoint,
            "request_id": request_id or "",
            "user_id": (user_id or "")[:8] if user_id else "",
            "total_duration_ms": round(total_duration_ms, 2),
            "status_code": status_code,
        }),
    )


@router.post("/api/auth/register", response_model=LoginResponse)
@limiter.limit("5/hour;20/day")
def register(body: RegisterRequest, request: Request):
    """Register a new user with username or email and role."""
    try:
        username = body.username.strip() if body.username else None
        email_raw = body.email.strip() if body.email else None
        email = email_raw.lower() if email_raw else None

        if not username and not email:
            raise HTTPException(
                status_code=400,
                detail=err_detail(IdentityErrorCode.AUTH_IDENTIFIER_REQUIRED, "Provide a username or email"),
            )

        if username:
            if not re.match(r"^[A-Za-z0-9_]{3,30}$", username):
                identity_event("identity.auth.signup.failed", reason="AUTH_USERNAME_INVALID_FORMAT")
                raise HTTPException(status_code=400, detail="Username must be 3-30 chars, alphanumeric or underscore")
            if db.get_user_by_username(username):
                identity_event(
                    "identity.auth.signup.failed",
                    reason="AUTH_USERNAME_TAKEN",
                    principal_fingerprint=principal_fingerprint(None, username),
                )
                raise HTTPException(
                    status_code=400,
                    detail=err_detail(
                        IdentityErrorCode.AUTH_USERNAME_TAKEN,
                        "This username is already taken. Choose another or sign in.",
                    ),
                )

        if email:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                identity_event("identity.auth.signup.failed", reason="AUTH_EMAIL_INVALID_FORMAT")
                raise HTTPException(status_code=400, detail="Invalid email format")
            if db.get_user_by_email(email):
                identity_event(
                    "identity.auth.signup.failed",
                    reason="AUTH_EMAIL_TAKEN",
                    principal_fingerprint=principal_fingerprint(email, None),
                )
                raise HTTPException(
                    status_code=400,
                    detail=err_detail(
                        IdentityErrorCode.AUTH_EMAIL_TAKEN,
                        "An account with this email already exists. Try logging in instead.",
                    ),
                )

        if not body.password:
            raise HTTPException(status_code=400, detail="Password required")

        password_hash = _pwd_context.hash(body.password)

        role = body.role
        if role == UserRole.ADMIN and (not email or not email.endswith("@relopass.com") or not db.is_admin_allowlisted(email)):
            role = UserRole.EMPLOYEE

        user_id = str(uuid.uuid4())
        created = db.create_user(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            role=role.value,
            name=body.name,
        )
        if not created:
            identity_event(
                "identity.auth.signup.failed",
                reason="AUTH_USER_CREATE_FAILED",
                principal_fingerprint=principal_fingerprint(email, username),
            )
            raise HTTPException(
                status_code=400,
                detail=err_detail(
                    IdentityErrorCode.AUTH_USER_CREATE_FAILED,
                    "Could not create this account. The email or username may already be registered.",
                ),
            )

        token = str(uuid.uuid4())
        db.create_session(token, user_id)
        db.ensure_profile_record(
            user_id=user_id,
            email=email,
            role=role.value,
            full_name=body.name,
            company_id=None,
        )

        reconciliation_payload = None
        if role == UserRole.EMPLOYEE and (email or username):
            try:
                claim_res = reconcile_pending_assignment_claims(
                    db,
                    user_id=user_id,
                    email=email,
                    username=username,
                    role=role.value,
                    request_id=None,
                    emit_side_effects=True,
                )
                identity_event(
                    "identity.auth.signup.reconcile",
                    auth_user_id=user_id,
                    principal_fingerprint=principal_fingerprint(email, username),
                    linked_contacts=len(claim_res.linked_contact_ids),
                    new_attachments=len(claim_res.newly_attached_assignment_ids),
                    skipped_revoked_invites=claim_res.skipped_revoked_invites,
                    skipped_contacts_linked_to_other_user=claim_res.skipped_contacts_linked_to_other_user,
                    skipped_assignments_linked_to_other_user=claim_res.skipped_assignments_linked_to_other_user,
                    skipped_already_linked_same_user=claim_res.skipped_already_linked_same_user,
                )
                rec = claim_res.to_api_dict()
                if rec.get("linkedContactIds") or rec.get("attachedAssignmentIds") or rec.get("message"):
                    reconciliation_payload = PostSignupReconciliation(
                        linkedContactIds=rec.get("linkedContactIds") or [],
                        attachedAssignmentIds=rec.get("attachedAssignmentIds") or [],
                        skippedContactsLinkedToOtherUser=int(rec.get("skippedContactsLinkedToOtherUser") or 0),
                        skippedAssignmentsLinkedToOtherUser=int(
                            rec.get("skippedAssignmentsLinkedToOtherUser") or 0
                        ),
                        skippedRevokedInvites=int(rec.get("skippedRevokedInvites") or 0),
                        skippedAlreadyLinkedSameUser=int(rec.get("skippedAlreadyLinkedSameUser") or 0),
                        headline=rec.get("headline"),
                        message=rec.get("message"),
                    )
            except Exception as rec_exc:
                log.warning("signup_reconciliation skipped user_id=%s error=%s", user_id[:8], rec_exc)
                identity_event(
                    "identity.auth.signup.reconcile",
                    auth_user_id=user_id,
                    outcome="error",
                    error_type=type(rec_exc).__name__,
                )

        identity_event(
            "identity.auth.signup.ok",
            auth_user_id=user_id,
            role=role.value,
            principal_fingerprint=principal_fingerprint(email, username),
        )
        log.info("auth_register success user_id=%s username=%s", user_id[:8], username)
        _audit_auth(entity_type="user", entity_id=user_id, action_type=ACTION_INSERT, actor_id=user_id)
        if email:
            _dispatch_supabase_sync(
                email,
                body.password,
                relopass_user_id=user_id,
                full_name=body.name,
            )
        return LoginResponse(
            token=token,
            user=UserResponse(
                id=user_id,
                username=username,
                email=email,
                role=role,
                name=body.name,
                company=None,
            ),
            reconciliation=reconciliation_payload,
        )
    except HTTPException:
        raise
    except Exception:
        # NEVER include str(e) in the response — psycopg2 errors carry the full
        # SQL + parameters and have leaked to end users (e.g. profiles_role_check
        # violations exposing DB internals on the registration page).
        # The exception is already captured server-side by log.exception below.
        log.exception("auth_register unexpected error email=%s", getattr(body, "email", ""))
        raise HTTPException(
            status_code=500,
            detail="Registration failed. Please try again or contact support.",
        )


@router.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute;100/hour")
def login(body: LoginRequest, request: Request):
    """Login with username or email + password."""
    t0 = time.perf_counter()
    request_id = getattr(request.state, "request_id", None) or ""
    identifier = (body.identifier or "").strip()
    if not identifier:
        log.warning("auth_login fail identifier_empty")
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_IDENTIFIER_REQUIRED",
            request_id=request_id or None,
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(IdentityErrorCode.AUTH_IDENTIFIER_REQUIRED, "Enter your username or email"),
        )
    user = db.get_user_by_identifier(identifier)
    if not user:
        log.warning("auth_login fail user_not_found identifier=%s", identifier[:3] + "***")
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_USER_NOT_FOUND",
            request_id=request_id or None,
            principal_fingerprint=principal_fingerprint_from_login_identifier(identifier),
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(
                IdentityErrorCode.AUTH_USER_NOT_FOUND,
                "Invalid username or email. Check spelling or create an account.",
            ),
        )

    if not user.get("password_hash"):
        log.warning("auth_login fail no_password user_id=%s", user.get("id", "")[:8])
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_NO_PASSWORD",
            request_id=request_id or None,
            auth_user_id=user.get("id"),
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(IdentityErrorCode.AUTH_NO_PASSWORD, "Invalid credentials"),
        )

    if not _pwd_context.verify(body.password, user["password_hash"]):
        log.warning("auth_login fail wrong_password user_id=%s", user.get("id", "")[:8])
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_WRONG_PASSWORD",
            request_id=request_id or None,
            auth_user_id=user.get("id"),
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(IdentityErrorCode.AUTH_WRONG_PASSWORD, "Incorrect password. Try again or reset."),
        )

    token = str(uuid.uuid4())
    db.create_session(token, user["id"])

    db.ensure_profile_record(
        user_id=user["id"],
        email=user.get("email"),
        role=user.get("role", UserRole.EMPLOYEE.value),
        full_name=user.get("name"),
        company_id=user.get("company"),
    )
    profile = db.get_profile_record(user["id"])

    effective_role = UserRole(user["role"])
    if _is_admin_user(user):
        effective_role = UserRole.ADMIN

    reconciliation_payload = None
    if effective_role == UserRole.EMPLOYEE:
        future = _reconcile_executor.submit(
            reconcile_pending_assignment_claims,
            db,
            user_id=user["id"],
            email=user.get("email"),
            username=user.get("username"),
            role=user.get("role") or UserRole.EMPLOYEE.value,
            request_id=request_id or None,
            emit_side_effects=True,
        )
        try:
            claim_res = future.result(timeout=_RECONCILE_TIMEOUT_SECONDS)
            identity_event(
                "identity.auth.signin.reconcile",
                request_id=request_id or None,
                auth_user_id=user["id"],
                principal_fingerprint=principal_fingerprint(user.get("email"), user.get("username")),
                linked_contacts=len(claim_res.linked_contact_ids),
                new_attachments=len(claim_res.newly_attached_assignment_ids),
                skipped_revoked_invites=claim_res.skipped_revoked_invites,
                skipped_contacts_linked_to_other_user=claim_res.skipped_contacts_linked_to_other_user,
                skipped_assignments_linked_to_other_user=claim_res.skipped_assignments_linked_to_other_user,
                skipped_already_linked_same_user=claim_res.skipped_already_linked_same_user,
            )
            if claim_res.newly_attached_assignment_ids:
                rec = claim_res.to_api_dict()
                reconciliation_payload = PostSignupReconciliation(
                    linkedContactIds=rec.get("linkedContactIds") or [],
                    attachedAssignmentIds=rec.get("attachedAssignmentIds") or [],
                    skippedContactsLinkedToOtherUser=int(rec.get("skippedContactsLinkedToOtherUser") or 0),
                    skippedAssignmentsLinkedToOtherUser=int(
                        rec.get("skippedAssignmentsLinkedToOtherUser") or 0
                    ),
                    skippedRevokedInvites=int(rec.get("skippedRevokedInvites") or 0),
                    skippedAlreadyLinkedSameUser=int(rec.get("skippedAlreadyLinkedSameUser") or 0),
                    headline=rec.get("headline"),
                    message=rec.get("message"),
                )
        except concurrent.futures.TimeoutError:
            log.warning(
                "login claim_link timed_out user_id=%s timeout_s=%s",
                user["id"][:8],
                _RECONCILE_TIMEOUT_SECONDS,
            )
            identity_event(
                "identity.auth.signin.reconcile",
                request_id=request_id or None,
                auth_user_id=user["id"],
                outcome="timeout",
                timeout_seconds=_RECONCILE_TIMEOUT_SECONDS,
            )
        except Exception as rec_exc:
            log.warning("login claim_link skipped user_id=%s error=%s", user["id"][:8], rec_exc)
            identity_event(
                "identity.auth.signin.reconcile",
                request_id=request_id or None,
                auth_user_id=user["id"],
                outcome="error",
                error_type=type(rec_exc).__name__,
            )

    identity_event(
        "identity.auth.signin.ok",
        request_id=request_id or None,
        auth_user_id=user["id"],
        role=effective_role.value,
        principal_fingerprint=principal_fingerprint(user.get("email"), user.get("username")),
    )
    log.info("auth_login success user_id=%s", user["id"][:8])
    _audit_auth(entity_type="session", entity_id=user["id"], action_type=ACTION_INSERT, actor_id=user["id"])
    if user.get("email"):
        _dispatch_supabase_sync(
            user["email"],
            body.password,
            relopass_user_id=user["id"],
            full_name=user.get("name"),
        )
    _log_auth_perf(
        "/api/auth/login",
        request_id,
        user["id"],
        (time.perf_counter() - t0) * 1000,
        200,
    )
    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            username=user.get("username"),
            email=user.get("email"),
            role=effective_role,
            name=user.get("name"),
            company=profile.get("company_id") if profile else user.get("company"),
        ),
        reconciliation=reconciliation_payload,
    )


@router.post("/api/auth/logout")
def logout(
    payload: Optional[Dict[str, Any]] = Body(None),
    authorization: Optional[str] = Header(None),
):
    """
    Invalidate both auth halves:

      1. Legacy ReloPass session token (Authorization: Bearer <uuid>).
      2. Supabase JWT, if the client forwards it as
         `supabase_access_token` in the request body.

    The Supabase revocation is best-effort — a failure there does not block
    the legacy logout. The client MUST also call supabase.auth.signOut() on
    its end to clear the Supabase JS client's cached session. This endpoint
    covers the server-side revocation so a leaked JWT cannot be replayed
    for the remainder of its TTL.
    """
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        if token:
            db.delete_session_by_token(token)
            log.info("auth_logout legacy_token_invalidated")
            _audit_auth(entity_type="session", entity_id=token[:8] + "***", action_type=ACTION_DELETE)

    supabase_access_token = (payload or {}).get("supabase_access_token") if isinstance(payload, dict) else None
    if supabase_access_token and isinstance(supabase_access_token, str):
        # Imported lazily to avoid a hard dependency on the Supabase SDK at
        # module import time in environments without Supabase configured.
        from ..services.supabase_auth_sync import revoke_supabase_session

        def _revoke_outcome(fut: "concurrent.futures.Future[bool]") -> None:
            try:
                log.info("auth_logout supabase_token_revoked=%s", fut.result())
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("auth_logout supabase revoke exception=%s", exc)

        try:
            _supabase_sync_executor.submit(
                revoke_supabase_session, supabase_access_token
            ).add_done_callback(_revoke_outcome)
        except RuntimeError as ex:
            log.warning("auth_logout supabase revoke dispatch failed: %s", ex)

    return {"success": True}
