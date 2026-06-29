"""Case rule-update notifications API (P2-02e / AIQ-693).

Employee/case-scoped endpoints powering the in-app "Rule updated — please review"
roadmap banner:

  GET  /api/cases/{case_id}/rule-updates                       — active updates
  POST /api/cases/{case_id}/rule-updates/{id}/dismiss          — dismiss one

Auth mirrors the other case-scoped reads in cases_read: get_current_user +
_assert_case_access (employee owns the case; HR/admin same company). Registered
in BOTH backend/main.py and backend/app/main.py per the CLAUDE.md dual-mount rule.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_current_user
from ..db import engine
from ..services.case_rule_update_service import (
    dismiss_rule_update,
    list_active_rule_updates,
)
from ..services.case_service import _assert_case_access

router = APIRouter(prefix="/api/cases", tags=["case-rule-updates"])


@router.get("/{case_id}/rule-updates")
def get_rule_updates(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _assert_case_access(user, case_id)
    with engine.connect() as conn:
        items = list_active_rule_updates(conn, case_id)
    return {"items": items, "count": len(items)}


@router.post("/{case_id}/rule-updates/{notification_id}/dismiss")
def post_dismiss_rule_update(
    case_id: str,
    notification_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _assert_case_access(user, case_id)
    try:
        with engine.begin() as conn:
            return dismiss_rule_update(conn, case_id, notification_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
