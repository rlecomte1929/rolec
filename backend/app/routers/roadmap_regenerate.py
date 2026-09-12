"""Recompute a case's roadmap from the current generator.

    POST /api/hr/cases/{case_id}/roadmap/regenerate            — apply
    POST /api/hr/cases/{case_id}/roadmap/regenerate?dry_run=1  — preview, writes nothing

WHY. Milestones are written once, at case creation/submit. #1938 added the corridor overlay
(the ES→IE CSEP journey), so every case created before it keeps the generic pack — Andrea's
6ecadafe has 16 `task_*` rows and 0 corridor steps. There was no way to re-run generation for
an existing case; this is it.

Admin/HR only (`require_admin_or_hr`). This rewrites what the employee is told to do, so it
is not an employee-triggerable action.

It does NOT touch `roadmap_review_status`. An absent row there means RELEASED (see
hr_roadmap_review.py), so writing to it here could publish an unreviewed roadmap or retract a
released one. Regenerating the STEPS and deciding whether HR has approved them are separate
decisions, and this endpoint only makes the first.

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md 405 rule).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth_deps import require_admin_or_hr
from ..services.case_service import resolve_case_forms_case_id
from ..services.roadmap_regeneration_service import regenerate_case_milestones

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr/cases", tags=["roadmap-regenerate"])


class RegenerateResponse(BaseModel):
    case_id: str
    applied: bool
    inserted: int
    updated: int
    deleted: int
    # Rows the generator no longer emits that were kept anyway: completed/in-progress work,
    # and service-owned rows. Named so an operator can see WHY the old list did not vanish.
    kept_protected: List[str] = []
    no_change: bool


@router.post("/{case_id}/roadmap/regenerate", response_model=RegenerateResponse)
def regenerate_roadmap(
    case_id: str,
    dry_run: bool = Query(False, description="Compute the plan and return it without writing."),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> RegenerateResponse:
    from backend.database import db  # imported here to match the legacy DB seam

    # [ANDREA-P1 / AIQ-1776 class] HR pages navigate with the ASSIGNMENT id, but
    # ``case_milestones`` and the relocation-plan view are keyed by the canonical case id.
    # Regenerating on the raw path param wrote 16 milestones under the assignment id that
    # no reader ever loaded (the employee plan stayed at 0 tasks). Key on the resolved id.
    case_id = resolve_case_forms_case_id(case_id)

    try:
        plan = regenerate_case_milestones(db, case_id, apply=not dry_run)
    except Exception:
        log.exception("roadmap regenerate failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to regenerate the roadmap.")

    summary = plan.summary()
    return RegenerateResponse(
        case_id=case_id,
        applied=not dry_run,
        inserted=summary["inserted"],
        updated=summary["updated"],
        deleted=summary["deleted"],
        kept_protected=plan.kept_protected,
        no_change=plan.is_noop,
    )
