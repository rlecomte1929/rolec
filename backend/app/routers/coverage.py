"""
Coverage dashboard endpoint (admin-only).

GET /api/admin/coverage — one aggregated per-destination coverage payload:
immigration facts (approved / pending / rejected) plus provider capabilities per
service category (live / total). Cached in-process; pass ``?refresh=true`` to
force a live recompute against the current database.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import require_admin
from ..services.coverage_service import get_coverage_summary

router = APIRouter(prefix="/api/admin", tags=["admin-coverage"])


@router.get("/coverage")
def get_coverage(
    refresh: bool = False,
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    return get_coverage_summary(refresh=refresh)
