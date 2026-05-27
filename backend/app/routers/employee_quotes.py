"""
Quote requests — employee requests vendor quotes, HR reviews them.

This is Step 4 of the employee 5-step workflow.

Endpoints:
  POST  /api/employee/quote-requests        — employee submits a request
  GET   /api/employee/quote-requests        — employee lists their own requests
  GET   /api/hr/quote-requests              — HR lists all pending requests for company
  PATCH /api/hr/quote-requests/{id}         — HR acknowledges or fulfils a request
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
from ...schemas import UserRole

router = APIRouter(tags=["quote_requests"])
logger = logging.getLogger(__name__)

VALID_STATUSES = ("pending", "acknowledged", "fulfilled")
SERVICE_CATEGORIES = [
    "Housing search",
    "Immigration/visa",
    "Moving & shipping",
    "School search",
    "Destination orientation",
    "Other",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QuoteRequestCreate(BaseModel):
    case_id: str = Field(..., min_length=1)
    service_categories: List[str] = Field(..., min_items=1)
    notes: Optional[str] = Field(None, max_length=2000)
    budget_range: Optional[str] = Field(None, max_length=100)


class QuoteRequestPatch(BaseModel):
    status: str = Field(..., pattern=r"^(acknowledged|fulfilled)$")


class QuoteRequestRead(BaseModel):
    id: str
    case_id: str
    employee_id: str
    company_id: str
    service_categories: List[str]
    notes: Optional[str]
    budget_range: Optional[str]
    status: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _caller_company_id(user: Dict[str, Any]) -> str:
    """Resolve the caller's company_id; 403 if missing."""
    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="No company linked to this profile.",
        )
    return company_id


def _row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
        # Postgres returns text[] as a Python list already; SQLite stores as
        # comma-separated text — normalise both to list.
        if k == "service_categories":
            if isinstance(v, str):
                d[k] = [s.strip() for s in v.split(",") if s.strip()]
            elif v is None:
                d[k] = []
    return d


def _require_employee(user: Dict[str, Any]) -> Dict[str, Any]:
    role = (user.get("role") or "").upper()
    if role == UserRole.EMPLOYEE.value:
        return user
    # Admin impersonating employee is OK; pure HR should not submit quotes
    if user.get("impersonation"):
        return user
    raise HTTPException(status_code=403, detail="Employee only")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/api/employee/quote-requests",
    response_model=QuoteRequestRead,
    status_code=201,
)
def create_quote_request(
    body: QuoteRequestCreate,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Employee submits a vendor quote request for their relocation case.
    """
    _require_employee(user)
    company_id = _caller_company_id(user)
    employee_id = user["id"]
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Normalise categories: join for SQLite compat, Postgres can store array
    cats_serialised = "{" + ",".join(f'"{c}"' for c in body.service_categories) + "}"

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO quote_requests
                    (id, case_id, employee_id, company_id,
                     service_categories, notes, budget_range,
                     status, created_at, updated_at)
                VALUES
                    (:id, :case_id, :emp, :company,
                     :cats::text[], :notes, :budget,
                     'pending', :now, :now)
                """
            ),
            {
                "id": new_id,
                "case_id": body.case_id,
                "emp": employee_id,
                "company": company_id,
                "cats": cats_serialised,
                "notes": body.notes,
                "budget": body.budget_range,
                "now": now,
            },
        )
        row = conn.execute(
            text("SELECT * FROM quote_requests WHERE id = :id"),
            {"id": new_id},
        ).mappings().first()

    return _row_to_dict(row)


@router.get(
    "/api/employee/quote-requests",
    response_model=List[QuoteRequestRead],
)
def list_employee_quote_requests(
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Employee lists their own submitted quote requests.
    """
    _require_employee(user)
    employee_id = user["id"]

    with db.engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT * FROM quote_requests
                WHERE employee_id = :emp
                ORDER BY created_at DESC
                """
            ),
            {"emp": employee_id},
        ).mappings().all()

    return [_row_to_dict(r) for r in rows]


@router.get(
    "/api/hr/quote-requests",
    response_model=List[QuoteRequestRead],
)
def list_hr_quote_requests(
    status: Optional[str] = None,
    case_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    HR lists all quote requests from employees in their company.
    Optional ?status=pending|acknowledged|fulfilled and ?case_id= filters.
    """
    role = (user.get("role") or "").upper()
    if role not in (UserRole.HR.value, UserRole.ADMIN.value) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")

    company_id = _caller_company_id(user)

    conditions = ["company_id = :company"]
    params: Dict[str, Any] = {"company": company_id}

    if status:
        conditions.append("status = :status")
        params["status"] = status
    if case_id:
        conditions.append("case_id = :case_id")
        params["case_id"] = case_id

    where_clause = " AND ".join(conditions)

    with db.engine.begin() as conn:
        rows = conn.execute(
            text(f"SELECT * FROM quote_requests WHERE {where_clause} ORDER BY created_at DESC"),
            params,
        ).mappings().all()

    return [_row_to_dict(r) for r in rows]


@router.patch(
    "/api/hr/quote-requests/{request_id}",
    response_model=QuoteRequestRead,
)
def update_quote_request_status(
    request_id: str,
    body: QuoteRequestPatch,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    HR marks a quote request as acknowledged or fulfilled.
    """
    role = (user.get("role") or "").upper()
    if role not in (UserRole.HR.value, UserRole.ADMIN.value) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")

    company_id = _caller_company_id(user)
    now = datetime.utcnow().isoformat()

    with db.engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT * FROM quote_requests WHERE id = :id AND company_id = :company"
            ),
            {"id": request_id, "company": company_id},
        ).mappings().first()

        if not existing:
            raise HTTPException(status_code=404, detail="Quote request not found")

        conn.execute(
            text(
                """
                UPDATE quote_requests
                SET status = :status, updated_at = :now
                WHERE id = :id
                """
            ),
            {"status": body.status, "now": now, "id": request_id},
        )
        row = conn.execute(
            text("SELECT * FROM quote_requests WHERE id = :id"),
            {"id": request_id},
        ).mappings().first()

    return _row_to_dict(row)


@router.get("/api/hr/service-categories")
def list_service_categories(
    _user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """
    Return the available service category options for the quote request form.
    """
    return {"service_categories": SERVICE_CATEGORIES}


# ---------------------------------------------------------------------------
# Destination Request — employee requests an unsupported relocation destination
# ---------------------------------------------------------------------------

class EmployeeDestinationRequestCreate(BaseModel):
    city: str = Field(..., min_length=1, max_length=200, description="Destination city name")
    country: str = Field(..., min_length=1, max_length=200, description="Destination country name")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional context or reason for the request")


@router.post("/api/employee/destination-request", status_code=201)
def submit_destination_request(
    body: EmployeeDestinationRequestCreate,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    """
    Employee (or HR on behalf of an employee) requests a destination that is not
    yet in the supported destination list.  The request lands in the HR dashboard
    for the employee's company.  HR can then approve or reject it via
    PATCH /api/hr/catalog/destination-requests/{id}.

    Deduplication: if a pending request already exists for the same
    (city, country, company), the existing ticket is returned instead of
    creating a duplicate.

    B24-REGRESSION: profile-lookup and the scrape_safety insert are wrapped so
    a transient DB error produces a logged traceback + 502 instead of an opaque
    500 (T6/T15/T16 E2E persona scenarios).
    """
    from ..services import scrape_safety

    user_id = user.get("id")
    try:
        profile = db.get_profile_record(user_id)
    except Exception:
        logger.exception("destination-request: profile lookup failed user_id=%s", user_id)
        raise HTTPException(
            status_code=502,
            detail="Profile lookup failed while creating destination request.",
        )

    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        raise HTTPException(status_code=403, detail="No company linked to this account.")

    try:
        ticket = scrape_safety.open_destination_request(
            city=body.city,
            country=body.country,
            category="Relocation destination",
            requested_by_user_id=str(user_id),
            company_id=str(company_id),
            notes=body.notes,
        )
    except ValueError as ve:
        # open_destination_request raises ValueError on bad input
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception:
        logger.exception(
            "destination-request: open_destination_request failed user_id=%s city=%s country=%s",
            user_id, body.city, body.country,
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to record destination request.",
        )
    return ticket


@router.get("/api/employee/destination-requests")
def list_employee_destination_requests(
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> List[Dict[str, Any]]:
    """
    Employee lists their own pending destination requests so they can track status.
    """
    from ..services import scrape_safety

    profile = db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company")
    if not company_id:
        return []

    all_reqs = scrape_safety.list_destination_requests(company_id=str(company_id), limit=200)
    # Filter to requests opened by this user (employees only see their own)
    role = (user.get("role") or "").upper()
    if role == UserRole.EMPLOYEE.value:
        return [r for r in all_reqs if r.get("requested_by") == str(user["id"])]
    return all_reqs
