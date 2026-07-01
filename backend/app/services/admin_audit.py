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

UUID safety (Postgres):
  ``audit_logs.actor_id`` and ``audit_logs.entity_id`` are typed ``uuid`` in
  Postgres.  Legacy admin IDs (e.g. ``"seed-admin-testingapril"``) are plain
  text and would raise ``invalid input syntax for type uuid`` if bound
  directly.  ``_normalise_uuid_field`` detects non-UUID values and routes them
  to ``new_value_json`` (``actor_ref`` / ``entity_ref``) so the INSERT always
  succeeds on Postgres while the original human-readable identifier is still
  preserved in the row.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .audit_log_service import ACTION_UPDATE, ACTOR_HUMAN, insert_audit_log

log = logging.getLogger(__name__)


def _is_valid_uuid(value: str) -> bool:
    """Return True iff *value* is a canonical UUID string."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _normalise_uuid_field(
    value: Optional[str],
    sidecar_key: str,
    new_value: Dict[str, Any],
    *,
    nullable: bool,
    auto_generate: bool = False,
) -> Optional[str]:
    """Normalise *value* for a Postgres ``uuid`` column.

    If *value* is already a valid UUID (or None), it is returned unchanged.
    If it is a non-UUID string:
      - The original value is stored in ``new_value[sidecar_key]`` so it is
        not lost.
      - Returns ``None`` when the column is nullable (``nullable=True``), or
        a freshly-generated UUID when the column is NOT NULL
        (``auto_generate=True``).

    Args:
        value:       Caller-supplied id string (may be legacy text).
        sidecar_key: Key under which to stash the original in *new_value*.
        new_value:   The dict being built for ``new_value_json``; mutated
                     in-place when a sidecar entry is needed.
        nullable:    Whether the target column accepts NULL.
        auto_generate: When True and the column is NOT NULL, generate a UUID
                     instead of returning None.
    """
    if value is None:
        return None
    if _is_valid_uuid(value):
        return value
    # Non-UUID: preserve original, return safe column value.
    new_value[sidecar_key] = value
    if nullable:
        return None
    # Column is NOT NULL — must supply a valid uuid.
    return str(uuid.uuid4())


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
        etype = entity or "admin_event"

        # actor_id: uuid nullable → non-UUID goes to new_value["actor_ref"], column gets NULL.
        safe_actor_id = _normalise_uuid_field(
            actor_id, "actor_ref", new_value, nullable=True
        )

        # entity_id: uuid NOT NULL → non-UUID goes to new_value["entity_ref"], column gets new UUID.
        raw_eid = entity_id  # may be None
        if raw_eid is not None:
            safe_eid = _normalise_uuid_field(
                raw_eid, "entity_ref", new_value, nullable=False, auto_generate=True
            )
        else:
            safe_eid = str(uuid.uuid4())

        if isinstance(db, Session):
            conn = db.connection()
            insert_audit_log(
                conn,
                entity_type=etype,
                entity_id=safe_eid,
                action_type=ACTION_UPDATE,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=safe_actor_id,
            )
        else:
            # Assume db is already a Connection (e.g. inside ``with engine.begin() as conn``)
            insert_audit_log(
                db,
                entity_type=etype,
                entity_id=safe_eid,
                action_type=ACTION_UPDATE,
                new_value=new_value,
                actor_type=ACTOR_HUMAN,
                actor_id=safe_actor_id,
            )
    except Exception:
        log.exception(
            "record_admin_event failed (best-effort, suppressed) event=%s actor=%s",
            event,
            actor_id,
        )
