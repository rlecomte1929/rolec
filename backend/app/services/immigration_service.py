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
from typing import Any, Dict, List, NamedTuple, Optional

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


class PassportDecryption(NamedTuple):
    """Result of trying to read the stored passport number back.

    `profile.passport_number` is plaintext or None. It is NEVER the ciphertext —
    that is the entire contract.
    """
    profile: Dict[str, Any]
    withheld: bool  # a value existed and could not be decrypted


def decrypt_passport_for_display(profile: Dict[str, Any]) -> PassportDecryption:
    """Return a copy of `profile` with passport_number decrypted, or WITHHELD.

    [AIQ-1802] This replaces three near-identical copies that all failed OPEN — on a
    decryption failure they left the ciphertext in place and handed it onward as though
    it were the value. It was rendered into the Article 15 subject-access PDF, shown to
    the employee as their own data, and pre-filled into an immigration form. That last
    one is the sharp end: an unreadable blob submitted on a government application is a
    different class of problem from a bad screen.

    All three were the LIVE path, because IMMIGRATION_ENCRYPTION_KEY is unset in
    production and `_get_encryption_key()` therefore raises on every call.

    Returning ciphertext is not graceful degradation. It presents unreadable data as the
    subject's real value, and every caller downstream treats it as one. So the failure
    branch yields None and says so, and the caller decides how to be honest about it —
    a blank form field, a "withheld" line in the PDF, a fallback to the value the
    employee typed themselves.

    The try/except stays: removing it would turn a display defect into a 500 on the whole
    form fill. What changed is what the branch DOES.

    The `CAST(:enc AS bytea)` form is deliberate and must survive edits — `:enc::bytea`
    makes SQLAlchemy bind a truncated parameter name and leaves a literal `:enc` in the
    SQL (AIQ-1780); it is guarded by backend/tests/test_jsonb_bind_cast.py.
    """
    p = dict(profile)
    raw = p.get("passport_number")
    if not raw:
        return PassportDecryption(profile=p, withheld=False)

    try:
        enc_key = _get_encryption_key()
        with db.engine.begin() as conn:
            row = conn.execute(
                text("SELECT pgp_sym_decrypt(CAST(:enc AS bytea), :key) AS decrypted"),
                {"enc": raw, "key": enc_key},
            ).mappings().first()
        decrypted = row["decrypted"] if row else None
        if decrypted:
            p["passport_number"] = decrypted
            return PassportDecryption(profile=p, withheld=False)
        # A NULL/absent result is a failure, not an empty passport number. Falling
        # through to the input would put the ciphertext back.
        log.warning("passport decryption returned no value; withholding")
    except Exception as exc:
        # NEVER exc_info=True here. SQLAlchemy builds its engine without
        # hide_parameters, so a DBAPI error stringifies as
        # "[parameters: ('<ciphertext>', '<encryption key>')]" — the traceback would
        # write the key that unlocks EVERY stored passport into the application log.
        # Verified against the pinned SQLAlchemy, not assumed. The exception type is
        # enough to tell a missing key from a bad ciphertext from a dead connection.
        log.warning("passport decryption failed (%s); withholding the value",
                    type(exc).__name__)

    p["passport_number"] = None
    return PassportDecryption(profile=p, withheld=True)


# ─────────────────────────────────────────────────────────────────────────────
# Consent + audit primitives
# ─────────────────────────────────────────────────────────────────────────────

def _check_consent(case_id: str, employee_id: str) -> bool:
    """Return True if immigration_processing consent is CURRENTLY held for this case+employee.

    Reads the latest ledger row and then judges it. The state test must not live in the
    WHERE clause: ``consent_records`` is append-only (a trigger blocks UPDATE and DELETE),
    so a withdrawal is a *new* row with ``consented=false``. Filtering on
    ``consented = TRUE AND withdrawn_at IS NULL`` before ``ORDER BY ... LIMIT 1`` prunes that
    withdrawal row out of the candidate set, leaving the older grant row to satisfy the
    query — which is how this answered "has any grant ever existed?" instead of "is consent
    held now?", and kept authorising processing after a withdrawal (AIQ-1803).

    Ordering first also means a re-grant after a withdrawal works: the newest row wins,
    whichever way it points.

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
                    SELECT consented, withdrawn_at
                    FROM public.consent_records
                    WHERE case_id    = :case_id
                      AND employee_id = :employee_id
                      AND purpose     = 'immigration_processing'
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"case_id": case_id, "employee_id": employee_id},
            ).mappings().first()
    except DataError:
        log.warning("immigration: consent check could not run for non-parseable id (case=%s)", case_id)
        return False
    if row is None:
        return False
    return bool(row["consented"]) and row["withdrawn_at"] is None


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

    relocation_cases is the third arm (AIQ-1831). It is the HR case of record and the
    table submit_assignment actually writes the route to (backend/main.py, via
    sync_relocation_case_route_from_wizard_draft), but it was never consulted here — so
    a case that exists ONLY in relocation_cases resolved to corridor=null even though its
    origin/dest columns were correctly populated at submit. Measured in prod 2026-08-13:
    3 of 498 submitted assignments, and zero disagreement between the three tables where
    more than one is present. It is COALESCEd LAST deliberately: it can only fire where
    the existing arms are already null, so it cannot change any answer that is correct
    today.

    It also returns origin_city / dest_city / employment_type (AIQ-1831). These are
    additive keys — no existing caller reads them — and they exist so the non-immigration
    corridor consumers can stop inventing their own resolution:

      * marketplace.py read case_assignments.origin_country / dest_country, columns that
        have never existed on that table, so its corridor was null for 100% of
        assignments since inception;
      * compat.py's missing_fields read flat origin_country / destination_country /
        employment_type off relocation_cases.profile_json, which carries none of them
        (prod: 1, 1 and 0 respectively, out of 1391 cases);
      * /api/resources/country read only wizard_cases.draft_json.relocationBasics and
        silently fell back to rendering Norway for a case with no destination.

    employment_type maps to contract_type, not assignment_type: contract_type is the
    nature of the employment contract ('permanent'), which is what compute_missing_fields
    sits beside origin/destination to ask about. assignment_type (STA/LTA/PERMANENT) is
    mobility duration and already has its own consumers.
    """
    with db.engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT ca.id, ca.case_id, ca.employee_user_id,
                       COALESCE(mc.destination_country, wc.dest_country,
                                rc.dest_country_code)    AS dest_country,
                       COALESCE(mc.origin_country,      wc.origin_country,
                                rc.origin_country_code)  AS origin_country,
                       COALESCE(wc.dest_city,   rc.dest_city)    AS dest_city,
                       COALESCE(wc.origin_city, rc.origin_city)  AS origin_city,
                       COALESCE(wc.contract_type,
                                (ca.intake_draft::jsonb ->> 'contract_type'))
                                                          AS employment_type
                FROM public.case_assignments ca
                LEFT JOIN public.mobility_cases   mc ON mc.id::text = ca.case_id
                LEFT JOIN public.wizard_cases     wc ON wc.id::text = ca.case_id
                LEFT JOIN public.relocation_cases rc ON rc.id::text = ca.case_id
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
    # Defense-in-depth: this is a fail-soft read-time overlay — a malformed
    # intake_data shape must degrade to "no prefill", never raise into the route.
    try:
        return _map_intake_to_vault_fields(intake)
    except Exception:  # noqa: BLE001
        return {}


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
    if not isinstance(profile, dict):
        profile = {}
    basics = intake.get("relocationBasics") or {}
    if not isinstance(basics, dict):
        basics = {}
    full_name = (
        profile.get("legal_full_name") or profile.get("legalFullName")
        or profile.get("full_name") or profile.get("fullName")
    )
    # Family can arrive as a dict ({"spouse": {...}}) OR — the common wizard shape —
    # a LIST of members ([{"relationship": "spouse", ...}, ...]). Handle both; a
    # bare list would otherwise crash on `.get` (AIQ-973 follow-up).
    fam = intake.get("familyMembers")
    if fam is None:
        fam = intake.get("family")
    spouse: Any = {}
    if isinstance(fam, dict):
        spouse = fam.get("spouse") or {}
    elif isinstance(fam, list):
        for member in fam:
            if not isinstance(member, dict):
                continue
            rel = str(member.get("relationship") or member.get("relation") or "").strip().lower()
            if rel in ("spouse", "partner", "husband", "wife", "married"):
                spouse = member
                break
    if not isinstance(spouse, dict):
        spouse = {}

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
