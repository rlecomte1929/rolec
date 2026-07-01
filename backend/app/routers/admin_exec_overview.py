"""
Executive dashboard endpoint (admin-only).

GET /api/admin/exec-overview — one aggregated "state of the platform" payload
(growth, activation funnel, throughput, AI cost, AI health + honest reliability/NPS
placeholders). Each panel soft-fails independently, so the dashboard never 500s.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import require_admin
from ..services.exec_overview_service import build_exec_overview

router = APIRouter(prefix="/api/admin", tags=["admin-exec"])


@router.get("/exec-overview")
def get_exec_overview(window_days: int = 30, _admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return build_exec_overview(window_days=window_days)
