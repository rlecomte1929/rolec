"""Standing destination-immigration authority link (IDR-260820-28EC).

GET /api/employee/immigration-authority/{country_code}

Auth: HR or employee (same gate as the Relocation Assistant). Country ISO-2 is
not PII. Returns `{authority: null}` rather than 404 when nothing is curated —
the UI renders nothing in that case.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import require_hr_or_employee
from ..db import SessionLocal
from ..services.destination_immigration_authority import lookup_destination_immigration_authority

router = APIRouter(prefix="/api/employee", tags=["employee-immigration"])


@router.get("/immigration-authority/{country_code}")
def get_destination_immigration_authority(
    country_code: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    del user  # auth gate only
    with SessionLocal() as session:
        return {"authority": lookup_destination_immigration_authority(session, country_code)}
