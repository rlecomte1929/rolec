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
from typing import Any, Dict, List, Optional

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
    # [AIQ-1842] Assignment-keyed, not subject-keyed — which is why it was missed. The
    # whole row is the relocation profile: `profile_json` carries primaryApplicant
    # nationality on all 511 prod rows. Resolved through the subject's assignments here
    # rather than via :case_ids, because `assignment_id` matches `case_assignments.id`
    # (505/511 in prod) and NOT `case_assignments.case_id` (0/511 — measured).
    (
        "wizard_employee_profiles",
        "assignment_id IN (SELECT id::text FROM public.case_assignments "
        "WHERE employee_user_id::text = :uid)",
    ),
]

# PII tables scoped via the subject's resolved case ids.
_CASE_TABLES: List[tuple] = [
    ("case_documents", "case_id::text = ANY(:case_ids)"),
    ("case_forms", "case_id::text = ANY(:case_ids)"),
    ("case_messages", "case_id::text = ANY(:case_ids)"),
    ("pets", "case_id::text = ANY(:case_ids)"),
    ("exception_requests", "case_id::text = ANY(:case_ids)"),
    # [AIQ-1842] `wizard_cases.id` IS a case id — it matches all three sources
    # `_resolve_case_ids` unions (cases 542, relocation_cases 640, case_assignments
    # .case_id 634 in prod), so it belongs here rather than in _SUBJECT_TABLES. Its
    # `draft_json` holds intake PII: full name, nationality, passport country/expiry,
    # employer and family members (949 of 1455 rows carry a nationality).
    ("wizard_cases", "id::text = ANY(:case_ids)"),
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


# --- Art. 17 erasure -------------------------------------------------------
#
# Per-table erasure action, driven by the PRIV-003 retention policy
# ("deletion is the default; anonymise only audit/accountability chains").
# The subject surface is the SAME _SUBJECT_TABLES / _CASE_TABLES the export
# walks, so erasure removes exactly what the export exposes.
#
#   ("delete",)            hard-delete the matched rows (operational data)
#   ("delete_authored",)   hard-delete only rows the subject authored
#   ("anon", [cols])       NULL the listed PII columns, keep the row skeleton
#   ("redact_json", [cols])overwrite the listed JSON blob columns with '{}' — for
#                          NOT NULL blobs, where ("anon", …) cannot be used
#   ("anon_imm",)          NULL the immigration PII block + stamp anonymised_at
#   ("retain_null", [cols])keep the row (legal/accountability), NULL only the
#                          listed network-PII columns
#   ("retain",)            keep the row untouched (it is the compliance record)
#   ("fulfil",)            mark the subject's open erasure_requests completed
_IMM_PII_COLS = [
    "legal_first_name", "legal_last_name", "middle_names", "date_of_birth",
    "place_of_birth", "nationality", "second_nationality", "gender",
    "passport_number", "passport_expiry", "passport_issue_date", "passport_country",
    "passport_mrz_line1", "passport_mrz_line2", "existing_visa_type",
    "existing_visa_expiry", "current_address", "address_history", "employer_name",
    "employer_reg_number", "employer_address", "job_title", "job_title_local",
    "salary_amount", "salary_currency", "marital_status", "spouse_name",
    "spouse_nationality", "spouse_dob", "dependents", "highest_qualification",
    "institution", "field_sources", "field_conflicts",
]
_ERASURE_ACTIONS: Dict[str, tuple] = {
    "profiles": ("anon", ["email", "full_name", "avatar_url"]),
    "employees": ("delete",),
    "cases": ("anon", ["intake_data", "notes"]),
    "relocation_cases": ("anon", ["profile_json"]),
    "case_assignments": ("anon", [
        "employee_first_name", "employee_last_name", "employee_identifier",
        "hr_notes", "intake_draft", "employee_contact_id",
    ]),
    "employee_tasks": ("delete",),
    "quote_requests": ("delete",),
    "consent_records": ("retain_null", ["ip_address", "user_agent"]),
    "imm_employee_profiles": ("anon_imm",),
    # [AIQ-1842] Deleted, not redacted: the table is (assignment_id, profile_json,
    # updated_at) and profile_json IS the relocation profile, so there is no non-PII
    # skeleton to preserve. Nothing FK-references it.
    "wizard_employee_profiles": ("delete",),
    "support_tickets": ("anon", [
        "from_email", "from_name", "subject", "raw_content", "html_content",
    ]),
    "erasure_requests": ("fulfil",),
    "data_access_log": ("retain_null", ["ip_address"]),
    # case-scoped
    "case_documents": ("delete",),
    "case_forms": ("delete",),
    "case_messages": ("delete_authored",),
    "pets": ("delete",),
    # [AIQ-1842] Redacted, not deleted: case_feedback, case_participants and
    # case_evidence all FK-reference wizard_cases, and the row's non-PII skeleton
    # (corridor, dates, status) is operational data. `anon` is unusable here —
    # draft_json is NOT NULL, so `SET draft_json = NULL` raises 23502, the SAVEPOINT
    # rolls it back and the table is reported in errors having erased nothing. That is
    # the AIQ-1801 defect exactly, so this writes '{}' instead.
    "wizard_cases": ("redact_json", ["draft_json", "family_details"]),
    # `ai_insight` was listed here and does not exist on the table — see
    # _erasable_columns. Its presence meant NOTHING on this table was ever erased.
    "exception_requests": ("anon", ["reason", "resolution_notes"]),
}


def _existing_columns(conn, table: str) -> Optional[set]:
    """The columns `public.<table>` actually has, or None if that can't be determined.

    Returning None means "don't filter" — callers then build the statement exactly as
    before. Fail-OPEN is deliberate: erasure must never be weakened by an introspection
    hiccup, and on SQLite (the test engine) information_schema does not exist at all.
    """
    try:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table},
        ).fetchall()
    except Exception:
        return None
    cols = {r[0] for r in rows}
    return cols or None


def _erasable_columns(conn, table: str, wanted: List[str], summary) -> List[str]:
    """Narrow `wanted` to the columns that exist, recording any that do not.

    [AIQ-1801] Why this exists. `_ERASURE_ACTIONS` named `ai_insight` on
    exception_requests, and that column does not exist. The whole list was rendered
    into ONE `UPDATE ... SET a = NULL, b = NULL, c = NULL`, so the single bad name made
    the statement raise, the SAVEPOINT rolled it back, and `reason` and
    `resolution_notes` — case-linked free text belonging to the data subject — were
    never erased. An Article 17 obligation silently unfulfilled because a schema drifted.

    One stale name must not cost the whole table. Erase what exists; report what does
    not, so a partial erasure can never be read as a complete one.
    """
    existing = _existing_columns(conn, table)
    if existing is None:
        return wanted
    missing = [c for c in wanted if c not in existing]
    if missing:
        log.error(
            "gdpr erasure: table %s lists column(s) %s that do not exist — "
            "erasing the remaining %d column(s); FIX THE MAP",
            table, ", ".join(missing), len(wanted) - len(missing),
        )
        summary.setdefault("skipped_columns", []).extend(
            f"{table}.{c}" for c in missing
        )
    return [c for c in wanted if c in existing]


def _apply_erasure(conn, table, where, params, summary):
    """Run one table's erasure action inside a SAVEPOINT so a single failing
    table (missing column, lock) records an error without aborting the rest."""
    action = _ERASURE_ACTIONS.get(table)
    if not action:
        return
    kind = action[0]
    try:
        with conn.begin_nested():
            if kind == "delete":
                conn.execute(text(f"DELETE FROM public.{table} WHERE {where}"), params)
                summary["erased_tables"].append(table)
            elif kind == "delete_authored":
                conn.execute(
                    text(f"DELETE FROM public.{table} WHERE ({where}) AND sender_id::text = :uid"),
                    params,
                )
                summary["erased_tables"].append(table)
            elif kind in ("anon", "retain_null"):
                cols = _erasable_columns(conn, table, list(action[1]), summary)
                if not cols:
                    # Every listed column is gone. Erasing nothing while reporting the
                    # table as anonymised would be the lie this change exists to prevent.
                    raise RuntimeError(
                        f"{table}: none of the columns listed for erasure exist"
                    )
                sets = ", ".join(f"{c} = NULL" for c in cols)
                conn.execute(text(f"UPDATE public.{table} SET {sets} WHERE {where}"), params)
                (summary["anonymised_tables"] if kind == "anon"
                 else summary["retained_tables"]).append(table)
            elif kind == "redact_json":
                # Same shape as "anon", but writes '{}' instead of NULL so it works on a
                # NOT NULL blob. '{}' assigns cleanly to both `text` (wizard_cases
                # .draft_json) and `jsonb` (family_details), so one statement covers both.
                cols = _erasable_columns(conn, table, list(action[1]), summary)
                if not cols:
                    raise RuntimeError(
                        f"{table}: none of the columns listed for redaction exist"
                    )
                sets = ", ".join(f"{c} = '{{}}'" for c in cols)
                conn.execute(text(f"UPDATE public.{table} SET {sets} WHERE {where}"), params)
                summary["anonymised_tables"].append(table)
            elif kind == "anon_imm":
                cols = _erasable_columns(conn, table, list(_IMM_PII_COLS), summary)
                if not cols:
                    raise RuntimeError(
                        f"{table}: none of the immigration PII columns exist"
                    )
                sets = ", ".join(f"{c} = NULL" for c in cols)
                conn.execute(
                    text(f"UPDATE public.{table} SET {sets}, anonymised_at = now() WHERE {where}"),
                    params,
                )
                summary["anonymised_tables"].append(table)
            elif kind == "fulfil":
                conn.execute(
                    text(
                        f"UPDATE public.{table} SET status = 'completed', completed_at = now() "
                        f"WHERE ({where}) AND status <> 'completed'"
                    ),
                    params,
                )
                summary["retained_tables"].append(table)
    except Exception:
        log.warning("gdpr erasure: table %s action %s failed", table, kind, exc_info=True)
        summary["errors"].append(table)


def _delete_supabase_auth_user(user_id: str) -> bool:
    """Delete the subject's Supabase Auth record (the final erasure step).
    Fail-soft: a missing service role / non-UUID id / SDK error is logged, not
    raised — the app-data erasure already committed and must not be rolled back."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        from ..services.supabase_auth_sync import _call_with_timeout
    except Exception:
        return False
    try:
        client = get_supabase_admin_client()
        _call_with_timeout(client.auth.admin.delete_user, user_id)
        return True
    except Exception:
        log.warning("gdpr erasure: supabase auth delete failed", exc_info=True)
        return False


def erase_subject_data(user_id: str) -> Dict[str, Any]:
    """Erase/anonymise all PII held for the subject, then delete the auth user.

    Returns {erased_tables, anonymised_tables, retained_tables, errors,
    auth_user_deleted}. Idempotent: a re-run deletes 0 operational rows and
    re-NULLs already-anonymised columns harmlessly.
    """
    uid = str(user_id)
    summary: Dict[str, Any] = {
        "erased_tables": [], "anonymised_tables": [], "retained_tables": [], "errors": [],
        # [AIQ-1801] "table.column" entries the map asked us to erase that do not exist.
        # A table can appear in anonymised_tables AND contribute here — that is a PARTIAL
        # erasure, and the whole point is that it is distinguishable from a complete one.
        "skipped_columns": [],
    }
    with db.engine.begin() as conn:
        case_ids = _resolve_case_ids(conn, uid)
        for table, where in _SUBJECT_TABLES:
            _apply_erasure(conn, table, where, {"uid": uid}, summary)
        if case_ids:
            for table, where in _CASE_TABLES:
                _apply_erasure(conn, table, where, {"case_ids": case_ids, "uid": uid}, summary)
    # Supabase auth.users is deleted LAST, outside the DB txn (Art. 17 final step).
    summary["auth_user_deleted"] = _delete_supabase_auth_user(uid)
    return summary


def _assert_erasure_access(caller: Dict[str, Any], subject_user_id: str) -> None:
    """Erasure is tighter than export: the subject themselves or a platform
    admin only. HR (any org) and everyone else → 403."""
    caller_id = str(caller.get("id") or caller.get("sub") or "")
    if caller_id and caller_id == str(subject_user_id):
        return  # own data
    if (caller.get("role") or "").upper() == "ADMIN" or caller.get("is_admin"):
        return  # platform admin
    raise HTTPException(status_code=403, detail="Not permitted to erase this subject's data.")


@router.delete("/users/{user_id}/data")
def erase_user_data(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """GDPR Art. 17 — erase (or anonymise, where an audit/accountability
    obligation applies) all personal data held for the subject.

    Access: the subject or a platform admin only (HR cannot erase). Returns a
    table-level summary for the DPO runbook.
    """
    _assert_erasure_access(current_user, user_id)
    summary = erase_subject_data(user_id)
    # The erasure act is itself a logged event (fail-soft).
    _log_access(
        case_id=None,
        profile_id=None,
        user_id=str(current_user.get("id") or ""),
        role=(current_user.get("role") or "").lower() or "employee",
        action="gdpr_erasure",
        fields=summary["erased_tables"] + summary["anonymised_tables"],
        purpose="right_to_erasure",
    )
    return summary


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
