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

from ..auth_deps import get_current_user, require_hr_or_employee, require_case_access
from ...database import db
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.precedent_insight_service import (
    compute_precedent_insight,
    insight_recommendation_id,
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
    # GAP 7: Enriched fields (all optional for backward compat)
    benefit_key: Optional[str] = Field(None, max_length=100)
    type_label: Optional[str] = Field(None, max_length=200)
    current_value: Optional[Dict[str, Any]] = None   # e.g. {"amount": 1500, "currency": "EUR"}
    requested_value: Optional[Dict[str, Any]] = None  # e.g. {"amount": 2200, "currency": "EUR"}


class ExceptionRequestPatch(BaseModel):
    status: str = Field(..., pattern=r"^(approved|rejected)$")
    hr_note: Optional[str] = Field(None, max_length=2000)
    ai_insight: Optional[str] = Field(None, max_length=2000)


class PrecedentInsight(BaseModel):
    """Structured precedent insight (AI-005). See precedent_insight_service.py."""
    rationale: str
    confidence: float
    historical_approval_rate: float
    sample_size: int
    similar_case_ids: List[str]
    generated_at: str
    source_version: str
    recommendation_id: str  # for ai_decisions correlation


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
    # GAP 7: Enriched fields
    benefit_key: Optional[str] = None
    type_label: Optional[str] = None
    current_value: Optional[Dict[str, Any]] = None
    requested_value: Optional[Dict[str, Any]] = None
    ai_insight: Optional[str] = None
    # AI-005: structured precedent payload (replaces the plain `ai_insight` string
    # for new callers; old callers can keep reading `ai_insight` for back-compat).
    precedent_insight: Optional[PrecedentInsight] = None
    audit_events: Optional[List[Dict[str, Any]]] = None
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


def _attach_precedent_insight(conn, row: Dict[str, Any]) -> Dict[str, Any]:
    """Compute and attach a structured precedent insight (AI-005) to a row.
    Only pending rows get insights — decided rows are already resolved, so the
    insight is no longer load-bearing for an oversight decision. Failures are
    swallowed so the audit pipeline never breaks the user-facing request.
    """
    if row.get("status") != "pending":
        return row
    try:
        insight = compute_precedent_insight(
            conn,
            category=str(row.get("category") or ""),
            benefit_key=row.get("benefit_key"),
            organization_id=str(row.get("organization_id") or ""),
            exclude_request_id=str(row.get("id") or ""),
        )
        insight["recommendation_id"] = insight_recommendation_id(str(row["id"]))
        row["precedent_insight"] = insight
    except Exception:
        logger.exception("precedent_insight compute failed for id=%s", row.get("id"))
    return row


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
    # B21 fix: employees must own this case; HR is scoped to their company.
    require_case_access(case_id, user)
    actor_id = user["id"]
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO policy_cap_requests (
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
            text("SELECT * FROM policy_cap_requests WHERE id = :id"),
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
    # B21 fix: employees must own this case; HR is scoped to their company.
    require_case_access(case_id, user)
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT * FROM policy_cap_requests
                WHERE case_id = :case_id AND organization_id = :org
                ORDER BY created_at DESC
                """
            ),
            {"case_id": case_id, "org": organization_id},
        ).mappings().all()
        dicts = [_attach_precedent_insight(conn, _row_to_dict(r)) for r in rows]
    return dicts


@router.get(
    "/api/exception-requests/{request_id}",
    response_model=ExceptionRequestRead,
)
def get_exception_request(
    request_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """HR / Admin: fetch one exception request with the AI-005 structured
    `precedent_insight` attached when the row is still pending."""
    role = (user.get("role") or "").upper()
    if role not in ("HR", "ADMIN") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")
    organization_id = _caller_company_id(user)
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM policy_cap_requests "
                "WHERE id = :id AND organization_id = :org"
            ),
            {"id": request_id, "org": organization_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Exception request not found")
        return _attach_precedent_insight(conn, _row_to_dict(row))


@router.get(
    "/api/exception-requests",
    response_model=List[ExceptionRequestRead],
)
def list_exception_requests_for_company(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    HR / Admin: list all exception requests across the caller's company.
    Optional ?status=pending|approved|rejected filter for the queue view.
    """
    role = (user.get("role") or "").upper()
    if role not in ("HR", "ADMIN") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")

    organization_id = _caller_company_id(user)
    with db.engine.begin() as conn:
        if status:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_cap_requests "
                    "WHERE organization_id = :org AND status = :status "
                    "ORDER BY created_at DESC"
                ),
                {"org": organization_id, "status": status},
            ).mappings().all()
        else:
            rows = conn.execute(
                text(
                    "SELECT * FROM policy_cap_requests "
                    "WHERE organization_id = :org "
                    "ORDER BY created_at DESC"
                ),
                {"org": organization_id},
            ).mappings().all()
        dicts = [_attach_precedent_insight(conn, _row_to_dict(r)) for r in rows]
    return dicts


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
                "SELECT * FROM policy_cap_requests WHERE id = :id AND organization_id = :org"
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
                UPDATE policy_cap_requests
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
            text("SELECT * FROM policy_cap_requests WHERE id = :id"),
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


# ─────────────────────────────────────────────────────────────────────────────
# GAP 7: Assignment-scoped exception endpoints (Supabase-backed)
# ─────────────────────────────────────────────────────────────────────────────

class AssignmentExceptionCreate(BaseModel):
    """Body for creating an exception request scoped to an assignment (not a case draft)."""
    benefit_key: str = Field(..., min_length=1, max_length=100)
    type_label: str = Field(..., min_length=1, max_length=200)
    current_value: Dict[str, Any]
    requested_value: Dict[str, Any]
    reason: str = Field(..., min_length=1, max_length=2000)


class AssignmentExceptionRead(BaseModel):
    id: str
    assignment_id: str
    benefit_key: str
    type_label: Optional[str] = None
    current_value: Optional[Dict[str, Any]] = None
    requested_value: Optional[Dict[str, Any]] = None
    reason: str
    status: str  # pending | approved | rejected
    hr_note: Optional[str] = None
    ai_insight: Optional[str] = None
    audit_events: Optional[List[Dict[str, Any]]] = None
    requested_by_user_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _get_supabase():
    from ..services.supabase_client import get_supabase_admin_client
    return get_supabase_admin_client()


@router.get(
    "/api/assignments/{assignment_id}/exceptions",
    response_model=List[AssignmentExceptionRead],
)
def list_assignment_exceptions(
    assignment_id: str,
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    GAP 7: List all exception requests for an assignment.
    Optionally filter by status: pending | approved | rejected.
    """
    try:
        sb = _get_supabase()
        q = (
            sb.table("exception_requests")
            .select("*")
            .eq("assignment_id", assignment_id)
        )
        if status:
            q = q.eq("status", status)
        result = q.order("created_at", desc=True).execute()
        rows = result.data if result and result.data else []
        return rows
    except Exception:
        logger.exception("list_assignment_exceptions failed assignment_id=%s", assignment_id)
        return []


@router.post(
    "/api/assignments/{assignment_id}/exceptions",
    response_model=AssignmentExceptionRead,
    status_code=201,
)
def create_assignment_exception(
    assignment_id: str,
    body: AssignmentExceptionCreate,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    GAP 7: Employee requests an exception for a specific benefit on their assignment.
    Saves to `exception_requests` table with enriched fields.
    """
    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()
    actor_id = user.get("id", "")

    row = {
        "id": str(uuid.uuid4()),
        "assignment_id": assignment_id,
        "benefit_key": body.benefit_key,
        "type_label": body.type_label,
        "current_value": body.current_value,
        "requested_value": body.requested_value,
        "reason": body.reason,
        "status": "pending",
        "requested_by_user_id": actor_id,
        "audit_events": [
            {"ts": now, "actor": actor_id, "action": "created", "note": "Exception request submitted"}
        ],
        "created_at": now,
        "updated_at": now,
    }

    try:
        sb = _get_supabase()
        result = sb.table("exception_requests").insert(row).execute()
        if result and result.data:
            return result.data[0]
    except Exception:
        logger.exception("create_assignment_exception failed assignment_id=%s", assignment_id)
        raise HTTPException(status_code=500, detail="Failed to create exception request")

    return row


@router.patch(
    "/api/assignments/{assignment_id}/exceptions/{exception_id}",
    response_model=AssignmentExceptionRead,
)
def resolve_assignment_exception(
    assignment_id: str,
    exception_id: str,
    body: ExceptionRequestPatch,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    GAP 7: HR approves or rejects an assignment-level exception request.
    Appends an audit event and optionally saves an ai_insight note.
    """
    role = (user.get("role") or "").upper()
    if role not in ("HR", "ADMIN") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")

    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()
    actor_id = user.get("id", "")

    try:
        sb = _get_supabase()

        # Fetch existing
        result = (
            sb.table("exception_requests")
            .select("*")
            .eq("id", exception_id)
            .eq("assignment_id", assignment_id)
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            raise HTTPException(status_code=404, detail="Exception request not found")
        existing = result.data
        if existing.get("status") != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request is already {existing.get('status')}; cannot change.",
            )

        # Build audit trail
        audit_events = existing.get("audit_events") or []
        audit_events.append({
            "ts": now,
            "actor": actor_id,
            "action": body.status,  # "approved" or "rejected"
            "note": body.hr_note or "",
        })

        update_payload: Dict[str, Any] = {
            "status": body.status,
            "hr_note": body.hr_note,
            "resolved_by_user_id": actor_id,
            "resolved_at": now,
            "updated_at": now,
            "audit_events": audit_events,
        }
        if body.ai_insight:
            update_payload["ai_insight"] = body.ai_insight

        updated = (
            sb.table("exception_requests")
            .update(update_payload)
            .eq("id", exception_id)
            .execute()
        )
        if updated and updated.data:
            return updated.data[0]
    except HTTPException:
        raise
    except Exception:
        logger.exception("resolve_assignment_exception failed id=%s", exception_id)
        raise HTTPException(status_code=500, detail="Failed to update exception request")

    raise HTTPException(status_code=500, detail="Update returned no data")
