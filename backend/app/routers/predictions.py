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
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..auth_deps import get_current_user, require_case_access
from ..db import SessionLocal

router = APIRouter(prefix="/api/cases", tags=["predictions"])
logger = logging.getLogger(__name__)


def _predictions_enabled() -> bool:
    return os.getenv("PREDICTIONS_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


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
