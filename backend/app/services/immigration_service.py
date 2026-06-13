"""
immigration_service.py — business-logic helpers extracted from
``backend/app/routers/immigration.py`` (AUDIT-B9-imm-2).

Pure, importable; contains **no** FastAPI route handlers. Houses:

* Timestamp + encryption-key utilities (`_now_iso`, `_ts`, `_get_encryption_key`).
* Consent + audit primitives (`_check_consent`, `_log_access`,
  `_get_case_details`).
* Immigration-case row serializer (`_serialize_imm_case`).
* Profile loaders (`_load_profile_for_case`, `_load_profile_for_case_employee`).
* Interview-session lifecycle (`_load_session`, `_load_session_for_update`,
  `_load_or_create_session`, `_save_session`).
* Encrypted-vault writer (`_apply_vault_updates`).

All helpers use the raw-SQL ``db.engine.begin()`` pattern — single-DB design,
no SQLAlchemy ORM. See ``backend/docs/immigration-split-plan.md``
(AUDIT-B9-imm-1) for the full grouping and the line-count projections that
motivate this split.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DataError

from ...database import db

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Timestamp + encryption-key utilities
# ─────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(v: Any) -> Optional[str]:
    """Coerce a datetime/string to ISO string, or None."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _get_encryption_key() -> str:
    import os
    key = os.environ.get("IMMIGRATION_ENCRYPTION_KEY", "")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="IMMIGRATION_ENCRYPTION_KEY environment variable not set.",
        )
    return key


# ─────────────────────────────────────────────────────────────────────────────
# Consent + audit primitives
# ─────────────────────────────────────────────────────────────────────────────

def _check_consent(case_id: str, employee_id: str) -> bool:
    """Return True if a valid immigration_processing consent exists for this case+employee.

    Degrades gracefully when ids don't parse: a legacy/seed account whose id is
    not a UUID (e.g. ReloPass-session text ids) can hit a uuid-typed column in
    the query path and make Postgres raise ``invalid input syntax for type uuid``.
    That has no consent match by definition, so we treat it as "no consent"
    (the caller surfaces the consent screen) rather than letting it 500.
    """
    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT id FROM public.consent_records
                    WHERE case_id    = :case_id
                      AND employee_id = :employee_id
                      AND purpose     = 'immigration_processing'
                      AND consented   = TRUE
                      AND withdrawn_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"case_id": case_id, "employee_id": employee_id},
            ).mappings().first()
    except DataError:
        log.warning("immigration: consent check could not run for non-parseable id (case=%s)", case_id)
        return False
    return row is not None


def _log_access(
    case_id: str,
    profile_id: Optional[str],
    user_id: str,
    role: str,
    action: str,
    fields: List[str],
    purpose: str = "immigration_processing",
) -> None:
    """Write an entry to data_access_log. Silently ignores errors (never block the main request)."""
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO public.data_access_log
                        (case_id, profile_id, accessed_by_user_id, accessed_by_role,
                         action, fields_accessed, purpose, accessed_at)
                    VALUES
                        (:case_id, :profile_id, :user_id, :role,
                         :action, :fields, :purpose, NOW())
                """),
                {
                    "case_id": case_id,
                    "profile_id": profile_id,
                    "user_id": user_id,
                    "role": role,
                    "action": action,
                    "fields": fields,
                    "purpose": purpose,
                },
            )
    except Exception as exc:
        log.warning("Failed to write data_access_log: %s", exc)


def _get_case_details(case_id: str, org_id: str) -> Optional[Dict[str, Any]]:
    """Fetch basic case details (corridor) from the assignment record.

    The route parameter is the case_assignments.id (PK), not case_id (FK).
    We try by PK first, then fall back to FK so the helper works in both call sites.

    Geography: HR-create cases carry origin/destination on mobility_cases; wizard /
    bridged cases (the employee-intake demo spine) carry it on wizard_cases. COALESCE
    both so a wizard case (e.g. FR→NO demo 08b7280b) resolves its corridor instead of
    reporting covered=false/corridor=null — mirroring how exception-requests resolves
    geography (AIQ-863).
    """
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT ca.id, ca.case_id, ca.employee_user_id,
                       COALESCE(mc.destination_country, wc.dest_country)   AS dest_country,
                       COALESCE(mc.origin_country,      wc.origin_country) AS origin_country
                FROM public.case_assignments ca
                LEFT JOIN public.mobility_cases mc ON mc.id::text = ca.case_id
                LEFT JOIN public.wizard_cases   wc ON wc.id::text = ca.case_id
                WHERE ca.id = :case_id OR ca.case_id = :case_id
                LIMIT 1
            """),
            {"case_id": case_id},
        ).mappings().first()
    return dict(row) if row else None


def resolve_case_corridor(case_id: str, org_id: str = "") -> Optional[str]:
    """Canonical corridor id ('FR_NO') for a case, or None. Best-effort — never
    raises; a missing case / geography just yields None so callers fall back to
    their corridor-agnostic default (I-3 Stage 3)."""
    try:
        details = _get_case_details(case_id, org_id)
        if not details:
            return None
        origin, dest = details.get("origin_country"), details.get("dest_country")
        if not origin or not dest:
            return None
        from .corridor_registry import normalize_corridor_id

        return normalize_corridor_id(f"{origin}_{dest}") or None
    except Exception:  # noqa: BLE001
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Immigration-case serializer
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_imm_case(row: Any) -> Dict[str, Any]:
    """Convert a DB row from immigration_cases to a JSON-safe dict."""
    r = dict(row)
    for col in ("created_at", "updated_at", "expected_submission_date",
                "expected_grant_date", "permit_expiry_date"):
        v = r.get(col)
        if hasattr(v, "isoformat"):
            r[col] = v.isoformat()
    # Ensure UUIDs are strings
    for col in ("id", "case_id", "created_by_hr_id"):
        if r.get(col) is not None:
            r[col] = str(r[col])
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Profile loaders
# ─────────────────────────────────────────────────────────────────────────────

def _load_profile_for_case(case_id: str) -> Optional[Dict[str, Any]]:
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT * FROM public.imm_employee_profiles
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"case_id": case_id},
        ).mappings().first()
    if not row:
        return None
    result = dict(row)
    for col in ("created_at", "updated_at", "passport_expiry", "date_of_birth",
                "employment_start_date", "retention_expires_at"):
        v = result.get(col)
        if hasattr(v, "isoformat"):
            result[col] = v.isoformat()
    return result


def _load_profile_for_case_employee(case_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT * FROM public.imm_employee_profiles
                WHERE case_id = :case_id AND employee_id = :employee_id
                LIMIT 1
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()
    if not row:
        return None
    result = dict(row)
    for col in ("created_at", "updated_at", "passport_expiry", "date_of_birth",
                "employment_start_date", "retention_expires_at"):
        v = result.get(col)
        if hasattr(v, "isoformat"):
            result[col] = v.isoformat()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Canonical intake resolution (AIQ-973 · ASK-ONCE)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_canonical_intake_fields(case_id: str) -> Dict[str, Any]:
    """ASK-ONCE: resolve already-provided identity/passport/spouse fields from the
    canonical intake store (``cases.intake_data``) and map them to the immigration
    interview's ``vault_field`` names. Used as a READ-TIME overlay so the interview
    surfaces these as pre-filled 'confirm' values instead of re-asking them as
    blank required questions. Returns ``{vault_field: value}`` for non-empty values
    only.

    Mirrors ``prefill_engine._build_context``'s intake sub-key fallbacks so the two
    inlets resolve the same source of truth. Conflict rule: the caller overlays
    this UNDER the real vault, so an OCR'd / already-answered value always wins.
    """
    import json as _json

    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT intake_data FROM public.cases WHERE id = :id"),
                {"id": case_id},
            ).mappings().first()
    except Exception:  # noqa: BLE001 — best-effort; fall back to no prefill
        return {}
    if not row or not row.get("intake_data"):
        return {}
    raw = row.get("intake_data")
    if isinstance(raw, dict):
        intake = raw
    else:
        try:
            intake = _json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(intake, dict):
        return {}
    return _map_intake_to_vault_fields(intake)


def _map_intake_to_vault_fields(intake: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapping (no I/O): intake_data dict → {interview vault_field: value} for
    the already-known identity/passport/spouse fields. Split out from the DB read
    so it's unit-testable. See :func:`_resolve_canonical_intake_fields`."""
    if not isinstance(intake, dict):
        return {}

    # profile sub-keys — same fallbacks as prefill_engine, plus wizard paths
    profile = (
        intake.get("profile")
        or intake.get("employee")
        or intake.get("personalDetails")
        or intake.get("employeeProfile")
        or intake.get("primaryApplicant")
        or {}
    )
    basics = intake.get("relocationBasics") or {}
    full_name = (
        profile.get("legal_full_name") or profile.get("legalFullName")
        or profile.get("full_name") or profile.get("fullName")
    )
    fam = intake.get("familyMembers") or intake.get("family") or {}
    spouse = fam.get("spouse") or {}

    out: Dict[str, Any] = {}
    # Name → first/last is a best-effort split, surfaced for CONFIRMATION (the user
    # can correct it), never silently committed.
    if full_name and str(full_name).strip():
        parts = str(full_name).strip().split()
        out["legal_first_name"] = parts[0]
        if len(parts) > 1:
            out["legal_last_name"] = " ".join(parts[1:])
    for vault_field, value in (
        ("date_of_birth", profile.get("date_of_birth") or profile.get("dateOfBirth")),
        ("nationality", profile.get("nationality") or basics.get("nationality")),
        ("passport_number", profile.get("passport_number") or profile.get("passportNumber")),
        ("passport_expiry", profile.get("passport_expiry") or profile.get("passportExpiry")),
        ("spouse_name", spouse.get("full_name") or spouse.get("fullName") or spouse.get("name")),
        ("spouse_dob", spouse.get("date_of_birth") or spouse.get("dateOfBirth")),
        ("spouse_nationality", spouse.get("nationality")),
    ):
        if value is not None and str(value).strip() != "":
            out[vault_field] = value
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Interview session lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def _load_session(case_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
    # See _check_consent: a non-UUID id can raise DataError against a uuid-typed
    # column in the query path. No session can exist for such an id, so degrade
    # to "no session" instead of 500.
    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT id, answers, skipped_fields, prefilled_fields,
                           completed_sections, completion_pct, current_section,
                           current_question_id, consent_record_id,
                           started_at, last_active_at, completed_at
                    FROM public.interview_sessions
                    WHERE case_id = :case_id AND employee_id = :employee_id
                    ORDER BY started_at DESC
                    LIMIT 1
                """),
                {"case_id": case_id, "employee_id": employee_id},
            ).mappings().first()
    except DataError:
        log.warning("immigration: session load could not run for non-parseable id (case=%s)", case_id)
        return None
    return dict(row) if row else None


def _load_session_for_update(case_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
    """Load session with row-level lock (FOR UPDATE) to prevent concurrent corruption."""
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT id, answers, skipped_fields, prefilled_fields,
                       completed_sections, completion_pct, current_section,
                       current_question_id, started_at, last_active_at, completed_at
                FROM public.interview_sessions
                WHERE case_id = :case_id AND employee_id = :employee_id
                ORDER BY started_at DESC
                LIMIT 1
                FOR UPDATE
            """),
            {"case_id": case_id, "employee_id": employee_id},
        ).mappings().first()
    return dict(row) if row else None


def _load_or_create_session(case_id: str, employee_id: str, org_id: str) -> Dict[str, Any]:
    """Load existing session or create a fresh one."""
    session = _load_session(case_id, employee_id)
    if session:
        return session

    session_id = str(uuid.uuid4())
    now = _now_iso()
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO public.interview_sessions
                    (id, case_id, employee_id, org_id,
                     answers, skipped_fields, prefilled_fields, completed_sections,
                     completion_pct, started_at, last_active_at, created_at, updated_at)
                VALUES
                    (:id, :case_id, :employee_id, :org_id,
                     '{}', '{}', '{}', '{}',
                     0, :now, :now, :now, :now)
            """),
            {
                "id": session_id,
                "case_id": case_id,
                "employee_id": employee_id,
                "org_id": org_id,
                "now": now,
            },
        )
    return _load_session(case_id, employee_id) or {}


def _save_session(
    session_id: str,
    answers: Dict[str, Any],
    skipped_fields: List[str],
    prefilled_fields: List[str],
    current_section: Optional[str],
    current_question_id: Optional[str],
    completed_sections: List[str],
    completion_pct: int,
    completed_at: Optional[str],
) -> None:
    import json as _json
    now = _now_iso()
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE public.interview_sessions
                SET answers              = :answers,
                    skipped_fields       = :skipped,
                    prefilled_fields     = :prefilled,
                    current_section      = :section,
                    current_question_id  = :question_id,
                    completed_sections   = :completed,
                    completion_pct       = :pct,
                    completed_at         = :completed_at,
                    last_active_at       = :now,
                    updated_at           = :now
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
                "answers": _json.dumps(answers),
                "skipped": skipped_fields,
                "prefilled": prefilled_fields,
                "section": current_section,
                "question_id": current_question_id,
                "completed": completed_sections,
                "pct": completion_pct,
                "completed_at": completed_at,
                "now": now,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Encrypted-vault writer
# ─────────────────────────────────────────────────────────────────────────────

def _apply_vault_updates(
    case_id: str,
    employee_id: str,
    vault_updates: Dict[str, Any],
    org_id: str = "",
) -> None:
    """
    Apply a dict of vault column → value updates to imm_employee_profiles.
    Creates the profile row if it doesn't exist.
    Fields already marked 'hr_provided' in field_sources are never overwritten.
    """
    now = _now_iso()
    profile = _load_profile_for_case_employee(case_id, employee_id)

    if profile:
        existing_sources: Dict[str, str] = dict(profile.get("field_sources") or {})
        set_clauses = []
        params: Dict[str, Any] = {"case_id": case_id, "employee_id": employee_id, "now": now}
        for col, val in vault_updates.items():
            if existing_sources.get(col) == "hr_provided":
                continue
            set_clauses.append(f"{col} = :{col}")
            params[col] = val
            existing_sources[col] = "interview"

        if not set_clauses:
            return

        params["field_sources"] = existing_sources
        set_clauses += ["field_sources = :field_sources", "updated_at = :now"]
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE public.imm_employee_profiles "
                    f"SET {', '.join(set_clauses)} "
                    f"WHERE case_id = :case_id AND employee_id = :employee_id"
                ),
                params,
            )
    else:
        profile_id = str(uuid.uuid4())
        field_sources = {col: "interview" for col in vault_updates}
        params = {
            "id": profile_id,
            "case_id": case_id,
            "employee_id": employee_id,
            "org_id": org_id,
            "field_sources": field_sources,
            "created_at": now,
            "updated_at": now,
            **vault_updates,
        }
        cols = list(params.keys())
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO public.imm_employee_profiles ({', '.join(cols)}) "
                    f"VALUES ({', '.join(f':{c}' for c in cols)})"
                ),
                params,
            )
