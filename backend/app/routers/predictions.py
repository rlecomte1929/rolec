"""Predictive analytics routes (Parker-A).

GET /api/cases/{case_id}/predicted-duration — Cox survival estimate of the days
remaining until a relocation case closes.

Canary kill-switch: the whole feature is gated behind PREDICTIONS_ENABLED
(default false). When disabled the route 404s, so it can be dark-shipped and
ramped per environment.

Heavy ML imports live in case_duration_model and are deferred to inside the
handler — importing this router never requires lifelines/pandas to be installed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_current_user, require_case_access
from ..db import SessionLocal
from ..services.feature_flags import resolve_flag_safe

router = APIRouter(prefix="/api/cases", tags=["predictions"])
logger = logging.getLogger(__name__)


# DB feature-flag row → env var (PREDICTIONS_ENABLED) → default OFF. Routing
# through resolve_flag_safe lets an admin toggle this from /admin/feature-flags
# without a redeploy; the env var still works as a fallback.
def _predictions_enabled() -> bool:
    return resolve_flag_safe("PREDICTIONS_ENABLED", env_default=False)


def _processing_time_enabled() -> bool:
    return resolve_flag_safe("PROCESSING_TIME_ENABLED", env_default=False)


@router.get("/{case_id}/predicted-duration")
def get_predicted_duration(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return {median_days, p20_days, p80_days, model_version, n_training_cases}.

    404 when the canary flag is off or no trained model exists. Ownership is
    enforced: the caller must own the case (employee), be its HR contact, or be
    an admin.
    """
    if not _predictions_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    # Ownership / tenant gate (employee-owner, HR-of-company, or admin).
    require_case_access(case_id, user)

    # Deferred import keeps lifelines/pandas off the module-load path.
    from ..services.case_duration_model import (
        InsufficientDataError,
        load_active_model,
        predict_remaining_duration,
    )

    with SessionLocal() as session:
        model = load_active_model(session)
        if model is None:
            raise HTTPException(status_code=404, detail="No prediction model available")
        try:
            return predict_remaining_duration(model, case_id, session)
        except InsufficientDataError:
            raise HTTPException(status_code=404, detail="Case not found")


@router.get("/{case_id}/processing-time")
def get_processing_time(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return {p50_days, p90_days, source, sample_size, last_updated, source_url}.

    Corridor-level processing-time estimate for a case (P2-04). Empirical p50/p90
    from completed platform cases once a corridor has >= 20 of them, otherwise the
    official statutory range with a citation. 404 when the canary flag is off, the
    case is unknown, or no source is available (the UI then renders nothing — never
    a processing time without a source). Same ownership gate as predicted-duration.
    """
    if not _processing_time_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    require_case_access(case_id, user)

    from ..services.processing_time_estimate import estimate_for_case

    with SessionLocal() as session:
        estimate = estimate_for_case(session, case_id)
        if estimate is None:
            raise HTTPException(status_code=404, detail="No processing-time estimate available")
        return dict(estimate)
