"""
Immigration partner status-sync service (AIQ-379d).

Maps a ``CaseStatus`` (from a ``PartnerAdapter`` — mock today, live via AIQ-379e)
onto rows in ``immigration_milestones`` so a partner's permit-lifecycle status
shows up on the existing HR case timeline.

Design choices (see docs/design/aiq-379-mcp-tunnel-partner-api.md §4):
  * Idempotent **manual upsert** keyed on (case_id, milestone_type) — no unique
    constraint, so no schema migration. Re-running with identical status is a
    no-op (no writes, no audit).
  * One audit row per **status transition** (new milestone, or a status change),
    written via ``audit_log_service``. The ``audit_logs.action_type`` CHECK only
    allows insert/update/delete, so the semantic event name lives in
    ``new_value.event`` — never in ``action_type``.
  * Writes use the backend connection (service_role in prod); the existing
    GET /api/hr/cases/{case_id}/immigration/milestones endpoint reads them back,
    so no new route and no dual-registration is needed.

Bare table names (``immigration_milestones``, ``audit_logs``) resolve to the
``public`` schema in prod and keep the SQLite unit tests working — same pattern
as ``audit_log_service``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ...database import db
from .audit_log_service import ACTOR_SERVICE, insert_audit_log
from .immigration_partner_adapter import CaseStatus, PartnerAdapter
from .immigration_partner_factory import get_partner_adapter
from .immigration_service import _now_iso


@dataclass
class SyncResult:
    """Outcome counters for one sync pass — handy for logging and tests."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    audited: int = 0


def _date_str(value: Any) -> Optional[str]:
    """Normalise a date/datetime (or already-string) to an ISO string for comparison."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def apply_case_status(
    conn: Connection,
    *,
    case_id: str,
    org_id: str,
    status: CaseStatus,
    actor_type: str = ACTOR_SERVICE,
) -> SyncResult:
    """Upsert every milestone in ``status`` into ``immigration_milestones``.

    Operates on the caller-supplied connection (the caller owns the transaction),
    mirroring ``audit_log_service`` so this is unit-testable on SQLite.
    """
    result = SyncResult()
    now = _now_iso()

    for m in status.milestones:
        incoming: Dict[str, Any] = {
            "status": m.status.value,
            "sort_order": m.sort_order,
            "target_date": _date_str(m.target_date),
            "completed_date": _date_str(m.completed_date),
            "notes": m.notes,
            "evidence_url": m.evidence_url,
        }

        existing = conn.execute(
            text(
                """
                SELECT id, status, sort_order, target_date, completed_date, notes, evidence_url
                FROM immigration_milestones
                WHERE case_id = :case_id AND milestone_type = :mt
                LIMIT 1
                """
            ),
            {"case_id": case_id, "mt": m.milestone_type.value},
        ).mappings().first()

        # ---- new milestone -------------------------------------------------
        if existing is None:
            ms_id = str(uuid.uuid4())
            conn.execute(
                text(
                    """
                    INSERT INTO immigration_milestones
                        (id, case_id, org_id, milestone_type, status, sort_order,
                         target_date, completed_date, notes, evidence_url,
                         created_at, updated_at)
                    VALUES
                        (:id, :case_id, :org_id, :mt, :status, :sort_order,
                         :target_date, :completed_date, :notes, :evidence_url,
                         :now, :now)
                    """
                ),
                {
                    "id": ms_id,
                    "case_id": case_id,
                    "org_id": org_id,
                    "mt": m.milestone_type.value,
                    "now": now,
                    **incoming,
                },
            )
            insert_audit_log(
                conn,
                entity_type="immigration_milestone",
                entity_id=ms_id,
                action_type="insert",
                new_value={
                    "event": "partner_milestone_synced",
                    "source": "immigration_partner_sync",
                    "case_id": case_id,
                    "milestone_type": m.milestone_type.value,
                    "status": incoming["status"],
                },
                actor_type=actor_type,
            )
            result.created += 1
            result.audited += 1
            continue

        # ---- existing milestone -------------------------------------------
        old = dict(existing)
        old_norm = {
            "status": old["status"],
            "sort_order": old["sort_order"],
            "target_date": _date_str(old["target_date"]),
            "completed_date": _date_str(old["completed_date"]),
            "notes": old["notes"],
            "evidence_url": old["evidence_url"],
        }

        if old_norm == incoming:
            result.unchanged += 1
            continue

        conn.execute(
            text(
                """
                UPDATE immigration_milestones
                SET status = :status, sort_order = :sort_order,
                    target_date = :target_date, completed_date = :completed_date,
                    notes = :notes, evidence_url = :evidence_url, updated_at = :now
                WHERE id = :id
                """
            ),
            {**incoming, "now": now, "id": old["id"]},
        )
        result.updated += 1

        # Audit only on a real status transition (not a notes/date-only edit).
        if old_norm["status"] != incoming["status"]:
            insert_audit_log(
                conn,
                entity_type="immigration_milestone",
                entity_id=old["id"],
                action_type="update",
                old_value={"status": old_norm["status"]},
                new_value={
                    "event": "partner_milestone_status_changed",
                    "source": "immigration_partner_sync",
                    "case_id": case_id,
                    "milestone_type": m.milestone_type.value,
                    "status": incoming["status"],
                },
                actor_type=actor_type,
            )
            result.audited += 1

    return result


def sync_case(
    case_id: str,
    org_id: str,
    partner_ref: str,
    adapter: Optional[PartnerAdapter] = None,
) -> SyncResult:
    """Pull a partner's current status and upsert it into ``immigration_milestones``.

    Resolves the adapter via the feature-flag factory unless one is injected.
    Opens its own transaction on the backend engine.
    """
    adapter = adapter or get_partner_adapter()
    status = adapter.get_case_status(partner_ref)
    with db.engine.begin() as conn:
        return apply_case_status(conn, case_id=case_id, org_id=org_id, status=status)
