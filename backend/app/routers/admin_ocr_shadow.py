"""
Admin OCR shadow-comparison rollup — Parker Step F.

Exposes the GPT-4o-vs-OSS passport-OCR shadow telemetry as an admin-only JSON
rollup. The dashboard UI that consumes this is a deferred follow-up; this is the
backend surface it will read.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_admin
from ..services import passport_ocr_oss

router = APIRouter(prefix="/api/admin", tags=["admin-ocr-shadow"])
logger = logging.getLogger(__name__)


@router.get("/ocr-shadow-comparison")
def ocr_shadow_comparison(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None, alias="to"),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Aggregate passport-OCR shadow comparisons over an optional date range.

    ``from`` / ``to`` are ISO-8601 timestamps (inclusive). Returns per-field
    agreement rate, MRZ-pass rate per pipeline, and average/total cost per
    pipeline. Empty range → zeroed rollup.
    """
    return passport_ocr_oss.compute_shadow_rollup(from_ts=from_, to_ts=to)
