"""
Admin RAG-quality dashboard — P3-01e.

Exposes the time-series of the three P3-01 RAG evaluation metrics (context
precision, factual consistency, outcome accuracy) plus per-metric threshold-alert
state, for the admin RAG-quality dashboard at ``/admin/rag-quality``.

Read-only; sources committed eval-report JSON under ``audit/rag_eval/`` and falls
back to a flagged mock series until real reports land. See
``services.rag_eval_reports`` for the data model.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import require_admin
from ..services import rag_eval_reports

router = APIRouter(prefix="/api/admin", tags=["admin-rag-eval"])
logger = logging.getLogger(__name__)


@router.get("/rag-eval/metrics")
def rag_eval_metrics(
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Per-metric time-series + threshold-alert state for the RAG-quality dashboard.

    Returns ``{source, metrics: [{metric, label, threshold, points, latest, alert}]}``
    where ``source`` is ``"live"`` when real eval reports exist on disk, else
    ``"mock"`` (a deterministic flagged series so the dashboard renders pre-launch).
    """
    return rag_eval_reports.build_dashboard()
