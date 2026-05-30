"""
Admin AI unit-economics rollup — Parker Step G.

Exposes per-customer / per-feature AI cost + carbon telemetry as an admin-only JSON
rollup. The admin panel that consumes this is deferred to a follow-up prompt
(prompts/followups/G-frontend.md); this is the backend surface it will read.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_admin
from ..services import ai_unit_economics

router = APIRouter(prefix="/api/admin", tags=["admin-ai-unit-economics"])
logger = logging.getLogger(__name__)


@router.get("/ai-unit-economics")
def ai_unit_economics_rollup(
    customer_id: Optional[str] = Query(None),
    feature_key: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None, alias="to"),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Aggregate AI cost + carbon per (customer, feature) over an optional date range.

    ``from`` / ``to`` are ISO-8601 timestamps (inclusive). ``customer_id`` /
    ``feature_key`` narrow to a single customer / feature. Returns per-bucket rows and
    grand totals (cost USD, tokens, estimated gCO₂e, call count). Empty range → zeroed.
    """
    return ai_unit_economics.compute_unit_economics_rollup(
        customer_id=customer_id,
        feature_key=feature_key,
        from_ts=from_,
        to_ts=to,
    )
