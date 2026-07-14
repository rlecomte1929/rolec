"""HR validates the roadmap before the employee acts on it.

Today the EMPLOYEE self-validates ("Validate & start tasks") and HR merely receives a
notification after the fact. The intended flow is the other way round:

    intake -> roadmap generated -> HR reviews and approves -> employee acknowledges -> tasks start

This adds the missing gate. It does NOT invent a store: `roadmap_review_status`
(case_id, released_to_user, regeneration_requested, reviewer_id, notes) already exists
and already carries exactly this state — it was simply admin-only, written by the
specialist-review surface (`specialist_review.py`) and read by
`roadmap_confidence_gate.py`. This exposes it to HR.

    GET  /api/hr/cases/{case_id}/roadmap-review          — current status
    POST /api/hr/cases/{case_id}/roadmap-review/approve  — release it to the employee
    POST /api/hr/cases/{case_id}/roadmap-review/request-changes — send it back, with a reason

FAIL-OPEN ON A MISSING ROW. 47 cases already have a roadmap and none has a review row.
Treating "no row" as "not released" would yank the roadmap out from under every one of
them the moment this ships. So an absent row means RELEASED, new roadmaps get a row
(released=false) at generation time, and the existing cases are backfilled explicitly.
An employee never loses their plan to a bug in a gate.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from ..auth_deps import require_admin_or_hr
from ..db import SessionLocal
from ..models import RoadmapReviewStatus

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr/cases", tags=["hr-roadmap-review"])


class RoadmapReviewDTO(BaseModel):
    case_id: str
    # An absent row is treated as released — see the module docstring. The employee
    # never loses a roadmap they already had.
    released_to_user: bool = True
    regeneration_requested: bool = False
    reviewer_id: Optional[str] = None
    notes: Optional[str] = None
    reviewed: bool = False  # False when no HR decision has ever been recorded


class RequestChangesBody(BaseModel):
    notes: str


def _to_dto(case_id: str, row: Optional[RoadmapReviewStatus]) -> RoadmapReviewDTO:
    if row is None:
        return RoadmapReviewDTO(case_id=case_id, released_to_user=True, reviewed=False)
    return RoadmapReviewDTO(
        case_id=case_id,
        released_to_user=bool(row.released_to_user),
        regeneration_requested=bool(row.regeneration_requested),
        reviewer_id=row.reviewer_id,
        notes=row.notes,
        reviewed=True,
    )


def _load_or_create(db, case_id: str) -> RoadmapReviewStatus:
    row = db.get(RoadmapReviewStatus, case_id)
    if row is None:
        row = RoadmapReviewStatus(case_id=case_id)
        db.add(row)
    return row


@router.get("/{case_id}/roadmap-review", response_model=RoadmapReviewDTO)
def get_roadmap_review(
    case_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> RoadmapReviewDTO:
    with SessionLocal() as db:
        return _to_dto(case_id, db.get(RoadmapReviewStatus, case_id))


@router.post("/{case_id}/roadmap-review/approve", response_model=RoadmapReviewDTO)
def approve_roadmap(
    case_id: str,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> RoadmapReviewDTO:
    """Release the roadmap to the employee. Idempotent."""
    reviewer_id = str(hr_user.get("id") or "")
    with SessionLocal() as db:
        row = _load_or_create(db, case_id)
        row.released_to_user = True
        row.regeneration_requested = False
        row.reviewer_id = reviewer_id
        row.updated_at = func.now()
        db.commit()
        db.refresh(row)
        dto = _to_dto(case_id, row)

    _invalidate(case_id)
    log.info("hr roadmap review: case %s released by %s", case_id, reviewer_id)
    return dto


@router.post("/{case_id}/roadmap-review/request-changes", response_model=RoadmapReviewDTO)
def request_changes(
    case_id: str,
    body: RequestChangesBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> RoadmapReviewDTO:
    """Send the roadmap back. The employee keeps seeing "HR is reviewing your plan" —
    they are never shown a plan HR has rejected, and never shown nothing at all."""
    notes = (body.notes or "").strip()
    if not notes:
        # A rejection with no reason is indistinguishable from a bug, and leaves the
        # employee waiting on something nobody can act on.
        raise HTTPException(status_code=422, detail="A reason is required when requesting changes.")

    reviewer_id = str(hr_user.get("id") or "")
    with SessionLocal() as db:
        row = _load_or_create(db, case_id)
        row.released_to_user = False
        row.regeneration_requested = True
        row.reviewer_id = reviewer_id
        row.notes = notes
        row.updated_at = func.now()
        db.commit()
        db.refresh(row)
        dto = _to_dto(case_id, row)

    _invalidate(case_id)
    log.info("hr roadmap review: case %s sent back by %s", case_id, reviewer_id)
    return dto


def _invalidate(case_id: str) -> None:
    """The plan view is cached; a review decision must be visible immediately."""
    try:
        from ..services.relocation_plan_view_service import invalidate_relocation_plan_cache

        invalidate_relocation_plan_cache(case_id)
    except Exception as exc:  # noqa: BLE001 — a stale cache must not fail the decision
        log.warning("hr roadmap review: cache invalidation failed for %s: %s", case_id, exc)
