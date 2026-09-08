"""
Provider coordination endpoints.

HR management (require_admin_or_hr):
  GET  /api/hr/providers           — list providers scoped to a case (or whole org)
  GET  /api/hr/providers/org       — list all providers for the caller's org
  POST /api/hr/providers           — create a new provider in the org
  POST /api/hr/providers/invite    — invite a provider to a case (magic link)
  GET  /api/hr/provider-tasks      — list provider tasks for a case
  POST /api/hr/provider-tasks      — create and assign a task to a provider
  PATCH /api/hr/provider-tasks/{task_id} — update task status / fields
  GET  /api/hr/provider-status-grid — case × provider-type status matrix

Provider auth (provider JWT, no Supabase session):
  POST /api/provider/auth/accept   — redeem invite token (marks first use)
  GET  /api/provider/auth/verify   — lightweight token validity check

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
from typing import Any, Dict, List, Optional

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from ..auth_deps import require_admin_or_hr
from ..services.supabase_client import get_supabase_admin_client
from ..services.provider_jwt import generate_provider_token, verify_provider_token, hash_token
from ..db import SessionLocal
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["providers"])


def _audit_provider(actor_id, entity_type: str, entity_id: str, action: str,
                    event: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """[AIQ-932b] Fail-soft canonical audit for a provider-domain mutation. These
    endpoints write via the Supabase client (no SQLAlchemy router conn), so audit
    runs in its own SessionLocal txn with the actor threaded from the router."""
    try:
        with SessionLocal() as asession:
            insert_audit_log(
                asession.connection(),
                entity_type=entity_type,
                entity_id=str(entity_id),
                action_type=action,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
                new_value={"event": event, **(extra or {})},
            )
            asession.commit()
    except Exception:
        log.exception("audit: provider %s entity=%s id=%s", event, entity_type, entity_id)

_INVITE_EXPIRY_DAYS = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _caller_org_id(user: Dict[str, Any]) -> str:
    """Return org_id (company_id) for the authenticated HR user."""
    from ...database import db
    # UIAUDIT-G4 / AIQ-861 pattern: legacy or text HR ids (e.g. seed-hr-testingapril)
    # resolve their company ONLY via hr_users — the profiles path is uuid-keyed and
    # returns NULL for them. hr_users first, then profile / user.company.
    uid = user.get("id")
    org_id = (db.get_hr_company_id(uid) if uid else None) \
        or (db.get_profile_record(uid) or {}).get("company_id") \
        or user.get("company")
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
# Schemas — provider management
# ---------------------------------------------------------------------------

class ProviderItem(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


class ProviderListResponse(BaseModel):
    providers: List[ProviderItem]


class CreateProviderRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None


class ProviderTaskItem(BaseModel):
    id: str
    case_id: str
    provider_id: str
    provider_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    due_date: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class ProviderTaskListResponse(BaseModel):
    tasks: List[ProviderTaskItem]


class CreateProviderTaskRequest(BaseModel):
    case_id: str
    provider_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class PatchProviderTaskRequest(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Schemas — provider status grid
# ---------------------------------------------------------------------------

class ProviderGridCells(BaseModel):
    housing: str
    immigration: str
    shipping: str
    other: str


class ProviderGridRow(BaseModel):
    case_id: str
    employee_name: str
    employee_identifier: str
    dest_country: Optional[str] = None
    move_date: Optional[str] = None
    coordination_status: str
    cells: ProviderGridCells


class ProviderGridResponse(BaseModel):
    rows: List[ProviderGridRow]
    total: int


# ---------------------------------------------------------------------------
# Schemas — invite
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

@router.get("/api/hr/provider-status-grid", response_model=ProviderGridResponse)
def get_provider_status_grid(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderGridResponse:
    """
    Returns the case × provider-type status matrix for the HR grid view.

    Each row is an active case assignment. Each row contains four cells
    (housing / immigration / shipping / other) with a status value:
      'on-track' | 'at-risk' | 'blocked' | 'complete' | 'not-assigned'

    Recommended client polling interval: 60 seconds.
    """
    from ...database import db

    # UIAUDIT-G4: hr_users-first company resolution so legacy/text HR ids (e.g.
    # seed-hr-testingapril, whose profiles.company_id is NULL) resolve their company
    # and the grid shows their active cases instead of "0 active cases".
    uid = user.get("id")
    company_id = (db.get_hr_company_id(uid) if uid else None) \
        or (db.get_profile_record(uid) or {}).get("company_id") \
        or user.get("company")
    hr_user_id = uid

    raw_rows = db.get_provider_status_grid(
        company_id=str(company_id) if company_id else None,
        hr_user_id=str(hr_user_id) if hr_user_id else None,
    )

    grid_rows: List[ProviderGridRow] = []
    for r in raw_rows:
        cells_raw = r.get("cells") or {}
        grid_rows.append(
            ProviderGridRow(
                case_id=r["case_id"],
                employee_name=r.get("employee_name") or r.get("employee_identifier") or "",
                employee_identifier=r.get("employee_identifier") or "",
                dest_country=r.get("dest_country"),
                move_date=r.get("move_date"),
                coordination_status=r.get("coordination_status") or "not-started",
                cells=ProviderGridCells(
                    housing=cells_raw.get("housing", "not-assigned"),
                    immigration=cells_raw.get("immigration", "not-assigned"),
                    shipping=cells_raw.get("shipping", "not-assigned"),
                    other=cells_raw.get("other", "not-assigned"),
                ),
            )
        )

    return ProviderGridResponse(rows=grid_rows, total=len(grid_rows))


@router.get("/api/hr/providers/org", response_model=ProviderListResponse)
def list_org_providers(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderListResponse:
    """List all providers registered for the caller's organisation."""
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()
    rows = (
        supa.table("providers")
        .select("id,name,email,phone,service_type,notes,created_at")
        .eq("org_id", org_id)
        .order("name")
        .execute()
    ).data or []
    return ProviderListResponse(
        providers=[
            ProviderItem(
                id=str(r["id"]),
                name=r.get("name", ""),
                email=r.get("email"),
                phone=r.get("phone"),
                service_type=r.get("service_type"),
                notes=r.get("notes"),
                created_at=str(r.get("created_at", "")),
            )
            for r in rows
        ]
    )


@router.get("/api/hr/providers", response_model=ProviderListResponse)
def list_case_providers(
    case_id: str = Query(..., description="Case ID to scope provider list"),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderListResponse:
    """
    List providers that have at least one task on a specific case.
    Falls back to all org providers when no tasks exist yet.
    """
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()

    # Providers with tasks on this case
    task_rows = (
        supa.table("provider_tasks")
        .select("provider_id")
        .eq("case_id", case_id)
        .eq("org_id", org_id)
        .execute()
    ).data or []
    linked_ids = list({r["provider_id"] for r in task_rows})

    if linked_ids:
        rows = (
            supa.table("providers")
            .select("id,name,email,phone,service_type,notes,created_at")
            .in_("id", linked_ids)
            .order("name")
            .execute()
        ).data or []
    else:
        # Return all org providers so HR can pick one
        rows = (
            supa.table("providers")
            .select("id,name,email,phone,service_type,notes,created_at")
            .eq("org_id", org_id)
            .order("name")
            .execute()
        ).data or []

    return ProviderListResponse(
        providers=[
            ProviderItem(
                id=str(r["id"]),
                name=r.get("name", ""),
                email=r.get("email"),
                phone=r.get("phone"),
                service_type=r.get("service_type"),
                notes=r.get("notes"),
                created_at=str(r.get("created_at", "")),
            )
            for r in rows
        ]
    )


@router.post("/api/hr/providers", response_model=ProviderItem)
def create_provider(
    body: CreateProviderRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderItem:
    """Create a new provider record in the caller's organisation."""
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()
    provider_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "id": provider_id,
        "org_id": org_id,
        "name": body.name,
        "email": body.email,
        "phone": body.phone,
        "service_type": body.service_type,
        "notes": body.notes,
        "created_by": user.get("id", ""),
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    supa.table("providers").insert(row).execute()
    _audit_provider(user.get("id"), "provider", provider_id, ACTION_INSERT,
                    "provider_created", {"service_type": body.service_type})
    log.info("Provider created: id=%s org_id=%s name=%s", provider_id, org_id, body.name)
    return ProviderItem(
        id=provider_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        service_type=body.service_type,
        notes=body.notes,
        created_at=now_iso,
    )


@router.get("/api/hr/provider-tasks", response_model=ProviderTaskListResponse)
def list_provider_tasks(
    case_id: str = Query(..., description="Case ID to filter tasks"),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderTaskListResponse:
    """List all provider tasks for a case, enriched with provider names."""
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()

    tasks = (
        supa.table("provider_tasks")
        .select("id,case_id,provider_id,title,description,status,due_date,notes,created_at,updated_at")
        .eq("case_id", case_id)
        .eq("org_id", org_id)
        .order("created_at")
        .execute()
    ).data or []

    # Enrich with provider names (batch lookup)
    provider_ids = list({t["provider_id"] for t in tasks})
    name_map: Dict[str, str] = {}
    if provider_ids:
        prov_rows = (
            supa.table("providers")
            .select("id,name")
            .in_("id", provider_ids)
            .execute()
        ).data or []
        name_map = {str(p["id"]): p.get("name", "") for p in prov_rows}

    return ProviderTaskListResponse(
        tasks=[
            ProviderTaskItem(
                id=str(t["id"]),
                case_id=str(t["case_id"]),
                provider_id=str(t["provider_id"]),
                provider_name=name_map.get(str(t["provider_id"])),
                title=t.get("title", ""),
                description=t.get("description"),
                status=t.get("status", "pending"),
                due_date=str(t["due_date"]) if t.get("due_date") else None,
                notes=t.get("notes"),
                created_at=str(t.get("created_at", "")),
                updated_at=str(t.get("updated_at", "")),
            )
            for t in tasks
        ]
    )


@router.post("/api/hr/provider-tasks", response_model=ProviderTaskItem)
def create_provider_task(
    body: CreateProviderTaskRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderTaskItem:
    """Create a task and assign it to a provider for a specific case."""
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()

    # Verify provider belongs to this org
    prov_rows = (
        supa.table("providers")
        .select("id,name")
        .eq("id", body.provider_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    ).data or []
    if not prov_rows:
        raise HTTPException(status_code=404, detail="Provider not found in this organisation.")
    provider_name = prov_rows[0].get("name", "")

    task_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "id": task_id,
        "case_id": body.case_id,
        "provider_id": body.provider_id,
        "org_id": org_id,
        "title": body.title,
        "description": body.description,
        "status": "pending",
        "due_date": body.due_date,
        "notes": body.notes,
        "created_by": user.get("id", ""),
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    supa.table("provider_tasks").insert(row).execute()
    log.info("Provider task created: id=%s case=%s provider=%s", task_id, body.case_id, body.provider_id)

    return ProviderTaskItem(
        id=task_id,
        case_id=body.case_id,
        provider_id=body.provider_id,
        provider_name=provider_name,
        title=body.title,
        description=body.description,
        status="pending",
        due_date=body.due_date,
        notes=body.notes,
        created_at=now_iso,
        updated_at=now_iso,
    )


@router.patch("/api/hr/provider-tasks/{task_id}", response_model=ProviderTaskItem)
def patch_provider_task(
    task_id: str,
    body: PatchProviderTaskRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> ProviderTaskItem:
    """Update status or fields of a provider task."""
    org_id = _caller_org_id(user)
    supa = get_supabase_admin_client()

    # Load existing task
    task_rows = (
        supa.table("provider_tasks")
        .select("*")
        .eq("id", task_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    ).data or []
    if not task_rows:
        raise HTTPException(status_code=404, detail="Task not found.")
    task = task_rows[0]

    # Validate status value if provided
    valid_statuses = {"pending", "in_progress", "completed", "blocked"}
    if body.status and body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(valid_statuses)}.")

    updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.status is not None:
        updates["status"] = body.status
    if body.title is not None:
        updates["title"] = body.title
    if body.description is not None:
        updates["description"] = body.description
    if body.due_date is not None:
        updates["due_date"] = body.due_date
    if body.notes is not None:
        updates["notes"] = body.notes

    supa.table("provider_tasks").update(updates).eq("id", task_id).execute()
    _audit_provider(user.get("id"), "provider_task", task_id, ACTION_UPDATE,
                    "provider_task_updated", {"status": body.status} if body.status else None)

    # Enrich with provider name
    prov_rows = (
        supa.table("providers").select("name").eq("id", task["provider_id"]).limit(1).execute()
    ).data or []
    provider_name = prov_rows[0].get("name") if prov_rows else None

    merged = {**task, **updates}
    return ProviderTaskItem(
        id=str(merged["id"]),
        case_id=str(merged["case_id"]),
        provider_id=str(merged["provider_id"]),
        provider_name=provider_name,
        title=merged.get("title", ""),
        description=merged.get("description"),
        status=merged.get("status", "pending"),
        due_date=str(merged["due_date"]) if merged.get("due_date") else None,
        notes=merged.get("notes"),
        created_at=str(merged.get("created_at", "")),
        updated_at=str(merged.get("updated_at", "")),
    )


# ---------------------------------------------------------------------------
# Routes — invite + auth
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
    _audit_provider(user.get("id"), "provider_invite", invite_id, ACTION_INSERT,
                    "provider_invited", {"provider_id": body.provider_id, "case_id": body.case_id})

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
            # Public endpoint — the actor is the vendor redeeming via signed token.
            _audit_provider(provider_id, "provider_invite", invite["id"], ACTION_UPDATE,
                            "provider_invite_accepted", {"case_id": case_id})
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
