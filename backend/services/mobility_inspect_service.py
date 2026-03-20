"""
Admin inspect: audit log rows related to a mobility_cases.id (Postgres jsonb-aware).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

log = logging.getLogger(__name__)


def fetch_audit_logs_for_mobility_case(conn: Connection, case_id: str) -> List[Dict[str, Any]]:
    """Return recent audit rows for the case and its people, documents, evaluations."""
    cid = (case_id or "").strip()
    if not cid:
        return []

    dialect = getattr(conn.engine, "dialect", None)
    if dialect is not None and dialect.name == "postgresql":
        sql = text(
            """
            SELECT
              id::text AS id,
              entity_type,
              entity_id::text AS entity_id,
              action_type,
              old_value_json,
              new_value_json,
              actor_type,
              actor_id::text AS actor_id,
              created_at
            FROM audit_logs
            WHERE entity_id = CAST(:cid AS uuid)
               OR (
                 entity_type = 'case_requirement_evaluations'
                 AND (
                   COALESCE(new_value_json->>'case_id', old_value_json->>'case_id') = :cid_s
                 )
               )
               OR (
                 entity_type = 'case_people'
                 AND (
                   COALESCE(new_value_json->>'case_id', old_value_json->>'case_id') = :cid_s
                 )
               )
               OR (
                 entity_type = 'case_documents'
                 AND (
                   COALESCE(new_value_json->>'case_id', old_value_json->>'case_id') = :cid_s
                 )
               )
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
        params = {"cid": cid, "cid_s": cid}
    else:
        sql = text(
            """
            SELECT id, entity_type, entity_id, action_type,
                   old_value_json, new_value_json, actor_type, actor_id, created_at
            FROM audit_logs
            WHERE entity_id = :cid_s
               OR (
                 entity_type = 'case_requirement_evaluations'
                 AND (
                   (old_value_json IS NOT NULL AND old_value_json LIKE '%' || :cid_s2 || '%')
                   OR (new_value_json IS NOT NULL AND new_value_json LIKE '%' || :cid_s3 || '%')
                 )
               )
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
        params = {"cid_s": cid, "cid_s2": cid, "cid_s3": cid}

    try:
        rows = conn.execute(sql, params).mappings().all()
    except ProgrammingError as ex:
        log.warning("audit_logs query failed (table missing?): %s", ex)
        return []

    import json as _json

    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        for k in ("old_value_json", "new_value_json"):
            v = d.get(k)
            if isinstance(v, dict):
                continue
            if isinstance(v, str) and v.strip().startswith("{"):
                try:
                    d[k] = _json.loads(v)
                except Exception:
                    pass
        if d.get("created_at") is not None and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out
