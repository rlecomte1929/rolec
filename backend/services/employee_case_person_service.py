"""
Sync one case_people row (role=employee) from live assignment data into the mobility graph.

Primary source: employee_profiles.profile_json (wizard / intake lane), keyed by assignment_id.
Secondary: case_assignments HR-entered names; profiles table when employee_user_id is linked.

Does not sync spouse/children. Idempotent; relies on assignment_mobility_links for mobility_cases.id.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

if TYPE_CHECKING:
    from ..database import Database

log = logging.getLogger(__name__)

ROLE_EMPLOYEE = "employee"
# Keys we own on case_people.metadata (replace each sync from live sources)
_SYNC_METADATA_KEYS: Set[str] = {
    "first_name",
    "last_name",
    "full_name",
    "email",
    "nationality",
    "passport_country",
    "residence_country",
    "date_of_birth",
    "relationship_status",
}


def _strip(s: Optional[Any]) -> Optional[str]:
    if s is None:
        return None
    t = str(s).strip()
    return t or None


def _dialect_name(engine: Any) -> str:
    d = getattr(engine, "dialect", None)
    return getattr(d, "name", "") or ""


def _coerce_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            o = json.loads(value)
            return dict(o) if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _mobility_case_id_for_assignment(conn: Any, assignment_id: str) -> Optional[str]:
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


def _build_employee_metadata(
    db: "Database",
    assignment: Dict[str, Any],
    profile_doc: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ep = profile_doc or {}
    emp = _coerce_dict(ep.get("employeeProfile"))
    fam = _coerce_dict(ep.get("familyMembers"))

    first_name = _strip(assignment.get("employee_first_name"))
    last_name = _strip(assignment.get("employee_last_name"))
    full_name = _strip(emp.get("fullName"))
    email = _strip(emp.get("email"))
    nationality = _strip(emp.get("nationality"))
    passport_country = _strip(emp.get("passportCountry"))
    residence_country = _strip(emp.get("residenceCountry"))
    date_of_birth = _strip(emp.get("dateOfBirth"))
    relationship_status = _strip(fam.get("maritalStatus"))

    emp_uid = _strip(assignment.get("employee_user_id"))
    if emp_uid:
        pr = db.get_profile_record(emp_uid)
        if pr:
            if not full_name:
                full_name = _strip(pr.get("full_name"))
            if not email:
                email = _strip(pr.get("email"))

    if not full_name and first_name and last_name:
        full_name = f"{first_name} {last_name}".strip()

    out: Dict[str, Any] = {}
    if first_name:
        out["first_name"] = first_name
    if last_name:
        out["last_name"] = last_name
    if full_name:
        out["full_name"] = full_name
    if email:
        out["email"] = email
    if nationality:
        out["nationality"] = nationality
    if passport_country:
        out["passport_country"] = passport_country
    if residence_country:
        out["residence_country"] = residence_country
    if date_of_birth:
        out["date_of_birth"] = date_of_birth
    if relationship_status:
        out["relationship_status"] = relationship_status
    return out


def _merge_metadata(existing_raw: Any, new_sync: Dict[str, Any]) -> Dict[str, Any]:
    existing = _coerce_dict(existing_raw)
    preserved = {k: v for k, v in existing.items() if k not in _SYNC_METADATA_KEYS}
    merged = {**preserved, **new_sync}
    return merged


def ensure_employee_case_person_for_assignment(
    db: "Database",
    assignment_id: str,
    *,
    request_id: Optional[str] = None,
) -> Optional[str]:
    """
    Ensure exactly one case_people row (role=employee) for the mobility case linked to this assignment.

    Returns case_people.id, or None if no mobility link / schema missing / no mobility case.
    """
    aid = _strip(assignment_id)
    if not aid:
        return None

    try:
        with db.engine.connect() as conn:
            mid = _mobility_case_id_for_assignment(conn, aid)
    except (ProgrammingError, OperationalError) as exc:
        log.debug("assignment_mobility_links / case_people unavailable: %s", exc)
        return None

    if not mid:
        return None

    assignment = db.get_assignment_by_id(aid, request_id=request_id)
    if not assignment:
        return None

    profile_doc = db.get_employee_profile(aid)
    new_sync = _build_employee_metadata(db, assignment, profile_doc)
    is_pg = _dialect_name(db.engine) == "postgresql"
    now = datetime.utcnow().isoformat()

    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT id, metadata FROM case_people "
                    "WHERE case_id = "
                    + ("CAST(:mid AS uuid)" if is_pg else ":mid")
                    + " AND role = :role ORDER BY created_at ASC, id ASC LIMIT 1"
                ),
                {"mid": mid, "role": ROLE_EMPLOYEE},
            ).mappings().first()

            merged = _merge_metadata(row.get("metadata") if row else None, new_sync)
            meta_json = json.dumps(merged)

            if row:
                pid = str(row["id"])
                if is_pg:
                    conn.execute(
                        text(
                            "UPDATE case_people SET metadata = CAST(:meta AS jsonb), updated_at = NOW() "
                            "WHERE id = CAST(:pid AS uuid)"
                        ),
                        {"meta": meta_json, "pid": pid},
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE case_people SET metadata = :meta, updated_at = :ua WHERE id = :pid"
                        ),
                        {"meta": meta_json, "pid": pid, "ua": now},
                    )
                return pid

            pid = str(uuid.uuid4())
            try:
                if is_pg:
                    ins_sql = (
                        "INSERT INTO case_people (id, case_id, role, metadata, created_at, updated_at) VALUES ("
                        "CAST(:pid AS uuid), CAST(:mid AS uuid), :role, CAST(:meta AS jsonb), NOW(), NOW())"
                    )
                    ins_params: Dict[str, Any] = {
                        "pid": pid,
                        "mid": mid,
                        "role": ROLE_EMPLOYEE,
                        "meta": meta_json,
                    }
                else:
                    ins_sql = (
                        "INSERT INTO case_people (id, case_id, role, metadata, created_at, updated_at) "
                        "VALUES (:pid, :mid, :role, :meta, :ca, :ua)"
                    )
                    ins_params = {
                        "pid": pid,
                        "mid": mid,
                        "role": ROLE_EMPLOYEE,
                        "meta": meta_json,
                        "ca": now,
                        "ua": now,
                    }
                conn.execute(text(ins_sql), ins_params)
            except IntegrityError:
                # Concurrent insert or legacy duplicate employee rows
                row2 = conn.execute(
                    text(
                        "SELECT id, metadata FROM case_people "
                        "WHERE case_id = "
                        + ("CAST(:mid AS uuid)" if is_pg else ":mid")
                        + " AND role = :role ORDER BY created_at ASC, id ASC LIMIT 1"
                    ),
                    {"mid": mid, "role": ROLE_EMPLOYEE},
                ).mappings().first()
                if not row2:
                    raise
                pid = str(row2["id"])
                merged2 = _merge_metadata(row2.get("metadata"), new_sync)
                if is_pg:
                    conn.execute(
                        text(
                            "UPDATE case_people SET metadata = CAST(:meta AS jsonb), updated_at = NOW() "
                            "WHERE id = CAST(:pid AS uuid)"
                        ),
                        {"meta": json.dumps(merged2), "pid": pid},
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE case_people SET metadata = :meta, updated_at = :ua WHERE id = :pid"
                        ),
                        {"meta": json.dumps(merged2), "pid": pid, "ua": now},
                    )
                return pid

            return pid
    except (ProgrammingError, OperationalError) as exc:
        log.debug("ensure_employee_case_person_for_assignment failed: %s", exc)
        return None

