"""GDPR data-subject endpoints (PRIV-001 / AIQ-469).

Art. 20 data-portability export. The Art. 17 erasure endpoint is intentionally a
SEPARATE, gated task — it is destructive and requires a corrected PII inventory,
validated subject resolution, and the anonymisation pepper provisioned.

Subject resolution is uuid/text-safe: across the schema the subject is keyed
inconsistently (`profiles.id` uuid, `relocation_cases.employee_id` text,
`employees.profile_id` text, …), so every comparison casts to ``::text`` to
avoid the silent uuid≠text miss that has bitten other rollup queries.
"""
from __future__ import annotations

import decimal
import logging
import uuid as _uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from ..auth_deps import get_current_user
from ...database import db
from ..services.immigration_service import _log_access  # data_access_log writer

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["gdpr"])

# PII tables keyed directly by the subject. `::text = :uid` is uuid/text-safe.
_SUBJECT_TABLES: List[tuple] = [
    ("profiles", "id::text = :uid"),
    ("employees", "profile_id::text = :uid"),
    ("cases", "employee_id::text = :uid"),
    ("relocation_cases", "employee_id::text = :uid"),
    ("case_assignments", "employee_user_id::text = :uid"),
    ("employee_tasks", "employee_id::text = :uid"),
    ("quote_requests", "employee_id::text = :uid"),
    ("consent_records", "employee_id::text = :uid"),
    ("imm_employee_profiles", "employee_id::text = :uid"),
    ("support_tickets", "user_id::text = :uid"),
    ("erasure_requests", "employee_id::text = :uid"),
    ("data_access_log", "accessed_by_user_id::text = :uid OR profile_id::text = :uid"),
]

# PII tables scoped via the subject's resolved case ids.
_CASE_TABLES: List[tuple] = [
    ("case_documents", "case_id::text = ANY(:case_ids)"),
    ("case_forms", "case_id::text = ANY(:case_ids)"),
    ("case_messages", "case_id::text = ANY(:case_ids)"),
    ("pets", "case_id::text = ANY(:case_ids)"),
    ("exception_requests", "case_id::text = ANY(:case_ids)"),
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<binary>"
    return value


def _rows(conn, table: str, where: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SELECT * defensively — a missing table/column yields [] so a schema gap
    can never 500 a subject-rights export."""
    try:
        result = conn.execute(text(f"SELECT * FROM public.{table} WHERE {where}"), params)
        return [{k: _jsonable(v) for k, v in dict(r).items()} for r in result.mappings()]
    except Exception:
        log.warning("gdpr export: table %s skipped (missing/unqueryable)", table, exc_info=True)
        return []


def _resolve_case_ids(conn, uid: str) -> List[str]:
    try:
        rows = conn.execute(
            text(
                """
                SELECT id::text AS cid FROM public.cases WHERE employee_id::text = :uid
                UNION SELECT id::text FROM public.relocation_cases WHERE employee_id::text = :uid
                UNION SELECT case_id::text FROM public.case_assignments WHERE employee_user_id::text = :uid
                """
            ),
            {"uid": uid},
        ).all()
        return [r[0] for r in rows if r[0]]
    except Exception:
        log.warning("gdpr export: case-id resolution failed", exc_info=True)
        return []


def _subject_company_ids(conn, uid: str) -> set:
    try:
        rows = conn.execute(
            text(
                """
                SELECT company_id::text AS c FROM public.cases
                  WHERE employee_id::text = :uid AND company_id IS NOT NULL
                UNION SELECT company_id::text FROM public.relocation_cases
                  WHERE employee_id::text = :uid AND company_id IS NOT NULL
                UNION SELECT company_id::text FROM public.employees
                  WHERE profile_id::text = :uid AND company_id IS NOT NULL
                """
            ),
            {"uid": uid},
        ).all()
        return {r[0] for r in rows if r[0]}
    except Exception:
        log.warning("gdpr export: subject-company resolution failed", exc_info=True)
        return set()


def build_subject_export(user_id: str) -> Dict[str, Any]:
    """Assemble a machine-readable JSON export of all PII held for the subject."""
    uid = str(user_id)
    tables: Dict[str, Any] = {}
    with db.engine.begin() as conn:
        case_ids = _resolve_case_ids(conn, uid)
        for tname, where in _SUBJECT_TABLES:
            rows = _rows(conn, tname, where, {"uid": uid})
            if rows:
                tables[tname] = rows
        if case_ids:
            for tname, where in _CASE_TABLES:
                rows = _rows(conn, tname, where, {"case_ids": case_ids})
                if rows:
                    tables[tname] = rows
    return {
        "user_id": uid,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }


def _assert_export_access(caller: Dict[str, Any], subject_user_id: str) -> None:
    """Allow: the subject themselves, a platform admin, or an HR admin in the
    subject's org. Cross-org HR (and everyone else) gets 403."""
    caller_id = str(caller.get("id") or caller.get("sub") or "")
    if caller_id and caller_id == str(subject_user_id):
        return  # own data
    role = (caller.get("role") or "").upper()
    if role == "ADMIN":
        return  # platform admin
    if role == "HR":
        hr_company = str(db.get_hr_company_id(caller.get("id")) or caller.get("company") or "")
        if hr_company:
            with db.engine.begin() as conn:
                subject_companies = _subject_company_ids(conn, str(subject_user_id))
            if hr_company in subject_companies:
                return  # HR admin in the subject's org
    raise HTTPException(status_code=403, detail="Not permitted to export this subject's data.")


@router.get("/users/{user_id}/data-export")
def export_user_data(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """GDPR Art. 20 — machine-readable export of all personal data held for the
    subject, as ``{user_id, exported_at, tables: {<table>: [rows]}}``.

    Access: the subject, a platform admin, or an HR admin in the subject's org;
    cross-org access is rejected with 403.
    """
    _assert_export_access(current_user, user_id)
    export = build_subject_export(user_id)
    # The export is itself a PII access — record it (fail-soft).
    _log_access(
        case_id=None,
        profile_id=None,
        user_id=str(current_user.get("id") or ""),
        role=(current_user.get("role") or "").lower() or "employee",
        action="gdpr_data_export",
        fields=list(export["tables"].keys()),
        purpose="data_portability",
    )
    return export
