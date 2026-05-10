"""
Durable bridge: case_assignments.id -> mobility_cases.id via assignment_mobility_links.

Idempotent; does not read wizard flags. Safe when mobility tables are missing (returns None).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .audit_log_service import ACTION_INSERT, ACTOR_SERVICE, insert_audit_log

if TYPE_CHECKING:
    from ..database import Database

log = logging.getLogger(__name__)


def _strip(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def _parse_uuid(s: Optional[str]) -> Optional[uuid.UUID]:
    t = _strip(s)
    if not t:
        return None
    try:
        return uuid.UUID(t)
    except (ValueError, AttributeError):
        return None


def _dialect_name(engine: Any) -> str:
    d = getattr(engine, "dialect", None)
    return getattr(d, "name", "") or ""


def _select_link_mobility_case_id(conn: Any, assignment_id: str) -> Optional[str]:
    row = conn.execute(
        text(
            "SELECT mobility_case_id FROM assignment_mobility_links "
            "WHERE assignment_id = :aid LIMIT 1"
        ),
        {"aid": assignment_id},
    ).mappings().first()
    if not row:
        return None
    mid = row.get("mobility_case_id")
    return str(mid).strip() if mid is not None else None


def _resolve_company_id_for_mobility(db: "Database", assignment: Dict[str, Any], case_row: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return a string suitable for mobility_cases.company_id (must be a real UUID on Postgres)."""
    if case_row:
        cid = _parse_uuid(case_row.get("company_id"))
        if cid:
            return str(cid)
    hr_id = _strip(assignment.get("hr_user_id"))
    if hr_id:
        co = db.get_company_for_user(hr_id) or None
        if co:
            cid = _parse_uuid(co.get("id"))
            if cid:
                return str(cid)
        hcid = _strip(db.get_hr_company_id(hr_id))
        if hcid:
            cid = _parse_uuid(hcid)
            if cid:
                return str(cid)
    return None


def ensure_mobility_case_link_for_assignment(
    db: "Database",
    assignment_id: str,
    *,
    request_id: Optional[str] = None,
) -> Optional[str]:
    """
    Return mobility_cases.id for this assignment, creating mobility_cases + bridge row if needed.
    Returns None if tables are missing or company_id cannot be resolved to a UUID (Postgres).
    """
    aid = _strip(assignment_id)
    if not aid:
        return None

    try:
        with db.engine.connect() as conn:
            existing = _select_link_mobility_case_id(conn, aid)
            if existing:
                return existing
    except (ProgrammingError, OperationalError) as exc:
        log.debug("assignment_mobility_links unreadable (schema?): %s", exc)
        return None

    assignment = db.get_assignment_by_id(aid, request_id=request_id)
    if not assignment:
        return None
    case_id = _strip(assignment.get("case_id")) or _strip(assignment.get("canonical_case_id"))
    case_row = db.get_case_by_id(case_id) if case_id else None
    company_id = _resolve_company_id_for_mobility(db, assignment, case_row)
    if not company_id:
        log.warning(
            "ensure_mobility_case_link: no UUID company_id for assignment_id=%s",
            aid,
        )
        return None

    emp_uid = _parse_uuid(assignment.get("employee_user_id"))
    emp_sql = str(emp_uid) if emp_uid else None

    origin = _strip(case_row.get("home_country")) if case_row else None
    dest = _strip(case_row.get("host_country")) if case_row else None
    case_type: Optional[str] = None

    is_pg = _dialect_name(db.engine) == "postgresql"
    mobility_id = str(uuid.uuid4())
    link_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    try:
        with db.engine.begin() as conn:
            again = _select_link_mobility_case_id(conn, aid)
            if again:
                return again

            if is_pg:
                base_params = {
                    "id": mobility_id,
                    "cid": company_id,
                    "origin": origin,
                    "dest": dest,
                    "ctype": case_type,
                }
                if emp_sql:
                    conn.execute(
                        text(
                            "INSERT INTO mobility_cases (id, company_id, employee_user_id, "
                            "origin_country, destination_country, case_type, created_at, updated_at) "
                            "VALUES (CAST(:id AS uuid), CAST(:cid AS uuid), CAST(:eid AS uuid), "
                            ":origin, :dest, :ctype, NOW(), NOW())"
                        ),
                        {**base_params, "eid": emp_sql},
                    )
                else:
                    conn.execute(
                        text(
                            "INSERT INTO mobility_cases (id, company_id, employee_user_id, "
                            "origin_country, destination_country, case_type, created_at, updated_at) "
                            "VALUES (CAST(:id AS uuid), CAST(:cid AS uuid), NULL, "
                            ":origin, :dest, :ctype, NOW(), NOW())"
                        ),
                        base_params,
                    )
                conn.execute(
                    text(
                        "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                        "VALUES (CAST(:lid AS uuid), :aid, CAST(:mid AS uuid), NOW(), NOW())"
                    ),
                    {"lid": link_id, "aid": aid, "mid": mobility_id},
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO mobility_cases (id, company_id, employee_user_id, "
                        "origin_country, destination_country, case_type, metadata, created_at, updated_at) "
                        "VALUES (:id, :cid, :eid, :origin, :dest, :ctype, '{}', :ca, :ua)"
                    ),
                    {
                        "id": mobility_id,
                        "cid": company_id,
                        "eid": emp_sql,
                        "origin": origin,
                        "dest": dest,
                        "ctype": case_type,
                        "ca": now,
                        "ua": now,
                    },
                )
                conn.execute(
                    text(
                        "INSERT INTO assignment_mobility_links (id, assignment_id, mobility_case_id, created_at, updated_at) "
                        "VALUES (:lid, :aid, :mid, :ca, :ua)"
                    ),
                    {"lid": link_id, "aid": aid, "mid": mobility_id, "ca": now, "ua": now},
                )

            try:
                insert_audit_log(
                    conn,
                    entity_type="assignment_mobility_links",
                    entity_id=link_id,
                    action_type=ACTION_INSERT,
                    new_value={
                        "assignment_id": aid,
                        "mobility_case_id": mobility_id,
                    },
                    actor_type=ACTOR_SERVICE,
                    actor_id=None,
                )
            except (ProgrammingError, OperationalError) as audit_exc:
                log.debug("assignment_mobility_links audit insert skipped: %s", audit_exc)

        return mobility_id
    except IntegrityError:
        with db.engine.connect() as conn:
            return _select_link_mobility_case_id(conn, aid)
    except (ProgrammingError, OperationalError) as exc:
        log.debug("ensure_mobility_case_link failed (schema?): %s", exc)
        return None
