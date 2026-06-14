"""
case_service.py — business-logic helpers extracted from
``backend/app/routers/cases.py`` (AUDIT-B9-cases-2).

Pure, importable; contains **no** FastAPI route handlers. Houses:

* Postgres-vs-SQLite dialect helpers (`_pg_table`, `_sql_now`, `_sql_uuid_gen`,
  `_pg_conn`).
* Tenant-isolation guard (`_assert_case_access`) — the linchpin used by every
  case-scoped route handler.
* Audit-log writer (`_audit_case`) and draft-merge helper
  (`_deep_merge_case_drafts`).
* ``CaseDTO`` mapping (`_case_dto`).
* Dossier-staleness check (`_dossier_is_stale`) and sender-role detector
  (`_detect_sender_role`).

Not moved in this PR (deferred to follow-ups):

* The 4 form/dossier DTO transformers (`_row_to_summary`,
  `_load_form_with_template`, `_compute_completion`,
  `_fetch_single_form_summary`) — they reference Pydantic models defined in
  ``cases.py`` (``CaseFormSummary`` etc.), so moving them requires relocating
  those models too. Tracked as a follow-up: ``case_dto_service.py``.
* The 10 PDF helpers (overlay/dossier merge/storage) — they pull in heavy
  ReportLab + pypdf dependencies that don't belong in the core service.
  Tracked as a follow-up: ``case_pdf_service.py``.

See ``backend/docs/cases-router-inventory.md`` (AUDIT-B9-cases-1) for the
full grouping and the line-count projections that motivate this split.
"""
from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import text as _sql_text

from .. import schemas
from ...database import db as main_db
from .audit_log_service import ACTOR_SYSTEM, insert_audit_log

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# ─────────────────────────────────────────────────────────────────────────────
# Dialect helpers for the Supabase-backed endpoints.
# Postgres prod uses `public.X` schema-qualified names; SQLite tests use bare.
# ─────────────────────────────────────────────────────────────────────────────

def _pg_table(name: str) -> str:
    try:
        dialect_name = main_db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def _sql_now() -> str:
    """Returns the SQL expression for current timestamp, dialect-aware."""
    try:
        dialect_name = main_db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return "now()" if dialect_name == "postgresql" else "datetime('now')"


def _sql_uuid_gen() -> str:
    """Returns a SQL expression that generates a new UUID, dialect-aware."""
    try:
        dialect_name = main_db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return "gen_random_uuid()" if dialect_name == "postgresql" else "lower(hex(randomblob(16)))"


def _pg_conn():
    """Context manager that yields a raw engine connection (dialect-agnostic helper)."""

    @contextmanager
    def _ctx():
        with main_db.engine.connect() as conn:
            yield conn

    return _ctx()


# ─────────────────────────────────────────────────────────────────────────────
# Audit & draft helpers
# ─────────────────────────────────────────────────────────────────────────────

def _audit_case(
    *,
    entity_type: str,
    entity_id: str,
    action_type: str,
    actor_type: str = ACTOR_SYSTEM,
    actor_id: Optional[str] = None,
    new_value: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one audit_logs row; never raises so callers need no try/except."""
    try:
        with main_db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type=action_type,
                actor_type=actor_type,
                actor_id=actor_id,
                new_value=new_value,
            )
    except Exception:
        logger.exception(
            "audit: failed to log %s %s entity_id=%s",
            action_type, entity_type, entity_id,
        )


def _deep_merge_case_drafts(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Merge PATCH payload into stored draft so partial saves never wipe other wizard sections."""
    out = dict(base)
    for key, val in update.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge_case_drafts(out[key], val)
        else:
            out[key] = val
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Tenant access
# ─────────────────────────────────────────────────────────────────────────────

def _assert_case_access(user: Dict[str, Any], case_id: str) -> None:
    """
    Verify the caller can read the given case.

    The ``case_id`` param may be either:
    - A UUID from ``public.cases`` (legacy seed data), or
    - An ``assignment_id`` from ``public.case_assignments`` (all real HR-created
      cases go through case_assignments; the canonical case lives in
      ``public.relocation_cases``).

    Resolution order:
    1. Try ``public.cases`` (legacy path).
    2. Try ``public.case_assignments`` → ``public.relocation_cases`` (real cases).

    Employees: must own the assignment (employee_user_id == auth uid).
    HR / Admin: sufficient to belong to the same company as the case.
    Raises 404 (case missing) or 403 (no access).

    B24-REGRESSION fail-safe: never returns 500. Malformed case_ids → 404.
    DB exceptions are logged and the affected query is treated as "no match"
    so a transient/lookup error can't cascade into a 500 on every cases.py
    endpoint downstream of this guard.
    """
    user_id = user.get("id")
    # AUTH-ID-2: a legacy/seed caller's id is a non-UUID text id, while case
    # ownership columns are uuid-typed. auth_uuid (AUTH-ID-1) is the caller's
    # canonical Supabase UUID. Match ownership against BOTH so a legacy
    # employee isn't wrongly denied access to their own case (and UUID-native
    # callers are unchanged, since for them auth_uuid == id).
    auth_uuid = user.get("auth_uuid")
    _caller_ids = {str(v) for v in (user_id, auth_uuid) if v}

    def _owns(value: Any) -> bool:
        return bool(value) and str(value) in _caller_ids

    role = (user.get("role") or "").upper()
    is_admin = user.get("is_admin") or role == "ADMIN"

    # Reject malformed IDs up-front: on Postgres a non-UUID string makes the
    # ``WHERE id = :id`` cast raise ``invalid input syntax for type uuid``,
    # which previously bubbled up as a 500.
    if not case_id or not _UUID_RE.match(case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    row = None
    try:
        with main_db.engine.connect() as conn:
            row = conn.execute(
                _sql_text(
                    f"SELECT id, company_id, employee_id, hr_owner_id "
                    f"FROM {_pg_table('cases')} WHERE CAST(id AS TEXT) = :id"
                ),
                {"id": case_id},
            ).mappings().first()
    except Exception:
        logger.exception("dossier: failed to query cases for access check id=%s", case_id)
        row = None  # fall through to assignment lookup rather than 500

    # --- assignment-based access (authoritative employee↔case link) ---
    # case_assignments carries the caller's (possibly legacy non-UUID)
    # employee_user_id and links the case via case_id / canonical_case_id. This
    # is the correct ownership signal even when public.cases.employee_id holds a
    # different (contact) UUID, or when there is no public.cases row at all.
    # Resolve by case_id / canonical_case_id (the value case-scoped routes pass)
    # AND by assignment id (legacy callers that pass an assignment_id).
    # Returns True (granted), False (assignment found, no access), None (none).
    def _assignment_access() -> Optional[bool]:
        try:
            with main_db.engine.connect() as conn:
                a = conn.execute(
                    _sql_text(
                        f"SELECT ca.employee_user_id, ca.hr_user_id, rc.company_id "
                        f"FROM {_pg_table('case_assignments')} ca "
                        f"LEFT JOIN {_pg_table('relocation_cases')} rc "
                        f"  ON CAST(rc.id AS TEXT) = CAST(ca.canonical_case_id AS TEXT) "
                        f"WHERE CAST(ca.id AS TEXT) = :id "
                        f"   OR CAST(ca.canonical_case_id AS TEXT) = :id "
                        f"   OR CAST(ca.case_id AS TEXT) = :id"
                    ),
                    {"id": case_id},
                ).mappings().first()
        except Exception:
            logger.exception("dossier: failed to resolve assignment for case id=%s", case_id)
            return None
        if a is None:
            return None
        if _owns(a.get("employee_user_id")) or _owns(a.get("hr_user_id")) or is_admin:
            return True
        if role == "HR":
            try:
                with main_db.engine.connect() as conn:
                    prof = conn.execute(
                        _sql_text(
                            f"SELECT company_id FROM {_pg_table('profiles')} WHERE CAST(id AS TEXT) = :id"
                        ),
                        {"id": str(auth_uuid or user_id or "")},
                    ).mappings().first()
                if prof and str(prof.get("company_id") or "") == str(a.get("company_id") or ""):
                    return True
            except Exception:
                logger.exception("dossier: HR profile lookup failed id=%s", user_id)
        return False

    if not row:
        granted = _assignment_access()
        if granted:
            return
        if granted is False:
            raise HTTPException(status_code=403, detail="Not authorised for this case")
        raise HTTPException(status_code=404, detail="Case not found")

    # public.cases row found — direct ownership on the row first…
    if _owns(row.get("employee_id")):
        return
    if _owns(row.get("hr_owner_id")):
        return
    if is_admin:
        return
    if role == "HR":
        try:
            with main_db.engine.connect() as conn:
                prof = conn.execute(
                    _sql_text(
                        f"SELECT company_id FROM {_pg_table('profiles')} "
                        f"WHERE id = :id"
                    ),
                    {"id": auth_uuid or user_id},
                ).mappings().first()
            if prof and str(prof.get("company_id") or "") == str(row.get("company_id") or ""):
                return
        except Exception:
            logger.exception("dossier: failed to look up HR profile company_id id=%s", user_id)

    # …then the authoritative assignment link (handles contact-UUID employee_id
    # and HR-created cases whose public.cases ownership columns differ).
    if _assignment_access():
        return
    raise HTTPException(status_code=403, detail="Not authorised for this case")


def resolve_case_forms_case_id(case_id: str) -> str:
    """
    [DOSSIER-ID] Resolve a route ``{case_id}`` to the id that ``case_forms`` rows
    are actually keyed by — the canonical relocation case id.

    Employee/HR case-scoped routes commonly pass an ``assignment_id`` (from
    ``case_assignments``), but ``case_forms.case_id`` holds the canonical case id
    (``case_assignments.canonical_case_id`` / ``case_id``). A verbatim
    ``WHERE cf.case_id = :id`` with an assignment id therefore matches nothing,
    so the Dossier renders empty even when forms exist.

    Mirrors the assignment→case resolution in ``_assert_case_access``. If no
    assignment row resolves (legacy ``public.cases`` ids), the input is returned
    unchanged. Never raises — a lookup failure falls back to the input id.
    """
    if not case_id or not _UUID_RE.match(case_id):
        return case_id
    try:
        with main_db.engine.connect() as conn:
            row = conn.execute(
                _sql_text(
                    f"SELECT COALESCE("
                    f"  NULLIF(TRIM(CAST(ca.canonical_case_id AS TEXT)), ''), "
                    f"  CAST(ca.case_id AS TEXT)"
                    f") AS resolved "
                    f"FROM {_pg_table('case_assignments')} ca "
                    f"WHERE CAST(ca.id AS TEXT) = :id "
                    f"   OR CAST(ca.canonical_case_id AS TEXT) = :id "
                    f"   OR CAST(ca.case_id AS TEXT) = :id "
                    f"LIMIT 1"
                ),
                {"id": case_id},
            ).mappings().first()
    except Exception:
        logger.exception("dossier: failed to resolve case_forms case_id id=%s", case_id)
        return case_id
    if row and row.get("resolved"):
        return str(row["resolved"])
    return case_id


# ─────────────────────────────────────────────────────────────────────────────
# DTO mapping
# ─────────────────────────────────────────────────────────────────────────────

def _case_dto(case: Any, draft: Dict[str, Any]) -> schemas.CaseDTO:
    return schemas.CaseDTO(
        id=case.id,
        status=case.status,
        draft=draft,
        createdAt=case.created_at,
        updatedAt=case.updated_at,
        originCountry=case.origin_country,
        originCity=case.origin_city,
        destCountry=case.dest_country,
        destCity=case.dest_city,
        purpose=case.purpose,
        targetMoveDate=case.target_move_date,
        flags=json.loads(case.flags_json or "{}"),
        requirementsSnapshotId=case.requirements_snapshot_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dossier-staleness + sender-role helpers
# ─────────────────────────────────────────────────────────────────────────────

def _dossier_is_stale(conn: Any, form_ids: list, generated_at: Optional[str]) -> bool:
    """
    Returns True if any FieldValue in the dossier's forms was updated after
    the dossier was last generated (generated_at).  Safe-fails to False.
    """
    if not generated_at or not form_ids:
        return False
    try:
        placeholders = ", ".join(f":fid_{i}" for i in range(len(form_ids)))
        params: Dict[str, Any] = {f"fid_{i}": fid for i, fid in enumerate(form_ids)}
        row = conn.execute(
            _sql_text(
                f"""
                SELECT updated_at
                FROM {_pg_table('case_form_field_values')}
                WHERE case_form_id IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            params,
        ).mappings().first()
        if not row or row["updated_at"] is None:
            return False
        last_ts = str(row["updated_at"])
        return last_ts > str(generated_at)
    except Exception:
        logger.debug("dossier: staleness check failed, treating as not stale")
        return False


def _detect_sender_role(user: Dict[str, Any]) -> str:
    role = (user.get("role") or "").upper()
    if role in ("HR", "ADMIN"):
        return role.lower()
    return "employee"
