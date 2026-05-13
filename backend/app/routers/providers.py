"""
Provider coordination endpoints.

POST /api/hr/providers/invite     — HR invites a provider to a case
POST /api/provider/auth/accept    — Provider redeems invite token (marks first use)
GET  /api/provider/auth/verify    — Lightweight token validation check

Auth model:
  - /api/hr/*  routes: require HR or Admin role (existing require_admin_or_hr dep)
  - /api/provider/* routes: Bearer token is the provider JWT itself; validated
    inline — no Supabase auth session required for providers.

Email delivery:
  If RESEND_API_KEY is set, the invite email is sent via Resend (api.resend.com).
  If unset, the magic link is logged at INFO level (dev / staging mode).
  Set EMAIL_FROM to control the sender address (default: noreply@relopass.com).
  Set APP_BASE_URL to control the link origin (default: https://app.relopass.com).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from ..auth_deps import require_admin_or_hr
from ...services.supabase_client import get_supabase_admin_client
from ...services.provider_jwt import generate_provider_token, verify_provider_token, hash_token

log = logging.getLogger(__name__)

router = APIRouter(tags=["providers"])

_INVITE_EXPIRY_DAYS = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _caller_org_id(user: Dict[str, Any]) -> str:
    """Return org_id (company_id) for the authenticated HR user."""
    from ...database import db
    profile = db.get_profile_record(user.get("id"))
    org_id = (profile or {}).get("company_id") or user.get("company")
    if not org_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this HR profile.",
        )
    return str(org_id)


def _send_invite_email(to_email: str, magic_link: str, provider_name: str) -> None:
    """
    Send the provider invite email.

    Uses Resend if RESEND_API_KEY is configured; otherwise logs the link.
    """
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("EMAIL_FROM", "noreply@relopass.com")

    plain_text, html_body = _render_invite_email(magic_link, provider_name)

    if resend_key:
        resp = http_requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_addr,
                "to": [to_email],
                "subject": f"You've been invited to coordinate on ReloPass — {provider_name}",
                "text": plain_text,
                "html": html_body,
            },
            timeout=10,
        )
        if not resp.ok:
            log.error("Resend delivery failed: %s %s", resp.status_code, resp.text[:200])
            raise HTTPException(
                status_code=502,
                detail=f"Email delivery failed (Resend {resp.status_code}).",
            )
        log.info("Invite email sent via Resend to %s", to_email)
    else:
        # Dev fallback — log the link so local testing works without email config
        log.info(
            "PROVIDER INVITE LINK (no RESEND_API_KEY set): %s",
            magic_link,
        )


def _render_invite_email(magic_link: str, provider_name: str) -> tuple[str, str]:
    """Return (plain_text, html) for the invite email."""
    plain = f"""You have been invited to coordinate on a relocation case via ReloPass.

Click the link below to access your task portal. The link is valid for {_INVITE_EXPIRY_DAYS} days.

{magic_link}

If you were not expecting this invitation, you can safely ignore this email.

— The ReloPass Team
"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 32px 16px;">
  <img src="https://app.relopass.com/logo.png" alt="ReloPass" style="height: 32px; margin-bottom: 32px;">
  <h2 style="font-size: 20px; font-weight: 600; margin: 0 0 12px;">You have a new relocation task</h2>
  <p style="margin: 0 0 24px; color: #555; line-height: 1.6;">
    You've been invited to coordinate on a relocation case as a service provider.
    Click the button below to view your assigned tasks.
  </p>
  <a href="{magic_link}"
     style="display: inline-block; background: #2563eb; color: #fff; text-decoration: none;
            padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 15px;">
    Open task portal
  </a>
  <p style="margin: 24px 0 0; font-size: 13px; color: #888;">
    This link expires in {_INVITE_EXPIRY_DAYS} days. If you were not expecting this invitation, ignore this email.
  </p>
</body>
</html>
"""
    return plain, html


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InviteRequest(BaseModel):
    provider_id: str          # UUID of the providers row
    email: str                # Email address to send the invite to
    case_id: str              # case_id this invite is scoped to


class InviteResponse(BaseModel):
    invite_id: str
    email: str
    expires_at: str           # ISO timestamp
    magic_link: Optional[str] = None  # only populated if RESEND_API_KEY unset (dev mode)


class AcceptRequest(BaseModel):
    token: str


class AcceptResponse(BaseModel):
    valid: bool
    provider_id: str
    org_id: str
    case_id: str
    token: str                # echo the token back for the client to store


class VerifyResponse(BaseModel):
    valid: bool
    provider_id: Optional[str] = None
    org_id: Optional[str] = None
    case_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/api/hr/providers/invite", response_model=InviteResponse)
def invite_provider(
    body: InviteRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> InviteResponse:
    """
    HR invites a provider to a case.

    Creates a provider_invites record, generates a signed JWT magic link,
    and sends the invite email (or logs the link in dev mode).
    """
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()

    # Verify the provider exists and belongs to this org
    provider_resp = (
        supa.table("providers")
        .select("id, name, org_id")
        .eq("id", body.provider_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    rows = provider_resp.data or []
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Provider not found or does not belong to your organisation.",
        )
    provider = rows[0]

    # Generate JWT
    token = generate_provider_token(
        provider_id=body.provider_id,
        org_id=org_id,
        case_id=body.case_id,
        email=body.email,
        expires_days=_INVITE_EXPIRY_DAYS,
    )
    token_hash = hash_token(token)

    now_iso = datetime.now(timezone.utc).isoformat()
    from datetime import timedelta
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=_INVITE_EXPIRY_DAYS)
    ).isoformat()

    # Persist invite record
    invite_id = str(uuid.uuid4())
    supa.table("provider_invites").insert({
        "id": invite_id,
        "provider_id": body.provider_id,
        "org_id": org_id,
        "case_id": body.case_id,
        "email": body.email,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "created_by": user.get("id", ""),
        "created_at": now_iso,
    }).execute()

    # Build magic link
    app_base = os.getenv("APP_BASE_URL", "https://app.relopass.com").rstrip("/")
    magic_link = f"{app_base}/provider/portal?token={token}"

    # Send (or log) the email
    _send_invite_email(
        to_email=body.email,
        magic_link=magic_link,
        provider_name=provider.get("name", "Provider"),
    )

    log.info(
        "Provider invite created: invite_id=%s provider_id=%s email=%s org_id=%s",
        invite_id, body.provider_id, body.email, org_id,
    )

    # In dev mode (no RESEND_API_KEY), return the link in the response so
    # the caller can test the flow without a real email.
    dev_link = magic_link if not os.getenv("RESEND_API_KEY") else None

    return InviteResponse(
        invite_id=invite_id,
        email=body.email,
        expires_at=expires_at,
        magic_link=dev_link,
    )


@router.post("/api/provider/auth/accept", response_model=AcceptResponse)
def accept_provider_invite(body: AcceptRequest) -> AcceptResponse:
    """
    Provider redeems an invite token.

    Validates the JWT, marks the invite as first-used if not already, and
    returns the validated claims. The client should store the token and use
    it as the Bearer token for all subsequent /api/provider/* requests.

    This endpoint is public — no HR session required.
    """
    try:
        import jwt as pyjwt
        claims = verify_provider_token(body.token)
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}") from exc

    provider_id = claims["provider_id"]
    org_id = claims["org_id"]
    case_id = claims["case_id"]

    # Mark first use if not already recorded
    supa = get_supabase_admin_client()
    token_hash = hash_token(body.token)
    invite_rows = (
        supa.table("provider_invites")
        .select("id, first_used_at, revoked_at")
        .eq("token_hash", token_hash)
        .limit(1)
        .execute()
    ).data or []

    if invite_rows:
        invite = invite_rows[0]
        if invite.get("revoked_at"):
            raise HTTPException(status_code=401, detail="This invite has been revoked.")
        if not invite.get("first_used_at"):
            supa.table("provider_invites").update({
                "first_used_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", invite["id"]).execute()
            log.info("Provider invite first use: provider_id=%s", provider_id)

    return AcceptResponse(
        valid=True,
        provider_id=provider_id,
        org_id=org_id,
        case_id=case_id,
        token=body.token,
    )


@router.get("/api/provider/auth/verify", response_model=VerifyResponse)
def verify_provider_token_endpoint(token: str) -> VerifyResponse:
    """
    Lightweight token validity check.

    Returns {valid: true, provider_id, org_id, case_id} or {valid: false}.
    Used by the frontend to check if a stored token is still valid before
    rendering the provider portal.
    """
    try:
        claims = verify_provider_token(token)
        return VerifyResponse(
            valid=True,
            provider_id=claims["provider_id"],
            org_id=claims["org_id"],
            case_id=claims["case_id"],
        )
    except Exception:
        return VerifyResponse(valid=False)
