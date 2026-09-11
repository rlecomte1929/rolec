"""GET /api/hr/duty-of-care — company-scoped R/A/G compliance board (AIQ-2268).

Company id comes from ``get_org_id_for_hr_user`` only. An unresolved company
returns an empty board, not 500. Dual-register this router in both mains.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth_deps import get_org_id_for_hr_user
from ..db import SessionLocal
from ..services.duty_of_care_service import list_duty_of_care_board

router = APIRouter(prefix="/api/hr", tags=["hr-duty-of-care"])


class DutyOfCareCase(BaseModel):
    case_id: str
    company_id: Optional[str] = None
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    host_country: Optional[str] = None
    home_country: Optional[str] = None
    expected_start_date: Optional[str] = None
    departing_soon: bool
    overall: str
    permit: Dict[str, Any]
    alert: Dict[str, Any]
    checklist: Dict[str, Any]
    a1: Dict[str, Any]
    medical: Dict[str, Any]
    insurance: Dict[str, Any]


class DutyOfCareResponse(BaseModel):
    cases: List[DutyOfCareCase]


@router.get("/duty-of-care", response_model=DutyOfCareResponse)
def get_duty_of_care(
    company_id: str = Depends(get_org_id_for_hr_user),
) -> DutyOfCareResponse:
    if not company_id:
        return DutyOfCareResponse(cases=[])
    with SessionLocal() as db:
        rows = list_duty_of_care_board(db, company_id)
    return DutyOfCareResponse(cases=[DutyOfCareCase(**row) for row in rows])
