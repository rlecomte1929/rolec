"""
Employee immigration snapshot route (relocation-assistant Slice 2).

GET /api/employee/cases/{case_id}/immigration-snapshot — the proactive "your move
at a glance" payload (risk flags + checklist summary) for the employee's OWN case.
These signals exist today only behind the HR-only immigration panel; this exposes
them to the relocating employee, scoped to their own case.

Auth: require_hr_or_employee + require_case_access (employee's own assignment, or
HR visibility) — mirrors the relocation-plan-view ownership model. No body case_id;
the path id is authorized before anything is computed.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_case_access, require_hr_or_employee
from ..services.immigration_snapshot_service import build_immigration_snapshot

router = APIRouter(prefix="/api/employee", tags=["employee-immigration"])


@router.get("/cases/{case_id}/immigration-snapshot")
def get_immigration_snapshot(
    case_id: str,
    # [AIQ-1833] No default. Resolved from the destination in the service, so an
    # Ireland or Denmark case is never told it needs an EU Blue Card.
    visa_type: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
) -> Dict[str, Any]:
    # Enforce ownership BEFORE computing anything (fail-closed on cross-case access).
    require_case_access(case_id, user)
    return build_immigration_snapshot(case_id, visa_type=visa_type)
