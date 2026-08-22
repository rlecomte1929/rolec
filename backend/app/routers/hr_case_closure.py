"""[AIQ-2088] HR case closure — the end of the relocation lifecycle.

THE GAP THIS FILLS
------------------
`AssignmentStatus.CLOSED` has existed and been permitted by the
`case_assignments_status_check` constraint since the canonical lifecycle landed, and
**nothing HR can reach has ever written it**. Measured on production 2026-08-22:

    case_assignments   1,418 rows
        submitted        838     assigned    523
        awaiting_intake   55     approved      2
        rejected           0     closed        0   <-- never, not once

The only writer was `PATCH /api/admin/assignments/{id}/status` (ADMIN-only), and
`POST /api/hr/assignments/{id}/decision` hard-rejects anything that is not
approved/rejected. So an HR user could create a relocation, run it, and never end it:
every case they opened stayed open forever from their side, with no completion, no
time-to-completion, and nothing to report to the business.

WHAT `closed` MEANS (decision, Romain, 2026-08-22)
--------------------------------------------------
`closed` is TERMINAL: the relocation is over. `approved` is MID-lifecycle — it is
granted when HR reviews the employee's *submitted intake* (see the `assignment.approved`
event in `hr_decision`), which happens weeks before anyone moves.

The codebase disagreed with itself on this and the disagreement is what made the card a
decision rather than a task:

    frontend caseStatusLabel.ts        approved='Complete', closed='Canceled'
    case_duration_model.py:94          terminal = completed|closed|done|archived
    hr_mobility_briefing_service.py:51 terminal = submitted|approved|rejected|...

The first is now corrected to 'Approved' / 'Closed' alongside this router.

WARN, NEVER BLOCK (decision, Romain, 2026-08-22)
------------------------------------------------
Closure surfaces what is still outstanding and lets HR close anyway, recording what was
outstanding in the audit event. HR knows things the system does not — the employee left,
the move was cancelled, the vendor was paid offline. Refusing closure on system state is
how you get cases that can never be closed, which is the defect being fixed.

No new column, and therefore no migration: `status` carries the terminal state and the
`assignment.closed` event carries the reason and the outstanding snapshot. CI blocks a PR
that adds a column and reads it in the same merge (`check_column_read_before_apply.py`,
written after a 2h33m production 500), so avoiding one keeps this shippable in one merge.

Registered in BOTH backend/app/main.py and backend/main.py (prod boots backend.main:app).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ...database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr", tags=["hr-case-closure"])

CLOSED = "closed"
CLOSE_EVENT = "assignment.closed"


class CloseBody(BaseModel):
    """`reason` is optional but strongly encouraged — it is the only thing that
    distinguishes a completed move from an abandoned one, since no outcome column
    exists (see the module docstring)."""

    reason: Optional[str] = Field(default=None, max_length=1000)


class Outstanding(BaseModel):
    open_rfqs: int = 0
    incomplete_milestones: int = 0


class ClosureReadiness(BaseModel):
    assignment_id: str
    status: Optional[str] = None
    already_closed: bool = False
    outstanding: Outstanding = Outstanding()


class CloseResult(BaseModel):
    assignment_id: str
    status: str
    already_closed: bool
    outstanding_at_close: Outstanding = Outstanding()


def _require_assignment_access(assignment_id: str, org_id: str) -> Dict[str, Any]:
    """Load the assignment and prove the caller's org owns its case.

    404 (never 403) on a tenant mismatch, matching `hr_case_detail._require_case_access`:
    a different status code would let an attacker probe which ids belong to other tenants.
    """
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    case_id = assignment.get("case_id")
    case = db.get_relocation_case(case_id) if case_id else None
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    case_company_id = case.get("company_id")
    if case_company_id and str(case_company_id) != str(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


_OUTSTANDING_SQL = """
SELECT
  (SELECT count(*) FROM rfqs r
    WHERE r.case_id = :case_id
      AND COALESCE(r.status, '') NOT IN ('accepted', 'cancelled', 'closed', 'declined')
  ) AS open_rfqs,
  (SELECT count(*) FROM case_milestones m
    WHERE m.case_id = :case_id
      AND m.actual_date IS NULL
      AND COALESCE(m.status, '') NOT IN ('done', 'completed', 'not_applicable')
  ) AS incomplete_milestones
"""


def _outstanding_for_case(case_id: str) -> Outstanding:
    """What is still open on this case. Safe-fails to zeros.

    Degrading to zeros is deliberate: this only WARNS, so a query failure must not stop
    HR closing a case. It is logged, because a silently-empty warning is how a reviewer
    concludes there was nothing outstanding when nobody actually looked.
    """
    if not case_id:
        return Outstanding()
    try:
        with db.engine.connect() as conn:
            row = conn.execute(text(_OUTSTANDING_SQL), {"case_id": case_id}).mappings().first()
        if not row:
            return Outstanding()
        return Outstanding(
            open_rfqs=int(row.get("open_rfqs") or 0),
            incomplete_milestones=int(row.get("incomplete_milestones") or 0),
        )
    except Exception:  # noqa: BLE001 — warn-only; never block closure on a query error
        logger.exception("hr_case_closure: outstanding query failed for case %s", case_id)
        return Outstanding()


@router.get("/assignments/{assignment_id}/closure-readiness", response_model=ClosureReadiness)
def get_closure_readiness(
    assignment_id: str,
    _hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> ClosureReadiness:
    """What HR should see before they close: current status and what is still open.

    Nothing here can refuse a closure — it exists so the confirmation dialog can say
    "3 milestones are still open" rather than closing silently.
    """
    assignment = _require_assignment_access(assignment_id, org_id)
    current = str(assignment.get("status") or "")
    return ClosureReadiness(
        assignment_id=assignment_id,
        status=current or None,
        already_closed=current == CLOSED,
        outstanding=_outstanding_for_case(str(assignment.get("case_id") or "")),
    )


@router.post("/assignments/{assignment_id}/close", response_model=CloseResult)
def close_assignment(
    assignment_id: str,
    body: CloseBody,
    hr_user: Dict[str, Any] = Depends(require_admin_or_hr),
    org_id: str = Depends(get_org_id_for_hr_user),
) -> CloseResult:
    """End the relocation. Terminal, tenant-scoped, idempotent, audited.

    Closable from ANY non-closed state — deliberately. Requiring `approved` first would
    make closure unreachable for 99.8% of production cases (2 of 1,418 are approved), and
    an abandoned move never reaches approval at all.
    """
    assignment = _require_assignment_access(assignment_id, org_id)
    case_id = str(assignment.get("case_id") or "")
    current = str(assignment.get("status") or "")

    if current == CLOSED:
        # Idempotent: a second close is a no-op and must NOT write a second audit event,
        # or the timeline gains a closure that never happened.
        return CloseResult(
            assignment_id=assignment_id,
            status=CLOSED,
            already_closed=True,
            outstanding_at_close=Outstanding(),
        )

    outstanding = _outstanding_for_case(case_id)
    db.update_assignment_status(assignment_id, CLOSED)

    try:
        db.insert_case_event(
            case_id=case_id,
            assignment_id=assignment_id,
            actor_principal_id=hr_user.get("id"),
            event_type=CLOSE_EVENT,
            payload={
                "reason": body.reason,
                "previous_status": current or None,
                # The warn-don't-block record: what was still open at the moment HR
                # closed. Without this, "why was this closed with 3 open milestones?"
                # is unanswerable six months later.
                "outstanding": outstanding.model_dump(),
            },
        )
    except Exception:  # noqa: BLE001
        # The status write already succeeded. Log loudly rather than raising: failing here
        # would tell HR the close failed while the case is, in fact, closed.
        logger.exception(
            "hr_case_closure: close event insert failed assignment=%s case=%s",
            assignment_id, case_id,
        )

    return CloseResult(
        assignment_id=assignment_id,
        status=CLOSED,
        already_closed=False,
        outstanding_at_close=outstanding,
    )
