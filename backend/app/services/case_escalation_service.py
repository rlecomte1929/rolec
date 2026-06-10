"""
W2-3 (HR-MVP): HR case escalation service.

Create / list / resolve escalations against the case_escalations table
(migration 20260620130000). Tenant-scoped by company_id at the app layer (in
addition to RLS). Audit-logged best-effort. Dialect-aware so it tests on SQLite
and runs on Postgres.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal
from .audit_log_service import ACTOR_HUMAN, insert_audit_log

log = logging.getLogger(__name__)

VALID_KINDS = {"specialist", "legal", "other"}


def _as_uuid(value: Any) -> Optional[str]:
    """audit_logs.actor_id is a uuid column — legacy text ids must become NULL."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for k in ("sla_due_at", "resolved_at", "created_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


def _audit(db, *, entity_id: str, action_type: str, new_value: Dict[str, Any], actor_id: Any) -> None:
    try:
        insert_audit_log(
            db.connection(),
            entity_type="case_escalation",
            entity_id=entity_id,
            action_type=action_type,
            new_value=new_value,
            actor_type=ACTOR_HUMAN,
            actor_id=_as_uuid(actor_id),
        )
    except Exception:  # noqa: BLE001 — audit must never break the operation
        log.warning("case_escalation audit-log failed (non-fatal)", exc_info=True)


def create_escalation(
    *,
    case_id: str,
    company_id: str,
    reason: str,
    kind: str = "specialist",
    assignee: Optional[str] = None,
    sla_due_at: Optional[str] = None,
    created_by: Any = None,
) -> Dict[str, Any]:
    """Create an open escalation and return the persisted row."""
    kind = kind if kind in VALID_KINDS else "specialist"
    eid = str(uuid.uuid4())
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO case_escalations "
                "(id, case_id, company_id, kind, reason, status, assignee, sla_due_at, created_by) "
                "VALUES (:id, :c, :co, :k, :r, 'open', :a, :sla, :by)"
            ),
            {"id": eid, "c": case_id, "co": company_id, "k": kind, "r": reason,
             "a": assignee, "sla": sla_due_at, "by": (str(created_by) if created_by else None)},
        )
        _audit(db, entity_id=eid, action_type="insert",
               new_value={"case_id": case_id, "kind": kind, "reason": reason}, actor_id=created_by)
        row = db.execute(text("SELECT * FROM case_escalations WHERE id = :id"), {"id": eid}).mappings().first()
        db.commit()
    return _row_to_dict(row)


def list_escalations(case_id: str, company_id: str) -> List[Dict[str, Any]]:
    """All escalations for a case within the caller's company (newest first)."""
    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT * FROM case_escalations WHERE case_id = :c AND company_id = :co "
                 "ORDER BY created_at DESC"),
            {"c": case_id, "co": company_id},
        ).mappings().all()
    return [_row_to_dict(r) for r in rows]


def resolve_escalation(
    escalation_id: str,
    company_id: str,
    *,
    resolution_note: str,
    resolved_by: Any = None,
) -> Optional[Dict[str, Any]]:
    """Resolve an escalation. Tenant-scoped by company_id (cross-tenant → None).
    Returns the updated row, or None if not found / not in this company."""
    with SessionLocal() as db:
        res = db.execute(
            text("UPDATE case_escalations SET status = 'resolved', resolution_note = :n, "
                 "resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                 "WHERE id = :id AND company_id = :co AND status <> 'resolved'"),
            {"n": resolution_note, "id": escalation_id, "co": company_id},
        )
        if res.rowcount == 0:
            # Either not found, cross-tenant, or already resolved — distinguish the
            # last case so an idempotent re-resolve still returns the row.
            existing = db.execute(
                text("SELECT * FROM case_escalations WHERE id = :id AND company_id = :co"),
                {"id": escalation_id, "co": company_id},
            ).mappings().first()
            db.rollback()
            return _row_to_dict(existing) if existing else None
        _audit(db, entity_id=escalation_id, action_type="update",
               new_value={"status": "resolved", "resolution_note": resolution_note}, actor_id=resolved_by)
        row = db.execute(text("SELECT * FROM case_escalations WHERE id = :id"), {"id": escalation_id}).mappings().first()
        db.commit()
    return _row_to_dict(row)
