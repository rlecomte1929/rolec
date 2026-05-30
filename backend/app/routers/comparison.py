"""
[AIQ-236 / P3-1] GET /api/comparison/{employee_id}

Returns one ComparisonResult per relevant benefit category, computed from
the employee's currently-active tier and their selected services. See
`backend/app/services/comparison_engine.py` for the core logic.

Auth model
──────────
- The employee themselves can read their own row.
- HR / admin can read any employee inside the same company.
- Everyone else → 403 (not 200 with `[]`, per the task spec).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from ...database import db
from ...schemas import UserRole
from ..auth_deps import get_current_user
from ..schemas_comparison import ComparisonResult
from ..services.comparison_engine import (
    NoActiveTierError,
    NoPublishedPolicyError,
    compute_comparison,
)


router = APIRouter(prefix="/api/comparison", tags=["comparison"])
logger = logging.getLogger(__name__)


def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def _fetch_profile(employee_id: str) -> Dict[str, Any]:
    """Return {id, company_id, role} for the target employee, or 404."""
    with db.engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT id, company_id, role FROM {_t('profiles')} "
                f"WHERE id = :id"
            ),
            {"id": employee_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")
    return dict(row)


def _authorize(caller: Dict[str, Any], target_profile: Dict[str, Any]) -> None:
    """
    Enforce the access model. Raises 403 on denial — never returns an empty
    payload (per the AIQ-236 spec, wrong-tier callers must see a hard 403).
    """
    caller_id = str(caller.get("id") or "")
    caller_role = (caller.get("role") or "").lower()
    caller_company = str(caller.get("company") or caller.get("company_id") or "")
    target_id = str(target_profile.get("id") or "")
    target_company = str(target_profile.get("company_id") or "")

    if caller.get("is_admin"):
        return

    if caller_role == UserRole.EMPLOYEE.value.lower():
        if caller_id == target_id:
            return
        raise HTTPException(
            status_code=403,
            detail="Employees can only read their own comparison.",
        )

    if caller_role == UserRole.HR.value.lower():
        # HR may be missing JWT.company; fall back to DB lookup.
        if not caller_company:
            caller_company = db.get_hr_company_id(caller_id) or ""
        if caller_company and caller_company == target_company:
            return
        raise HTTPException(
            status_code=403,
            detail="HR may only read employees in their own company.",
        )

    raise HTTPException(status_code=403, detail="Not authorized for comparison.")


@router.get("/{employee_id}", response_model=List[ComparisonResult])
def get_employee_comparison(
    employee_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[ComparisonResult]:
    """Compute and return the comparison rows for the given employee."""
    target = _fetch_profile(employee_id)
    _authorize(user, target)

    try:
        return compute_comparison(db, employee_id)
    except NoActiveTierError:
        # 404 because the data the caller asked for doesn't exist yet —
        # distinct from 403 (you can't see it) and 409 (server-side conflict).
        raise HTTPException(
            status_code=404,
            detail="Employee has no active tier assignment.",
        )
    except NoPublishedPolicyError:
        # 409 — the request is well-formed but the company hasn't published
        # a policy version yet, so there's nothing to compare against.
        raise HTTPException(
            status_code=409,
            detail="Employee's company has no published policy version.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "comparison_engine failed employee_id=%s", employee_id,
        )
        raise HTTPException(status_code=500, detail="Failed to compute comparison")
