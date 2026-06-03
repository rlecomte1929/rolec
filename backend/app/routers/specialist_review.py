"""
Specialist Review API — admin-only endpoints for AI roadmap step review.

GET  /api/internal/specialist-review/{case_id}   — fetch AI roadmap steps for review
POST /api/internal/specialist-review/submit       — write review events + flip release/regen flags
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import RoadmapReviewStatus, SpecialistReviewEvent

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/specialist-review", tags=["specialist-review"])


class ReviewItem(BaseModel):
    step_id: str
    decision: Literal["approve", "reject", "edit"]
    reason_code: Optional[Literal["WRONG_PATHWAY", "OUTDATED_RULE", "MISSING_DEPENDENCY", "INCORRECT_FORM"]] = None
    original_step: Dict[str, Any]
    edited_step: Optional[Dict[str, Any]] = None


class SubmitBody(BaseModel):
    case_id: str
    decision: Literal["approved", "rejected"]
    notes: Optional[str] = None
    items: List[ReviewItem]


@router.get("/{case_id}")
def get_roadmap(case_id: str, user: Dict[str, Any] = Depends(require_admin)):
    # TODO(P1-01): wire real AI step source — currently derives from case draft shape.
    # derive_roadmap expects a full wizard case dict (with a "draft" key containing
    # relocationBasics, familyMembers, assignmentContext etc.).  Calling it with only
    # {"case_id": case_id} would succeed but return a minimal roadmap (no dest/family
    # context), so we wrap defensively and fall back to an empty steps list on any error.
    try:
        from ..services.roadmap_builder import derive_roadmap  # local import avoids cycle
        derived = derive_roadmap({"case_id": case_id})
        raw_steps = derived.get("steps", []) if isinstance(derived, dict) else []
        # Normalise each step: guarantee step_id and title.
        # roadmap_builder steps use "key" as the stable identifier, not "step_id".
        steps = []
        for idx, step in enumerate(raw_steps):
            steps.append({
                **step,
                "step_id": step.get("step_id") or step.get("key") or f"{case_id}-{idx}",
                "title": step.get("title", ""),
            })
    except Exception:
        log.exception("specialist-review GET: derive_roadmap failed for case_id=%s", case_id)
        steps = []  # TODO(P1-01)
    return {"case_id": case_id, "steps": steps}


@router.post("/submit")
def submit_review(body: SubmitBody, user: Dict[str, Any] = Depends(require_admin)):
    reviewer_id = str(user.get("id", ""))
    any_reject = any(it.decision == "reject" for it in body.items)
    all_approve = len(body.items) > 0 and all(it.decision == "approve" for it in body.items)
    released = body.decision == "approved" and all_approve and not any_reject
    regen = body.decision == "rejected" or any_reject

    with SessionLocal() as db:
        for it in body.items:
            db.add(
                SpecialistReviewEvent(
                    id=str(uuid.uuid4()),
                    case_id=body.case_id,
                    step_id=it.step_id,
                    reviewer_id=reviewer_id,
                    action=it.decision,
                    reason_code=it.reason_code,
                    original_step_json=json.dumps(it.original_step),
                    edited_step_json=json.dumps(it.edited_step) if it.edited_step else None,
                )
            )
        status = db.get(RoadmapReviewStatus, body.case_id)
        if status is None:
            status = RoadmapReviewStatus(case_id=body.case_id)
            db.add(status)
        status.released_to_user = released
        status.regeneration_requested = regen
        status.reviewer_id = reviewer_id
        status.notes = body.notes
        status.updated_at = func.now()
        db.commit()

    return {"released_to_user": released, "regeneration_requested": regen}
