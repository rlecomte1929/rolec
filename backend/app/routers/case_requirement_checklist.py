"""Visa Checklist — the case cockpit's requirement checklist and its per-case state.

GET  /api/cases/{case_id}/requirements/checklist   — requirements + completion state
POST /api/cases/{case_id}/requirements/checklist   — tick / untick one requirement

ONE SOURCE OF REQUIREMENTS. The list comes from
`requirements_builder.compute_case_requirements`, which is what
`public_corridor.py` and `GET /api/cases/{id}/requirements` already use. This module adds
completion state on top and never re-queries `requirement_items` itself — a second query
would drift, which is the thing the brief was explicit about avoiding.

TENANT SCOPING. Every route resolves through `_assert_case_access`, which both authorises
the caller and returns the CANONICAL case id. All SQL keys on that return value, never on
the raw path param: the param is commonly an assignment id, and keying on it is how twelve
endpoints silently returned empty (AIQ-1775).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user
from ..services import case_requirement_checklist as checklist_store
from ..services.case_service import _assert_case_access
from ..services.requirements_builder import compute_case_requirements

router = APIRouter(prefix="/api/cases", tags=["cases"])
logger = logging.getLogger(__name__)


class ChecklistItem(BaseModel):
    id: str
    title: str
    pillar: str
    description: str = ""
    severity: Optional[str] = None
    owner: Optional[str] = None
    # Carried through from the requirement so the checklist can show WHY an item is
    # unexpected and WHEN it is due — the two fields that make this more than a to-do list.
    nonObvious: Optional[bool] = None
    timing: Optional[str] = None
    completed: bool = False
    completedAt: Optional[str] = None


class ChecklistView(BaseModel):
    caseId: str
    destCountry: str
    purpose: str
    # False when the destination resolves to no catalogue. Distinct from an empty list,
    # which means "we checked and nothing applies" — collapsing them is the AIQ-1473c bug.
    covered: bool = True
    items: List[ChecklistItem]
    completedCount: int
    totalCount: int
    percentComplete: int


class ChecklistToggle(BaseModel):
    requirement_id: str = Field(..., min_length=1, max_length=200)
    completed: bool


def _build_view(case_id: str) -> ChecklistView:
    """Merge the computed requirements with this case's stored completion state."""
    computed = compute_case_requirements(case_id)
    state = checklist_store.get_state(case_id)

    items: List[ChecklistItem] = []
    for req in computed.requirements:
        stored = state.get(str(req.id)) or {}
        items.append(
            ChecklistItem(
                id=str(req.id),
                title=req.title,
                pillar=req.pillar,
                description=getattr(req, "description", "") or "",
                severity=getattr(req, "severity", None),
                owner=getattr(req, "owner", None),
                nonObvious=getattr(req, "nonObvious", None),
                timing=getattr(req, "timing", None),
                completed=bool(stored.get("completed")),
                completedAt=stored.get("completed_at"),
            )
        )

    total = len(items)
    done = sum(1 for i in items if i.completed)
    return ChecklistView(
        caseId=str(computed.caseId),
        destCountry=computed.destCountry,
        purpose=computed.purpose,
        covered=bool(getattr(computed, "covered", True)),
        items=items,
        completedCount=done,
        totalCount=total,
        # Integer percent; 0 when there is nothing to complete, never a division by zero.
        percentComplete=int(round(done * 100 / total)) if total else 0,
    )


@router.get("/{case_id}/requirements/checklist", response_model=ChecklistView)
def get_checklist(case_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> ChecklistView:
    resolved_case_id = _assert_case_access(user, case_id)
    try:
        return _build_view(resolved_case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.post("/{case_id}/requirements/checklist", response_model=ChecklistView)
def set_checklist_item(
    case_id: str,
    body: ChecklistToggle,
    user: Dict[str, Any] = Depends(get_current_user),
) -> ChecklistView:
    """Tick or untick one requirement, then return the whole refreshed view.

    Returning the view rather than the single row keeps the client's progress counter
    honest without a second round trip, and means two HR users toggling concurrently both
    see the true total rather than their own optimistic guess.
    """
    resolved_case_id = _assert_case_access(user, case_id)

    # Only a requirement that genuinely belongs to this case may be written. Without this a
    # caller could persist state against an arbitrary id — harmless-looking, but it would
    # let the table accumulate rows the checklist can never show or clear.
    try:
        view = _build_view(resolved_case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found")
    if not any(i.id == body.requirement_id for i in view.items):
        raise HTTPException(
            status_code=404,
            detail="That requirement is not part of this case's checklist.",
        )

    checklist_store.set_state(
        case_id=resolved_case_id,
        requirement_id=body.requirement_id,
        completed=body.completed,
        actor_id=user.get("id"),
    )
    return _build_view(resolved_case_id)
