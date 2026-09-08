"""
Policy Builder — HR policy version CRUD (AIQ-37-A/B/C).

Routes (all require HR or Admin):
  GET    /api/hr/policies              — list all versions for the caller's org
  GET    /api/hr/policies/active       — get the currently active version
  POST   /api/hr/policies              — create a new draft version
  PATCH  /api/hr/policies/{policy_id}  — update label / json_schema of a draft
  POST   /api/hr/policies/{policy_id}/activate — atomically activate a version

The relocation_policies + policy_audit_log tables are defined in
supabase/migrations/20260513150000_relocation_policy_builder_schema.sql.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import require_admin_or_hr
from ...database import db
from ..db import SessionLocal
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr/policies", tags=["hr_policies"])


def _audit_policy(user: Dict[str, Any], policy_id: str, action: str,
                  event: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """[AIQ-932] Fail-soft canonical audit for a relocation-policy mutation. The
    write goes through the Supabase client (no SQLAlchemy router conn), so audit
    runs in its own SessionLocal txn."""
    try:
        with SessionLocal() as asession:
            insert_audit_log(
                asession.connection(),
                entity_type="relocation_policy",
                entity_id=str(policy_id),
                action_type=action,
                actor_type=ACTOR_HUMAN,
                actor_id=user.get("id") or user.get("sub"),
                new_value={"event": event, **(extra or {})},
            )
            asession.commit()
    except Exception:
        log.exception("audit: policy %s id=%s", event, policy_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _org_id(user: Dict[str, Any]) -> str:
    """Return the caller's company_id — used as org_id in relocation_policies."""
    uid = user.get("id")
    # hr_users-first: legacy/text HR ids have NULL profiles.company_id but a valid hr_users row.
    company_id = (db.get_hr_company_id(uid) if uid else None) or (db.get_profile_record(uid) or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — policy management requires a tenant.",
        )
    return company_id


def _sb():
    """Lazy Supabase admin client (fails fast if env vars missing)."""
    return get_supabase_admin_client()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PolicyJsonSchema(BaseModel):
    """Flexible container for the 5 wizard dimensions — validated at TypeScript level."""
    tiers: List[Dict[str, Any]] = Field(default_factory=list)
    budgets: Dict[str, Any] = Field(default_factory=dict)
    documents: Dict[str, Any] = Field(default_factory=dict)
    vendor_categories: Dict[str, Any] = Field(default_factory=dict)
    approval_workflow: Dict[str, Any] = Field(default_factory=dict)


class CreatePolicyRequest(BaseModel):
    label: Optional[str] = None
    json_schema: PolicyJsonSchema = Field(default_factory=PolicyJsonSchema)


class PatchPolicyRequest(BaseModel):
    label: Optional[str] = None
    json_schema: Optional[PolicyJsonSchema] = None


class PolicyVersionOut(BaseModel):
    id: str
    org_id: str
    version: int
    is_active: bool
    label: Optional[str]
    created_at: str
    created_by: Optional[str]
    json_schema: Dict[str, Any]


class PolicyListResponse(BaseModel):
    ok: bool = True
    org_id: str
    policies: List[PolicyVersionOut]


class ActivePolicyResponse(BaseModel):
    ok: bool = True
    policy: Optional[PolicyVersionOut]


class CreatePolicyResponse(BaseModel):
    ok: bool = True
    policy: PolicyVersionOut


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=PolicyListResponse)
def list_policies(user: Dict[str, Any] = Depends(require_admin_or_hr)):
    """List all policy versions for the caller's org, newest first."""
    org_id = _org_id(user)
    try:
        result = (
            _sb()
            .table("relocation_policies")
            .select("*")
            .eq("org_id", org_id)
            .order("version", desc=True)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        log.exception("list_policies failed org=%s", org_id)
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    return PolicyListResponse(
        org_id=org_id,
        policies=[PolicyVersionOut(**r) for r in rows],
    )


@router.get("/active", response_model=ActivePolicyResponse)
def get_active_policy(user: Dict[str, Any] = Depends(require_admin_or_hr)):
    """Return the currently active policy version, or null if none."""
    org_id = _org_id(user)
    try:
        result = (
            _sb()
            .table("relocation_policies")
            .select("*")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        log.exception("get_active_policy failed org=%s", org_id)
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    return ActivePolicyResponse(
        policy=PolicyVersionOut(**rows[0]) if rows else None
    )


@router.post("", response_model=CreatePolicyResponse, status_code=201)
def create_policy(
    body: CreatePolicyRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
):
    """Create a new (inactive) draft policy version. Version number auto-increments."""
    org_id = _org_id(user)
    user_id = user.get("id")

    # Compute next version number
    try:
        ver_result = (
            _sb()
            .table("relocation_policies")
            .select("version")
            .eq("org_id", org_id)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        existing = ver_result.data or []
        next_version = (existing[0]["version"] + 1) if existing else 1
    except Exception as exc:
        log.exception("create_policy version lookup failed org=%s", org_id)
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    new_row = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "version": next_version,
        "is_active": False,
        "json_schema": body.json_schema.model_dump(),
        "created_by": user_id,
        "label": body.label,
    }

    try:
        ins = _sb().table("relocation_policies").insert(new_row).execute()
        row = (ins.data or [new_row])[0]
    except Exception as exc:
        log.exception("create_policy insert failed org=%s", org_id)
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    _audit_policy(user, row.get("id") or new_row["id"], ACTION_INSERT,
                  "policy_created", {"version": next_version, "label": body.label})

    return CreatePolicyResponse(policy=PolicyVersionOut(**row))


@router.patch("/{policy_id}", response_model=CreatePolicyResponse)
def update_policy(
    policy_id: str,
    body: PatchPolicyRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
):
    """Update label and/or json_schema of an existing policy version (draft or active)."""
    org_id = _org_id(user)

    updates: Dict[str, Any] = {}
    if body.label is not None:
        updates["label"] = body.label
    if body.json_schema is not None:
        updates["json_schema"] = body.json_schema.model_dump()

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    try:
        result = (
            _sb()
            .table("relocation_policies")
            .update(updates)
            .eq("id", policy_id)
            .eq("org_id", org_id)   # tenant isolation
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        log.exception("update_policy failed id=%s org=%s", policy_id, org_id)
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="Policy version not found.")

    _audit_policy(user, policy_id, ACTION_UPDATE, "policy_updated",
                  {"fields": list(updates.keys())})

    return CreatePolicyResponse(policy=PolicyVersionOut(**rows[0]))


@router.post("/{policy_id}/activate", response_model=CreatePolicyResponse)
def activate_policy(
    policy_id: str,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
):
    """Atomically activate the given policy version, deactivating any previous active version."""
    org_id = _org_id(user)
    user_id = user.get("id")

    try:
        # Call the DB helper function (security definer, handles atomicity)
        result = _sb().rpc(
            "activate_policy_version",
            {"p_new_version_id": policy_id, "p_org_id": org_id, "p_changed_by": user_id},
        ).execute()
    except Exception as exc:
        log.exception("activate_policy rpc failed id=%s org=%s", policy_id, org_id)
        raise HTTPException(status_code=502, detail=f"Activation error: {exc}") from exc

    # Fetch the freshly-activated row to return
    try:
        fetch = (
            _sb()
            .table("relocation_policies")
            .select("*")
            .eq("id", policy_id)
            .single()
            .execute()
        )
        row = fetch.data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    if not row:
        raise HTTPException(status_code=404, detail="Policy version not found after activation.")

    _audit_policy(user, policy_id, ACTION_UPDATE, "policy_activated",
                  {"version": row.get("version")})

    return CreatePolicyResponse(policy=PolicyVersionOut(**row))
