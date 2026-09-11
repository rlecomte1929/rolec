"""
Expense claims — employee reimbursement ledger drawing down against policy caps.

[AIQ-2271]
  POST   /api/cases/{case_id}/expense-claims   — employee (or HR) creates
  GET    /api/cases/{case_id}/expense-claims   — case-scoped list
  PATCH  /api/expense-claims/{id}              — submit (employee) / resolve (HR)

Tenant isolation: every query is scoped by company_id. FX is snapshotted on
submit and never recomputed live.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

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
from ..services.fx_service import convert_with_snapshot

router = APIRouter(tags=["expense_claims"])
logger = logging.getLogger(__name__)

CREATE_STATUSES = ("draft", "submitted")
HR_RESOLVE_STATUSES = ("approved", "rejected", "paid")
NOTIFICATION_TYPE_SUBMITTED = "EXPENSE_CLAIM_SUBMITTED"
NOTIFICATION_TYPE_DECIDED = "EXPENSE_CLAIM_DECIDED"


class ExpenseClaimLineIn(BaseModel):
    benefit_key: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    cap_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    receipt_ocr_id: Optional[str] = Field(None, max_length=80)
    vendor_name: Optional[str] = Field(None, max_length=200)
    expense_date: Optional[str] = Field(None, max_length=10)


class ExpenseClaimCreate(BaseModel):
    status: Literal["draft", "submitted"] = "submitted"
    lines: List[ExpenseClaimLineIn] = Field(..., min_length=1)
    hr_note: Optional[str] = Field(None, max_length=2000)


class ExpenseClaimPatch(BaseModel):
    status: Literal["submitted", "approved", "rejected", "paid"]
    hr_note: Optional[str] = Field(None, max_length=2000)


class ExpenseClaimLineRead(BaseModel):
    id: str
    benefit_key: str
    amount: float
    currency: str
    cap_currency: Optional[str] = None
    fx_rate_to_cap: Optional[float] = None
    fx_rate_date: Optional[str] = None
    amount_in_cap_currency: Optional[float] = None
    receipt_ocr_id: Optional[str] = None
    vendor_name: Optional[str] = None
    expense_date: Optional[str] = None


class ExpenseClaimRead(BaseModel):
    id: str
    case_id: str
    company_id: str
    employee_user_id: Optional[str] = None
    status: str
    hr_note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by_user_id: Optional[str] = None
    lines: List[ExpenseClaimLineRead] = []


def _canonical_case_id(case_id: str) -> str:
    """AIQ-1704: path may carry assignment id; ledger is keyed on canonical case id."""
    ids = db.resolve_case_ids(case_id)
    if ids is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return ids.canonical_case_id


def _caller_company_id(user: Dict[str, Any]) -> str:
    uid = user.get("id")
    profile = db.get_profile_record(uid) if uid else None
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id and uid:
        try:
            company_id = db.get_hr_company_id(uid)
        except Exception:
            logger.debug("expense_claims: hr_users lookup failed", exc_info=True)
    if not company_id and uid:
        try:
            assignment = db.get_assignment_for_employee(uid, request_id=None)
            if assignment:
                company_id = db.get_company_id_for_assignment_id(str(assignment.get("id")))
        except Exception:
            logger.debug("expense_claims: assignment lookup failed", exc_info=True)
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile — expense claims need a tenant.",
        )
    return str(company_id)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
        elif isinstance(v, uuid.UUID):
            d[k] = str(v)
    return d


def _audit(*, claim_id: str, action: str, actor_id: str, new_value: Optional[Dict[str, Any]] = None) -> None:
    try:
        insert_audit_log(
            entity_type="expense_claims",
            entity_id=claim_id,
            action_type=action,
            actor_type=ACTOR_HUMAN,
            actor_id=actor_id,
            new_value=new_value,
        )
    except Exception:
        logger.exception("expense_claims: audit insert failed id=%s", claim_id)


def _notify_hr_submitted(case_id: str, claim_id: str) -> None:
    try:
        assignment = db.get_assignment_by_case_id(case_id) or {}
        hr_user_id = assignment.get("hr_user_id")
        if not hr_user_id:
            return
        db.create_notification_with_preferences(
            user_id=str(hr_user_id),
            type_=NOTIFICATION_TYPE_SUBMITTED,
            title="Expense claim submitted",
            body="An employee submitted an expense claim for review.",
            data={"case_id": case_id, "claim_id": claim_id},
        )
        from ..services.notification_outbox_dispatch import dispatch_outbox_soon
        dispatch_outbox_soon()
    except Exception as exc:
        logger.warning(
            "expense_claims: HR notify failed id=%s error=%s", claim_id, str(exc), exc_info=True
        )


def _notify_employee_decision(employee_user_id: Optional[str], claim_id: str, status: str) -> None:
    if not employee_user_id:
        return
    try:
        db.create_notification_with_preferences(
            user_id=str(employee_user_id),
            type_=NOTIFICATION_TYPE_DECIDED,
            title="Expense claim updated",
            body=f"Your expense claim was marked {status}.",
            data={"claim_id": claim_id, "status": status},
        )
        from ..services.notification_outbox_dispatch import dispatch_outbox_soon
        dispatch_outbox_soon()
    except Exception as exc:
        logger.warning(
            "expense_claims: employee notify failed id=%s error=%s", claim_id, str(exc), exc_info=True
        )


def _snapshot_line(conn: Any, line: ExpenseClaimLineIn) -> Dict[str, Any]:
    cap_ccy = (line.cap_currency or line.currency).upper()
    amount_in_cap, rate, as_of = convert_with_snapshot(
        line.amount, line.currency.upper(), cap_ccy, conn
    )
    return {
        "cap_currency": cap_ccy,
        "fx_rate_to_cap": rate,
        "fx_rate_date": as_of.isoformat() if as_of else None,
        "amount_in_cap_currency": amount_in_cap,
    }


def _insert_lines(conn: Any, claim_id: str, lines: List[ExpenseClaimLineIn], snapshot: bool) -> None:
    for line in lines:
        fx = _snapshot_line(conn, line) if snapshot else {
            "cap_currency": (line.cap_currency or line.currency).upper(),
            "fx_rate_to_cap": 1.0 if (line.cap_currency or line.currency).upper() == line.currency.upper() else None,
            "fx_rate_date": None,
            "amount_in_cap_currency": line.amount if (line.cap_currency or line.currency).upper() == line.currency.upper() else None,
        }
        conn.execute(
            text(
                """
                INSERT INTO expense_claim_lines (
                    id, claim_id, benefit_key, amount, currency, cap_currency,
                    fx_rate_to_cap, fx_rate_date, amount_in_cap_currency,
                    receipt_ocr_id, vendor_name, expense_date
                ) VALUES (
                    :id, :claim_id, :benefit_key, :amount, :currency, :cap_currency,
                    :fx_rate_to_cap, :fx_rate_date, :amount_in_cap_currency,
                    :receipt_ocr_id, :vendor_name, :expense_date
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "claim_id": claim_id,
                "benefit_key": line.benefit_key,
                "amount": line.amount,
                "currency": line.currency.upper(),
                "cap_currency": fx["cap_currency"],
                "fx_rate_to_cap": fx["fx_rate_to_cap"],
                "fx_rate_date": fx["fx_rate_date"],
                "amount_in_cap_currency": fx["amount_in_cap_currency"],
                "receipt_ocr_id": line.receipt_ocr_id,
                "vendor_name": line.vendor_name,
                "expense_date": line.expense_date,
            },
        )


def _load_claim(conn: Any, claim_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text("SELECT * FROM expense_claims WHERE id = :id AND company_id = :org"),
        {"id": claim_id, "org": company_id},
    ).mappings().first()
    if not row:
        return None
    claim = _row_to_dict(row)
    lines = conn.execute(
        text("SELECT * FROM expense_claim_lines WHERE claim_id = :id ORDER BY created_at"),
        {"id": claim_id},
    ).mappings().all()
    claim["lines"] = [_row_to_dict(l) for l in lines]
    return claim


def _snapshot_existing_lines(conn: Any, claim_id: str) -> None:
    lines = conn.execute(
        text("SELECT * FROM expense_claim_lines WHERE claim_id = :id"),
        {"id": claim_id},
    ).mappings().all()
    for line in lines:
        from_ccy = str(line["currency"])
        to_ccy = str(line.get("cap_currency") or from_ccy)
        amount_in_cap, rate, as_of = convert_with_snapshot(
            float(line["amount"]), from_ccy, to_ccy, conn
        )
        conn.execute(
            text(
                """
                UPDATE expense_claim_lines
                SET fx_rate_to_cap = :rate, fx_rate_date = :d,
                    amount_in_cap_currency = :amt, cap_currency = :cap
                WHERE id = :id
                """
            ),
            {
                "rate": rate,
                "d": as_of.isoformat() if as_of else None,
                "amt": amount_in_cap,
                "cap": to_ccy.upper(),
                "id": str(line["id"]),
            },
        )


@router.post(
    "/api/cases/{case_id}/expense-claims",
    response_model=ExpenseClaimRead,
    status_code=201,
)
def create_expense_claim(
    case_id: str,
    body: ExpenseClaimCreate,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    company_id = _caller_company_id(user)
    require_case_access(case_id, user)
    case_id = _canonical_case_id(case_id)
    if body.status not in CREATE_STATUSES:
        raise HTTPException(status_code=400, detail="status must be draft or submitted")
    actor_id = user["id"]
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    submitted_at = now if body.status == "submitted" else None

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO expense_claims (
                    id, case_id, company_id, employee_user_id, status,
                    hr_note, created_at, updated_at, submitted_at
                ) VALUES (
                    :id, :case_id, :org, :actor, :status,
                    :hr_note, :now, :now, :submitted_at
                )
                """
            ),
            {
                "id": new_id,
                "case_id": case_id,
                "org": company_id,
                "actor": actor_id,
                "status": body.status,
                "hr_note": body.hr_note,
                "now": now,
                "submitted_at": submitted_at,
            },
        )
        _insert_lines(conn, new_id, body.lines, snapshot=body.status == "submitted")
        claim = _load_claim(conn, new_id, company_id)

    _audit(
        claim_id=new_id,
        action=ACTION_INSERT,
        actor_id=actor_id,
        new_value={"case_id": case_id, "company_id": company_id, "status": body.status},
    )
    if body.status == "submitted":
        _notify_hr_submitted(case_id, new_id)
    return claim or {}


@router.get(
    "/api/cases/{case_id}/expense-claims",
    response_model=List[ExpenseClaimRead],
)
def list_expense_claims_for_case(
    case_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> List[Dict[str, Any]]:
    company_id = _caller_company_id(user)
    require_case_access(case_id, user)
    case_id = _canonical_case_id(case_id)
    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT * FROM expense_claims WHERE case_id = :case_id AND company_id = :org "
                "ORDER BY created_at DESC"
            ),
            {"case_id": case_id, "org": company_id},
        ).mappings().all()
        out = []
        for row in rows:
            claim = _row_to_dict(row)
            lines = conn.execute(
                text("SELECT * FROM expense_claim_lines WHERE claim_id = :id ORDER BY created_at"),
                {"id": claim["id"]},
            ).mappings().all()
            claim["lines"] = [_row_to_dict(l) for l in lines]
            out.append(claim)
    return out


@router.patch(
    "/api/expense-claims/{claim_id}",
    response_model=ExpenseClaimRead,
)
def patch_expense_claim(
    claim_id: str,
    body: ExpenseClaimPatch,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    company_id = _caller_company_id(user)
    role = (user.get("role") or "").upper()
    is_hr = role in ("HR", "ADMIN") or bool(user.get("is_admin"))
    actor_id = user["id"]
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        existing = conn.execute(
            text("SELECT * FROM expense_claims WHERE id = :id"),
            {"id": claim_id},
        ).mappings().first()
        if not existing:
            raise HTTPException(status_code=404, detail="Expense claim not found")
        if str(existing["company_id"]) != str(company_id):
            raise HTTPException(status_code=403, detail="Not authorised for this claim")

        current = str(existing["status"])
        if body.status == "submitted":
            if current != "draft":
                raise HTTPException(status_code=409, detail=f"Claim is {current}; cannot submit.")
            if str(existing.get("employee_user_id") or "") != str(actor_id) and not is_hr:
                raise HTTPException(status_code=403, detail="Not authorised for this claim")
            _snapshot_existing_lines(conn, claim_id)
            conn.execute(
                text(
                    "UPDATE expense_claims SET status = 'submitted', submitted_at = :now, "
                    "updated_at = :now WHERE id = :id AND company_id = :org"
                ),
                {"now": now, "id": claim_id, "org": company_id},
            )
        elif body.status in HR_RESOLVE_STATUSES:
            if not is_hr:
                raise HTTPException(status_code=403, detail="HR or Admin only")
            if current not in ("submitted", "approved"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Claim is {current}; cannot mark {body.status}.",
                )
            if body.status == "paid" and current not in ("approved", "paid"):
                raise HTTPException(status_code=409, detail="Claim must be approved before paid.")
            conn.execute(
                text(
                    """
                    UPDATE expense_claims
                    SET status = :status, hr_note = COALESCE(:hr_note, hr_note),
                        resolved_at = :now, resolved_by_user_id = :actor, updated_at = :now
                    WHERE id = :id AND company_id = :org
                    """
                ),
                {
                    "status": body.status,
                    "hr_note": body.hr_note,
                    "now": now,
                    "actor": actor_id,
                    "id": claim_id,
                    "org": company_id,
                },
            )
        else:
            raise HTTPException(status_code=400, detail="unsupported status")

        claim = _load_claim(conn, claim_id, company_id)

    _audit(
        claim_id=claim_id,
        action=ACTION_UPDATE,
        actor_id=actor_id,
        new_value={"status": body.status},
    )
    if body.status == "submitted":
        _notify_hr_submitted(str(existing["case_id"]), claim_id)
    elif body.status in HR_RESOLVE_STATUSES:
        _notify_employee_decision(existing.get("employee_user_id"), claim_id, body.status)
    return claim or {}
