"""Platform audit-log viewer (Task 7 — A-05).

GET /api/admin/audit-log?since=&actor=&event=&limit=&offset=

Admin-only. Reads audit_logs ordered by created_at DESC with optional filters.
Dual-registered in both backend/main.py and backend/app/main.py.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth_deps import require_admin
from ..db import SessionLocal

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin-audit-log"])


def _get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/audit-log")
def get_audit_log(
    since: Optional[str] = Query(None, description="ISO datetime lower bound (inclusive)"),
    actor: Optional[str] = Query(None, description="Filter by actor_id (substring match)"),
    event: Optional[str] = Query(None, description="Filter by event name in new_value_json.event (exact)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(_get_db),
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    clauses = ["1=1"]
    params: Dict[str, Any] = {}

    if since:
        clauses.append("created_at >= :since")
        params["since"] = since

    if actor:
        # Use LIKE for substring match; works on both SQLite and Postgres
        clauses.append("actor_id LIKE :actor")
        params["actor"] = f"%{actor}%"

    if event:
        # Use dialect-aware JSON extraction rather than LIKE to avoid spacing sensitivity.
        # Postgres: new_value_json is jsonb → use ->> operator.
        # SQLite: new_value_json is TEXT → use json_extract().
        _engine = getattr(db, "bind", None)
        _dialect = getattr(getattr(_engine, "dialect", None), "name", "") if _engine else ""
        if _dialect == "postgresql":
            clauses.append("new_value_json ->> 'event' = :event_val")
        else:
            clauses.append("json_extract(new_value_json, '$.event') = :event_val")
        params["event_val"] = event

    where = " AND ".join(clauses)
    params["limit"] = limit
    params["offset"] = offset

    rows = db.execute(
        text(
            f"SELECT id, entity_type, entity_id, action_type, "
            f"old_value_json, new_value_json, actor_type, actor_id, created_at "
            f"FROM audit_logs WHERE {where} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    def _parse_json(s: Optional[str]) -> Any:
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return s

    items = [
        {
            "id": r[0],
            "entity_type": r[1],
            "entity_id": r[2],
            "action_type": r[3],
            "old_value": _parse_json(r[4]),
            "new_value": _parse_json(r[5]),
            "actor_type": r[6],
            "actor_id": r[7],
            "created_at": r[8],
        }
        for r in rows
    ]
    return {"items": items, "limit": limit, "offset": offset}
