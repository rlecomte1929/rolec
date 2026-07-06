"""Admin Autopilot metrics — funnel + cost dashboard backend (Feedback Autopilot Phase 4).

Admin-only JSON the AdminAutopilotMetricsPage reads: the ingest→dispatch→fix→merge→done funnel
(from public.events autopilot.* stages) plus month-to-date autopilot spend vs the monthly cap.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_admin
from ..services import autopilot_metrics

router = APIRouter(prefix="/api/admin", tags=["admin-autopilot-metrics"])


@router.get("/autopilot-metrics")
def autopilot_metrics_rollup(
    since: Optional[str] = Query(None, description="Inclusive ISO-8601 lower bound on created_at"),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Autopilot funnel counts, dedup ratio, per-stage cost + KPIs. Near-empty until the
    automation is enabled — proving the dashboard reads the live pipeline."""
    return autopilot_metrics.compute_autopilot_metrics(since=since)
