"""
B16 — vendor-curation widget aliases at the /api/hr prefix.

The vendor curation widget and the E2E runner (T11_WIDGET) call:
  GET /api/hr/vendor-assignments/pending
  GET /api/hr/employees/waiting

The underlying logic already lives in hr_catalog.py but is only exposed under
the /api/hr/catalog prefix. These thin aliases expose the same data at the
paths the frontend and E2E runner expect, without duplicating the SQL.

Note: /employees/waiting must resolve before the monolith's
/api/hr/employees/{employee_id} route — this router is registered ahead of that
@app.get in backend/main.py, so the static path matches first.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import require_admin_or_hr
from .hr_catalog import (
    list_pending_vendor_assignments,
    employees_waiting_count,
)

router = APIRouter(prefix="/api/hr", tags=["hr-vendor-assignments"])


@router.get("/vendor-assignments/pending")
def vendor_assignments_pending(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Alias for GET /api/hr/catalog/vendor-assignments/pending (B16)."""
    return list_pending_vendor_assignments(user)


@router.get("/employees/waiting")
def employees_waiting(
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Alias for GET /api/hr/catalog/employees/waiting (B16)."""
    return employees_waiting_count(user)
