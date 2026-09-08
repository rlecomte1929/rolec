"""Per-case completion state for the Visa Checklist.

Thin layer over `public.case_requirement_checklist_state` (migration
20261105000000). Deliberately raw SQL with no ORM model, matching the closest
analogues in this codebase — `service_catalog.py` and `vendor_curation.py`, whose
tables also have no model.

WHY NO MODEL. A model is a second declaration of the same table, and when the two
disagree the tests cannot see it: `Base.metadata.create_all` renders the model, so the
fixture always agrees with the model that drew it. That is exactly how #1864 shipped —
the migration said `id uuid`, the model said `Column(String)`, every test passed and
production 500'd on the first multi-row insert. No model, no divergence.

CONTENT VS STATE. This module owns only "has this case completed this requirement".
The requirements themselves come from `requirements_builder.compute_case_requirements`,
the same source the public corridor endpoint uses. Nothing here duplicates requirement
text, and nothing here decides which requirements apply.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text

from ... import db_config
from ...database import db

log = logging.getLogger(__name__)

# Postgres wants an explicit cast for a uuid column bound from a Python str; SQLite has no
# uuid type and rejects the CAST. Same switch test_drive.py uses for funnel_events.
_IS_SQLITE = (db_config.DATABASE_URL or "").startswith("sqlite")
_CASE = ":case_id" if _IS_SQLITE else "CAST(:case_id AS uuid)"
_ACTOR = ":actor_id" if _IS_SQLITE else "CAST(:actor_id AS uuid)"
_ID = ":id" if _IS_SQLITE else "CAST(:id AS uuid)"


def _row_to_state(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k in ("completed_by",):
        if d.get(k) is not None:
            d[k] = str(d[k])
    for k in ("completed_at",):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:  # noqa: BLE001
                d[k] = str(v)
    d["completed"] = bool(d.get("completed"))
    return d


def get_state(case_id: str) -> Dict[str, Dict[str, Any]]:
    """Completion state for one case, keyed by `requirement_id`.

    A requirement with no row has never been touched; callers treat that as not completed.
    Absence is the default rather than a seeded `false` row, so the table only ever holds
    decisions somebody actually made.
    """
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT requirement_id, completed, completed_by, completed_at "
                f"FROM case_requirement_checklist_state WHERE case_id = {_CASE}"
            ),
            {"case_id": str(case_id)},
        ).mappings().all()
    return {r["requirement_id"]: _row_to_state(r) for r in rows}


def set_state(
    *,
    case_id: str,
    requirement_id: str,
    completed: bool,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Upsert one requirement's completion state. Idempotent on (case_id, requirement_id).

    `completed_at` / `completed_by` are stamped when ticking and CLEARED when unticking, so
    a row can never claim it was completed by someone at a time while reading `completed=false`.
    """
    now_fn = "CURRENT_TIMESTAMP" if _IS_SQLITE else "now()"
    stamp_at = now_fn if completed else "NULL"
    stamp_by = _ACTOR if (completed and actor_id) else "NULL"

    with db.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO case_requirement_checklist_state "
                f"(id, case_id, requirement_id, completed, completed_at, completed_by) "
                f"VALUES ({_ID}, {_CASE}, :requirement_id, :completed, {stamp_at}, {stamp_by}) "
                "ON CONFLICT (case_id, requirement_id) DO UPDATE SET "
                "completed = EXCLUDED.completed, "
                "completed_at = EXCLUDED.completed_at, "
                "completed_by = EXCLUDED.completed_by, "
                f"updated_at = {now_fn}"
            ),
            {
                "id": str(uuid.uuid4()),
                "case_id": str(case_id),
                "requirement_id": str(requirement_id),
                "completed": bool(completed),
                "actor_id": str(actor_id) if actor_id else None,
            },
        )
        row = conn.execute(
            text(
                "SELECT requirement_id, completed, completed_by, completed_at "
                f"FROM case_requirement_checklist_state "
                f"WHERE case_id = {_CASE} AND requirement_id = :requirement_id"
            ),
            {"case_id": str(case_id), "requirement_id": str(requirement_id)},
        ).mappings().first()
    return _row_to_state(row) if row else {
        "requirement_id": requirement_id, "completed": completed,
        "completed_at": None, "completed_by": None,
    }
