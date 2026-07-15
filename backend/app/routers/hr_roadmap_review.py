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
from sqlalchemy import func, text

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


def is_roadmap_pending_review(case_id: str) -> bool:
    """Is this roadmap still waiting on HR?

    FAILS OPEN — no review row, or a lookup error, means NOT pending. Same asymmetry as
    the read path: we only ever hold something back when we positively know HR withheld
    it. 47 live cases have a roadmap and no review row; a gate that guessed "pending"
    would lock every one of those employees out of their own tasks.
    """
    try:
        with SessionLocal() as db:
            row = db.get(RoadmapReviewStatus, case_id)
            if row is None:
                return False
            return not bool(row.released_to_user)
    except Exception as exc:  # noqa: BLE001
        log.warning("roadmap action gate: lookup failed for %s (%s); allowing", case_id, exc)
        return False


def assert_roadmap_released(case_id: str) -> None:
    """Block an EMPLOYEE action on a roadmap HR hasn't approved yet.

    The employee can freely READ their plan — exploring it is reassuring and costs
    nothing. What they cannot do is act on a plan that may still change: HR can send it
    back for regeneration, and work done against a superseded plan is wasted (or worse,
    wrong). So reads are open and writes wait.

    409 (not 403): this is a state conflict, not a permissions problem. The employee is
    entitled to act — just not yet.
    """
    if is_roadmap_pending_review(case_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "Your HR team is still reviewing this plan. You can explore it now — "
                "your tasks unlock once they approve it."
            ),
        )


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


# ── Ops metrics ──────────────────────────────────────────────────────────────────────

metrics_router = APIRouter(prefix="/api/admin/roadmap-review", tags=["hr-roadmap-review"])

_METRICS_SQL = text(
    """
    SELECT
      count(*) FILTER (WHERE released_to_user IS FALSE)                              AS pending_review,
      count(*) FILTER (WHERE released_to_user IS FALSE AND notified_at IS NOT NULL)  AS pending_and_notified,
      count(*) FILTER (WHERE notify_status = 'unreachable')                          AS unreachable,
      count(*) FILTER (WHERE notify_status IN ('failed', 'error'))                   AS undelivered,
      count(*) FILTER (WHERE notify_status = 'no_key')                               AS no_key,
      count(*) FILTER (WHERE notify_status = 'sent')                                 AS sent,
      EXTRACT(EPOCH FROM (now() - min(updated_at) FILTER (WHERE released_to_user IS FALSE))) / 3600.0
                                                                                     AS oldest_pending_age_hours
    FROM public.roadmap_review_status r
    -- Only real roadmaps. E2E tests leave orphan review rows behind (case purged, no
    -- FK), which would otherwise inflate pending_review. A real pending roadmap always
    -- has milestones; an orphan has none.
    WHERE EXISTS (SELECT 1 FROM public.case_milestones m WHERE m.case_id = r.case_id)
    """
)

_UNREACHABLE_SQL = text(
    """
    SELECT r.case_id FROM public.roadmap_review_status r
    WHERE r.notify_status = 'unreachable'
      AND EXISTS (SELECT 1 FROM public.case_milestones m WHERE m.case_id = r.case_id)
    ORDER BY r.updated_at DESC LIMIT 50
    """
)


class RoadmapReviewMetrics(BaseModel):
    pending_review: int = 0
    pending_and_notified: int = 0
    #: Cases where HR is waiting but was NEVER told — because no HR contact resolves at
    #: all. The employee is blocked and nobody knows. This is the number that must never
    #: be hidden: a silent skip looks exactly like a successful send.
    unreachable: int = 0
    unreachable_case_ids: list[str] = []
    #: Send attempted and failed. Not retried (instant-fire has no sweep) — but visible.
    undelivered: int = 0
    no_key: int = 0
    sent: int = 0
    oldest_pending_age_hours: Optional[float] = None
    #: pending_review - pending_and_notified: HR is waiting and has NOT been told.
    pending_unnotified: int = 0


@metrics_router.get("/metrics", response_model=RoadmapReviewMetrics)
def roadmap_review_metrics(
    _admin: Dict[str, Any] = Depends(require_admin_or_hr),
) -> RoadmapReviewMetrics:
    """Does the HR-notification actually work? These are the numbers that answer it."""
    with SessionLocal() as db:
        row = db.execute(_METRICS_SQL).fetchone()
        unreachable_ids = [str(r[0]) for r in db.execute(_UNREACHABLE_SQL).fetchall()]

    m = row._mapping if row else {}
    pending = int(m.get("pending_review") or 0)
    notified = int(m.get("pending_and_notified") or 0)
    age = m.get("oldest_pending_age_hours")
    return RoadmapReviewMetrics(
        pending_review=pending,
        pending_and_notified=notified,
        pending_unnotified=max(0, pending - notified),
        unreachable=int(m.get("unreachable") or 0),
        unreachable_case_ids=unreachable_ids,
        undelivered=int(m.get("undelivered") or 0),
        no_key=int(m.get("no_key") or 0),
        sent=int(m.get("sent") or 0),
        oldest_pending_age_hours=round(float(age), 1) if age is not None else None,
    )


@metrics_router.post("/notify/{case_id}")
def trigger_notification(
    case_id: str,
    dry_run: bool = False,
    to_override: Optional[str] = None,
    _admin: Dict[str, Any] = Depends(require_admin_or_hr),
) -> Dict[str, Any]:
    """Manually (re-)run the HR notification for a case.

    `dry_run=true` resolves the recipient and renders the email without sending — the way
    to verify the wiring in production without mailing a real person. Mirrors the
    dry_run/to_override escape hatches on the HR mobility briefing cron.
    """
    from ..services.roadmap_review_notification import notify_hr_roadmap_pending

    return notify_hr_roadmap_pending(case_id, dry_run=dry_run, to_override=to_override)
