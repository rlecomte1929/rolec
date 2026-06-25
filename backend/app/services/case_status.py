"""Canonical case/assignment status normalization — single shared source.

Both the case LIST endpoint (`GET /api/employee/cases`, in backend/main.py) and the
case DETAIL endpoint (`GET /api/cases/{id}`, in app/routers/cases_read.py) must report
status derived from the SAME logic so they can never disagree. This module is that
single source; `backend/main.py` re-imports `normalize_status` / `_CANONICAL_STATUS_VALUES`
from here (it used to define them locally).
"""

from __future__ import annotations

import logging
from typing import Optional

from ...schemas import AssignmentStatus

log = logging.getLogger(__name__)

_CANONICAL_STATUS_VALUES = {s.value for s in AssignmentStatus}


def normalize_status(status: Optional[str]) -> str:
    """
    Normalize legacy / mixed-case status values to canonical Postgres values.

    Canonical statuses (and ONLY these) are:
      created | assigned | awaiting_intake | submitted | approved | rejected | closed

    - Accepts Optional[str] and returns one of the canonical strings.
    - Case-insensitive, trims whitespace.
    - Maps legacy values like DRAFT / IN_PROGRESS / EMPLOYEE_SUBMITTED / HR_APPROVED, etc.
    - Unknown or empty values fall back to 'created' (and are logged once).
    """
    if not status:
        return AssignmentStatus.CREATED.value

    raw = str(status).strip()
    if not raw:
        return AssignmentStatus.CREATED.value

    lower = raw.lower()
    upper = raw.upper()

    # Already canonical
    if lower in _CANONICAL_STATUS_VALUES:
        return lower

    legacy_map = {
        # Old uppercase workflow statuses
        "DRAFT": AssignmentStatus.AWAITING_INTAKE.value,
        "IN_PROGRESS": AssignmentStatus.ASSIGNED.value,
        "EMPLOYEE_SUBMITTED": AssignmentStatus.SUBMITTED.value,
        "PENDING_EMPLOYEE": AssignmentStatus.AWAITING_INTAKE.value,
        "SUBMITTED_TO_HR": AssignmentStatus.SUBMITTED.value,
        "HR_APPROVED": AssignmentStatus.APPROVED.value,
        "APPROVED": AssignmentStatus.APPROVED.value,
        "HR_REJECTED": AssignmentStatus.REJECTED.value,
        "REJECTED": AssignmentStatus.REJECTED.value,
        "DONE": AssignmentStatus.CLOSED.value,
        "CLOSED": AssignmentStatus.CLOSED.value,
        # Transitional / review states get folded into submitted
        "HR_REVIEW": AssignmentStatus.SUBMITTED.value,
        "CHANGES_REQUESTED": AssignmentStatus.AWAITING_INTAKE.value,
    }

    mapped = legacy_map.get(upper)
    if mapped:
        return mapped

    # Fallback: log once per distinct unknown value and return 'created'
    log.warning("Unknown assignment status '%s', normalizing to 'created'", raw)
    return AssignmentStatus.CREATED.value
