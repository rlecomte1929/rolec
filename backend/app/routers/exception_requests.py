"""
Exception requests — employee asks HR to allow an estimate that exceeds policy cap.
T1.3 from the Sprint 2 execution plan.

Endpoints (all require authenticated session):
  POST   /api/cases/{case_id}/exception-requests   — employee creates
  GET    /api/cases/{case_id}/exception-requests   — employee + HR read for case
  PATCH  /api/exception-requests/{id}              — HR approves/rejects with note

Tenant isolation: every query is scoped by `organization_id` (the caller's
profile.company_id). HR can only see/resolve requests for their own company;
employees can only see requests on cases they own.

Audit: every POST and PATCH writes an `audit_logs` row with
`actor_type=human` and the caller's user id, regardless of tier (the
write hits whatever DB `db.engine` points at — Postgres in prod, SQLite
in local dev).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_current_user, require_hr_or_employee
from ...database import db
from ...services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)

router = APIRouter(tags=["exception_requests"])
logger = logging.getLogger(__name__)

VALID_STATUSES = ("pending", "approved", "rejected")
RESOLVABLE_STATUSES = ("approved", "rejected")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExceptionRequestCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    requested_amount: float = Field(..., ge=0)
    cap_amount: float = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3)
    reason: str = Field(..., min_length=1, max_length=2000)


class ExceptionRequestPatch(BaseModel):
    status: str = Field(..., pattern=r"^(approved|rejected)$")
    hr_note: Optional[str] = Field(None, max_length=2000)


class ExceptionRequestRead(BaseModel):
    id: str
    case_id: str
    organization_id: str
    category: str
    requested_amount: float
    cap_amount: float
    currency: str
    reason: str
    status: str
    hr_note: Optional[str]
    requested_by_user_id: str
    resolved_by_user_id: Optional[str]
    created_at: str
    resolved_at: Optional[str]
    updated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _caller_company_id(user: Dict[str, Any]) -> str:
    """Resolve the caller's company id from their profile; 403 if missing."""
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — exception requests need a tenant.",
        )
    return company_id


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Normalize a SQLAlchemy mapping row into a JSON-safe dict."""
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return d


def _audit(
    *,
    request_id: str,
    action: str,
    actor_id: str,
    new_value: Optional[Dict[str, Any]] = None,
    old_value: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an audit_logs row; never raise (audit must not break the request)."""
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="exception_requests",
                entity_id=request_id,
                action_type=action,
                old_value=old_value,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        logger.exception("audit_log write failed exception_requests id=%s", request_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/api/cases/{case_id}/exception-requests",
    response_model=ExceptionRequestRead,
    status_code=201,
)
def create_exception_request(
    case_id: str,
    body: ExceptionRequestCreate,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """
    Employee (or HR on their behalf) opens an exception request for a case.
    Tenant scoping: organization_id = caller's company_id. The case_id is
    trusted as a string identifier here (the heavy validation lives in the
    Postgres FK + RLS); local SQLite tier is permissive.
    """
    organization_id = _caller_company_id(user)
    actor_id = user["id"]
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO exception_requests (
                    id, case_id, organization_id, category,
                    requested_amount, cap_amount, currency, reason,
                    status, requested_by_user_id, created_at, updated_at
                ) VALUES (
                    :id, :case_id, :org, :cat,
                    :req_amt, :cap_amt, :cur, :reason,
                    'pending', :actor, :now, :now
                )
                """
            ),
            {
                "id": new_id,
                "case_id": case_id,
                "org": organization_id,
                "cat": body.category,
                "req_amt": body.requested_amount,
                "cap_amt": body.cap_amount,
                "cur": body.currency.upper(),
                "reason": body.reason,
                "actor": actor_id,
                "now": now,
            },
        )
        row = conn.execute(
            text("SELECT * FROM exception_requests WHERE id = :id"),
            {"id": new_id},
        ).mappings().first()

    _audit(
        request_id=new_id,
        action=ACTION_INSERT,
        actor_id=actor_id,
        new_value={
            "case_id": case_id,
            "organization_id": organization_id,
            "category": body.category,
            "requested_amount": body.requested_amount,
            "cap_amount": body.cap_amount,
            "currency": body.currency.upper(),
            "status": "pending",
        },
    )
    return _row_to_dict(row)


@router.get(
    "/api/cases/{case_id}/exception-requests",
    response_model=List[ExceptionRequestRead],
)
def list_exception_requests_for_case(
    case_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> List[Dict[str, Any]]:
    """List all exception requests on a case, scoped to the caller's company."""
    organization_id = _caller_company_id(user)
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT * FROM exception_requests
                WHERE case_id = :case_id AND organization_id = :org
                ORDER BY created_at DESC
                """
            ),
            {"case_id": case_id, "org": organization_id},
        ).mappings().all()
    return [_row_to_dict(r) for r in rows]


@router.patch(
    "/api/exception-requests/{request_id}",
    response_model=ExceptionRequestRead,
)
def resolve_exception_request(
    request_id: str,
    body: ExceptionRequestPatch,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """HR approves or rejects an exception request, optionally with a note."""
    role = (user.get("role") or "").upper()
    if role not in ("HR", "ADMIN") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")

    organization_id = _caller_company_id(user)
    actor_id = user["id"]
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT * FROM exception_requests WHERE id = :id AND organization_id = :org"
            ),
            {"id": request_id, "org": organization_id},
        ).mappings().first()
        if not existing:
            raise HTTPException(status_code=404, detail="Exception request not found")
        if existing["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request is already {existing['status']}; cannot change.",
            )

        conn.execute(
            text(
                """
                UPDATE exception_requests
                SET status = :status,
                    hr_note = :note,
                    resolved_by_user_id = :actor,
                    resolved_at = :now,
                    updated_at = :now
                WHERE id = :id
                """
            ),
            {
                "status": body.status,
                "note": body.hr_note,
                "actor": actor_id,
                "now": now,
                "id": request_id,
            },
        )
        row = conn.execute(
            text("SELECT * FROM exception_requests WHERE id = :id"),
            {"id": request_id},
        ).mappings().first()

    _audit(
        request_id=request_id,
        action=ACTION_UPDATE,
        actor_id=actor_id,
        old_value={"status": existing["status"]},
        new_value={
            "status": body.status,
            "hr_note": body.hr_note,
            "resolved_by_user_id": actor_id,
        },
    )
    return _row_to_dict(row)
