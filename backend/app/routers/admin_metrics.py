"""
Admin KPI summary endpoint (admin-only) — AIQ-2326 / ADMIN-IA-0a.

GET /api/admin/metrics/summary — one payload with every admin KPI, each carrying an
explicit definition + source + as-of timestamp. All admin surfaces read from here so a
metric means the same thing on every page (see admin_metrics_service for the rationale).
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import require_admin
from ..services.admin_metrics_service import build_metrics_summary

router = APIRouter(prefix="/api/admin", tags=["admin-metrics"])


@router.get("/metrics/summary")
def get_metrics_summary(_admin: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    return build_metrics_summary()
