"""Shared admin audit writer.

Writes one ``audit_logs`` row for each admin-initiated action.  Used by
admin-hardening tasks (A-01, A-07, …).

Design notes:
- ``action_type`` is always ``'update'``; the semantic event name lives in
  ``new_value_json.event`` to stay within the CHECK(insert|update|delete).
- ``actor_type`` is always ``'human'`` — admin actions are human-initiated.
- Best-effort: exceptions are logged and suppressed; an audit-write failure
  must never break the real action.
- ``db`` accepts a SQLAlchemy Session (typical router injection) or a raw
  Connection (for callers that already hold one).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .audit_log_service import ACTION_UPDATE, ACTOR_HUMAN, insert_audit_log

log = logging.getLogger(__name__)


def record_admin_event(
    db: Any,
    *,
    actor_id: str,
    event: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one ``audit_logs`` row for an admin action.

    Args:
        db: SQLAlchemy Session or Connection for the current request.
        actor_id: The admin user's id (string; may be legacy text id).
        event: Semantic event name, e.g. ``'country.policy_updated'``.
        entity: Logical table/domain name (defaults to ``'admin_event'``).
        entity_id: Target entity id string (uuid preferred).  Auto-generated
            if omitted so that the NOT NULL constraint is always satisfied.
        detail: Extra key/value pairs merged into ``new_value_json``.
    """
    try:
        new_value: Dict[str, Any] = {"event": event, **(detail or {})}
        eid = entity_id or str(uuid.uuid4())
        etype = entity or "admin_event"

        if isinstance(db, Session):
            conn = db.connection()
            insert_audit_log(
                conn,
                entity_type=etype,
                entity_id=eid,
                action_type=ACTION_UPDATE,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
        else:
            # Assume db is already a Connection (e.g. inside ``with engine.begin() as conn``)
            insert_audit_log(
                db,
                entity_type=etype,
                entity_id=eid,
                action_type=ACTION_UPDATE,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=actor_id,
            )
    except Exception:
        log.exception(
            "record_admin_event failed (best-effort, suppressed) event=%s actor=%s",
            event,
            actor_id,
        )
