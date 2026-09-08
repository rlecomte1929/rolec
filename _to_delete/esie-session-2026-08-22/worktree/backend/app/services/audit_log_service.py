"""
Audit log helper — inserts into public.audit_logs (evaluations + optional app-level rows).

Postgres: mobility_cases, case_people, case_documents are also covered by relopass_audit_row()
triggers when rows change. Evaluations are logged here so SQLite tests and services stay aligned.

Optional session context for trigger-backed writes (Postgres only):
  SET LOCAL relopass.audit_actor_type = 'human';
  SET LOCAL relopass.audit_actor_id = '<uuid>';
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

log = logging.getLogger(__name__)

ACTION_INSERT = "insert"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"

ACTOR_SYSTEM = "system"
ACTOR_HUMAN = "human"
ACTOR_SERVICE = "service"


def _as_uuid_or_none(value: Optional[str]) -> Optional[str]:
    """`value` if it parses as a UUID, else None.

    [AIQ-1807] `audit_logs.actor_id` is uuid and nullable. Callers hand it the
    authenticated user's id, which is TEXT for legacy ReloPass-session accounts. Passing
    one through raises and — before the savepoint below — took the caller's write with it.
    """
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _json_param(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps({"_error": "non_serializable"})


def insert_audit_log(
    conn: Connection,
    *,
    entity_type: str,
    entity_id: str,
    action_type: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    actor_type: str = ACTOR_SYSTEM,
    actor_id: Optional[str] = None,
) -> str:
    """
    Insert one audit_logs row. Returns new audit log id (uuid string).
    Works on Postgres (jsonb) and SQLite tests (TEXT json).
    """
    aid = str(uuid.uuid4())
    old_s = _json_param(old_value)
    new_s = _json_param(new_value)
    dialect = getattr(conn.engine, "dialect", None)
    is_pg = dialect is not None and dialect.name == "postgresql"
    if is_pg:
        sql = """
            INSERT INTO audit_logs (
              id, entity_type, entity_id, action_type,
              old_value_json, new_value_json, actor_type, actor_id
            ) VALUES (
              :id, :et, :eid, :at,
              CAST(:old_j AS jsonb), CAST(:new_j AS jsonb), :actor_t, :actor_id
            )
            """
    else:
        sql = """
            INSERT INTO audit_logs (
              id, entity_type, entity_id, action_type,
              old_value_json, new_value_json, actor_type, actor_id
            ) VALUES (
              :id, :et, :eid, :at,
              :old_j, :new_j, :actor_t, :actor_id
            )
            """
    # [AIQ-1807] actor_id is a nullable uuid column, and callers pass whatever id the
    # authenticated user carries. Legacy/seed ReloPass-session accounts have TEXT ids
    # (e.g. 'seed-emp-testingapril'), which Postgres rejects with `invalid input syntax
    # for type uuid`. Coerce rather than raise, and keep the real value in the payload so
    # the actor is still recorded — just not in a column it never fitted.
    actor_uuid = _as_uuid_or_none(actor_id)
    if actor_id and actor_uuid is None:
        new_s = _json_param({**(new_value or {}), "actor_ref": str(actor_id)})

    # THE SAVEPOINT IS THE POINT OF THIS FUNCTION'S FAILURE HANDLING.
    #
    # This INSERT runs on the CALLER's connection, inside the caller's transaction. A
    # failure here aborts that transaction — and a Python `except` around the call does
    # not un-abort it. 64 call sites wrap this in `try/except: log`, so the caller
    # believed it had degraded gracefully while SQLAlchemy's commit-on-exit silently
    # became a ROLLBACK and took the PRIMARY write with it.
    #
    # That is not hypothetical: POST /api/employee/cases/{id}/consent returned 201 with a
    # consent_record_id and wrote no consent row, because this insert raised on a
    # non-uuid actor_id. The employee was told their GDPR consent was recorded when it
    # was not, and the consent gate then correctly refused to proceed — an unescapable
    # loop.
    #
    # begin_nested() scopes the damage to a SAVEPOINT: a failure rolls back the audit row
    # only, and the caller's write survives. Same pattern as _apply_erasure in
    # routers/gdpr.py.
    #
    # SOFT, BUT LOUD. An audit_logs gap is an accountability gap, so a swallowed failure
    # is its own compliance problem in the opposite direction. Logged at ERROR with the
    # entity, never silently.
    try:
        with conn.begin_nested():
            conn.execute(
                text(sql),
                {
                    "id": aid,
                    "et": entity_type,
                    "eid": entity_id,
                    "at": action_type,
                    "old_j": old_s,
                    "new_j": new_s,
                    "actor_t": actor_type,
                    "actor_id": actor_uuid,
                },
            )
    except Exception:
        log.error(
            "AUDIT GAP: audit_logs insert failed for %s/%s action=%s — the caller's write "
            "was preserved, but this action has no audit row",
            entity_type, entity_id, action_type, exc_info=True,
        )
    return aid


def fetch_evaluation_row_dict(conn: Connection, evaluation_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT id, case_id, person_id, requirement_id, source_rule_id,
                   evaluation_status, reason_text, evaluated_at, evaluated_by,
                   created_at, updated_at
            FROM case_requirement_evaluations
            WHERE id = :id
            LIMIT 1
            """
        ),
        {"id": evaluation_id},
    ).mappings().first()
    if not row:
        return None
    d = dict(row)
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            try:
                out[k] = v.isoformat()
            except Exception:
                out[k] = str(v)
        else:
            out[k] = v
    return out


def set_audit_actor_context(conn: Connection, actor_type: str, actor_id: Optional[str] = None) -> None:
    """Postgres only: following INSERT/UPDATE on audited tables will use this actor in triggers."""
    try:
        conn.execute(text("SELECT set_config('relopass.audit_actor_type', :t, true)"), {"t": actor_type})
        conn.execute(
            text("SELECT set_config('relopass.audit_actor_id', :id, true)"),
            {"id": actor_id or ""},
        )
    except Exception as ex:
        log.debug("set_audit_actor_context skipped (non-Postgres or no set_config): %s", ex)
