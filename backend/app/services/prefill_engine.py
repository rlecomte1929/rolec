"""
[P2-1] Pre-Fill Engine
======================
Populates case_form_field_values records when a CaseForm is first created
(or re-triggered after an upstream dependency is approved).

Source priority (highest → lowest):
  1. Structured profile   — cases.intake_data + profiles row      (source='intake_profile')
  2. Contract / employment — cases.intake_data (camelCase aliases) (source='contract')
  3. Passport / ID OCR     — imm_employee_profiles vault (OCR fields) (source='passport_ocr')
  4. Previously approved forms — donated values from the same person's
     approved case forms                                          (source='prior_form')
  5. Authority lookups    — (future: Brønnøysund API)
  6. AI inference         — (future: GPT-4o mini)

Each resolved value is tagged with a `source` (the DATA ORIGIN) written to
case_form_field_values.source, alongside a confidence. A lower-priority source
only fills a leaf that every higher source left empty — it never overrides a
value that intake already supplied. Unsourced fields stay blank: the engine
never invents a value (AIQ-1755).

Idempotency: never overwrites a FieldValue row where overridden=True.
Errors are logged but never raised — a prefill failure must not block the
primary case save or the trigger engine.

Called from trigger_engine.py after each successful CaseForm creation:

    from .prefill_engine import run_prefill
    run_prefill(case_form_id, case_uuid)

Design follows trigger_engine.py exactly:
  - Pure SQLAlchemy text() queries
  - _t() dialect helper for Postgres vs SQLite portability
  - No ORM, no HTTP calls
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .audit_log_service import ACTION_INSERT, ACTOR_SYSTEM, insert_audit_log

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source descriptors (written to case_form_field_values.source) + confidences.
# `source` is the DATA ORIGIN of a value; `filled_by` stays the coarse actor
# ('system' for everything the engine resolves). See migration
# 20261011000000_autofill_prefill_provenance_and_source_language.sql.
# ---------------------------------------------------------------------------

SOURCE_INTAKE_PROFILE = "intake_profile"
SOURCE_CONTRACT = "contract"
SOURCE_BANKING = "banking"
SOURCE_PASSPORT_OCR = "passport_ocr"
SOURCE_PRIOR_FORM = "prior_form"
SOURCE_SYSTEM = "system"

_INTAKE_CONFIDENCE = 0.99
_PASSPORT_OCR_CONFIDENCE = 0.9
_PRIOR_FORM_CONFIDENCE = 0.95

# ctx top-level key → default source for intake-origin leaves.
_KEY_SOURCE = {
    "profile": SOURCE_INTAKE_PROFILE,
    "person": SOURCE_INTAKE_PROFILE,
    "family": SOURCE_INTAKE_PROFILE,
    "contract": SOURCE_CONTRACT,
    "banking": SOURCE_BANKING,
}


# ---------------------------------------------------------------------------
# Dialect-aware table helper (mirrors trigger_engine._t)
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


def _now() -> str:
    """Return the current-timestamp SQL expression for the active dialect."""
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return "now()" if dialect_name == "postgresql" else "CURRENT_TIMESTAMP"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_prefill(case_form_id: str, case_uuid: str) -> int:
    """
    Populate FieldValue records for a single CaseForm.

    Returns the number of fields that were written (0 on re-run with no
    changes, or when no prefill_source paths resolve).
    Errors are caught and logged — never raised.
    """
    try:
        return _run(case_form_id, case_uuid)
    except Exception:
        logger.exception(
            "prefill_engine: unhandled error case_form_id=%s case_uuid=%s",
            case_form_id, case_uuid,
        )
        return 0


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _run(case_form_id: str, case_uuid: str) -> int:
    # 1. Load the CaseForm + FormTemplate fields
    form_row = _load_case_form(case_form_id)
    if not form_row:
        logger.warning("prefill_engine: case_form %s not found", case_form_id)
        return 0

    fields: List[Dict[str, Any]] = _parse_json(form_row.get("fields"))
    if not fields:
        logger.debug("prefill_engine: template has no fields, skipping cf=%s", case_form_id)
        return 0

    # 2. Build the case context (intake) + a per-path provenance map, then
    #    layer the lower-priority sources (passport OCR, prior approved forms)
    #    onto leaves the higher sources left empty. A source never overrides a
    #    value a higher source already supplied (AIQ-1755).
    context = _build_context(case_uuid, form_row.get("person_id"), form_row.get("dependent_id"))
    sources = _build_sources_map(context)
    _apply_passport_ocr(context, sources, case_uuid)
    _apply_prior_forms(context, sources, form_row.get("person_id"), case_form_id)

    # 3. Load existing field state to skip overrides and detect real changes
    overridden_ids = _load_overridden_field_ids(case_form_id)
    existing_values = _load_existing_values(case_form_id)

    # 4. Resolve each field. Track two sets:
    #    - resolved: every field the engine can fill (drives completion %)
    #    - changed:  fields whose value is genuinely new or different (drives
    #                the audit + return value, so a no-op re-run is a no-op)
    resolved_field_ids: List[str] = []
    changed_field_ids: List[str] = []
    for field in fields:
        field_id = field.get("id") or field.get("field_id")
        if not field_id:
            continue
        if field_id in overridden_ids:
            continue  # never overwrite user-edited values

        prefill_source: Optional[str] = field.get("prefill_source")
        if not prefill_source:
            continue

        value = _resolve_path(context, prefill_source)
        if value is None:
            continue

        new_value = str(value)
        resolved_field_ids.append(field_id)
        if existing_values.get(field_id) == new_value:
            continue  # already holds this exact value — no write, no change event

        # Provenance for this value: which source supplied it + its confidence.
        src_info = sources.get(prefill_source)
        _upsert_field_value(
            case_form_id=case_form_id,
            field_id=field_id,
            value=new_value,
            filled_by="system",
            ai_confidence=(src_info[1] if src_info else _INTAKE_CONFIDENCE),
            source=(src_info[0] if src_info else None),
        )
        changed_field_ids.append(field_id)

    # 5. Completion % + status reflect everything the engine can fill (so a
    #    re-run keeps the form's coverage accurate even when nothing changed).
    if resolved_field_ids:
        _update_completion(case_form_id, len(resolved_field_ids), len(fields))
        _update_status_to_auto_filled(case_form_id)

    # 6. Audit only genuine changes — no phantom pre-fill events on no-op re-runs.
    if changed_field_ids:
        _insert_prefill_audit(case_form_id, changed_field_ids)

    logger.info(
        "prefill_engine: %d changed / %d fillable / %d total for case_form_id=%s",
        len(changed_field_ids), len(resolved_field_ids), len(fields), case_form_id,
    )
    return len(changed_field_ids)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_case_form(case_form_id: str) -> Optional[Dict[str, Any]]:
    """Return case_form row joined with its template fields array."""
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT cf.id, cf.person_id, cf.dependent_id, "
                    f"       ft.fields "
                    f"FROM {_t('case_forms')} cf "
                    f"JOIN {_t('form_templates')} ft ON ft.id = cf.form_template_id "
                    f"WHERE cf.id = :id"
                ),
                {"id": case_form_id},
            ).mappings().first()
        if row:
            return dict(row)
    except Exception:
        logger.exception("prefill_engine: failed to load case_form id=%s", case_form_id)
    return None


def _load_overridden_field_ids(case_form_id: str) -> set:
    """Return the set of field_ids where overridden=true for this CaseForm."""
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT field_id FROM {_t('case_form_field_values')} "
                    f"WHERE case_form_id = :cfid AND overridden = true"
                ),
                {"cfid": case_form_id},
            ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        logger.exception("prefill_engine: failed to load overridden fields cf=%s", case_form_id)
        return set()


def _load_existing_values(case_form_id: str) -> Dict[str, Optional[str]]:
    """Return {field_id: stored value} for this CaseForm, used to detect whether
    a resolved value would actually change anything before writing."""
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT field_id, value FROM {_t('case_form_field_values')} "
                    f"WHERE case_form_id = :cfid"
                ),
                {"cfid": case_form_id},
            ).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        logger.exception("prefill_engine: failed to load existing values cf=%s", case_form_id)
        return {}


def _build_context(
    case_uuid: str,
    person_id: Optional[str],
    dependent_id: Optional[str],
) -> Dict[str, Any]:
    """
    Assemble the prefill context from multiple DB sources.

    Shape mirrors the prefill_source dotted paths used in the form template
    seed (P1-4):
      profile.*   — personal + passport data
      contract.*  — employment details
      person.*    — resolved person (employee or dependent)
      case.*      — case-level metadata
      banking.*   — bank account details
      family.*    — spouse / children
    """
    ctx: Dict[str, Any] = {
        "profile": {},
        "contract": {},
        "person": {},
        "case": {},
        "banking": {},
        "family": {"spouse": {}, "children": []},
    }

    try:
        with db.engine.connect() as conn:
            # ── cases row + intake_data ──────────────────────────────────────
            case_row = conn.execute(
                text(
                    f"SELECT dest_country_code, origin_country_code, "
                    f"       employee_id, intake_data "
                    f"FROM {_t('cases')} WHERE id = :id"
                ),
                {"id": case_uuid},
            ).mappings().first()

            if not case_row:
                return ctx

            intake: Dict[str, Any] = _parse_json(case_row.get("intake_data"))

            # ── case-level ───────────────────────────────────────────────────
            ctx["case"]["dest_country_code"] = case_row.get("dest_country_code")
            ctx["case"]["origin_country_code"] = case_row.get("origin_country_code")

            # ── profile — try multiple intake_data sub-keys ──────────────────
            profile_raw = (
                intake.get("profile")
                or intake.get("employee")
                or intake.get("personalDetails")
                or {}
            )
            ctx["profile"] = {
                "legal_full_name": (
                    profile_raw.get("legal_full_name")
                    or profile_raw.get("legalFullName")
                    or profile_raw.get("full_name")
                    or profile_raw.get("fullName")
                ),
                "date_of_birth": (
                    profile_raw.get("date_of_birth")
                    or profile_raw.get("dateOfBirth")
                ),
                "nationality": (
                    profile_raw.get("nationality")
                ),
                "passport_number": (
                    profile_raw.get("passport_number")
                    or profile_raw.get("passportNumber")
                ),
                "passport_expiry": (
                    profile_raw.get("passport_expiry")
                    or profile_raw.get("passportExpiry")
                ),
            }

            # ── contract / employment ────────────────────────────────────────
            contract_raw = (
                intake.get("contract")
                or intake.get("employment")
                or intake.get("employmentDetails")
                or {}
            )
            ctx["contract"] = {
                "employer_name": (
                    contract_raw.get("employer_name")
                    or contract_raw.get("employerName")
                ),
                "employer_org_number": (
                    contract_raw.get("employer_org_number")
                    or contract_raw.get("employerOrgNumber")
                    or contract_raw.get("orgNumber")
                ),
                "job_title": (
                    contract_raw.get("job_title")
                    or contract_raw.get("jobTitle")
                    or contract_raw.get("position")
                ),
                "salary_amount_nok": (
                    contract_raw.get("salary_amount_nok")
                    or contract_raw.get("salaryAmountNok")
                    or contract_raw.get("salary")
                    or contract_raw.get("salaryAmount")
                ),
                "employment_start_date": (
                    contract_raw.get("employment_start_date")
                    or contract_raw.get("employmentStartDate")
                    or contract_raw.get("startDate")
                ),
            }

            # ── banking ──────────────────────────────────────────────────────
            banking_raw = intake.get("banking") or intake.get("bankDetails") or {}
            ctx["banking"] = {
                "iban": banking_raw.get("iban") or banking_raw.get("IBAN"),
                "bank_name": banking_raw.get("bank_name") or banking_raw.get("bankName"),
                "account_holder": (
                    banking_raw.get("account_holder")
                    or banking_raw.get("accountHolder")
                ),
            }

            # ── person (resolved employee or dependent) ──────────────────────
            resolved_person: Dict[str, Any] = {}
            if dependent_id:
                dep_row = conn.execute(
                    text(
                        f"SELECT full_name, date_of_birth, nationality, "
                        f"       passport_expiry, relationship "
                        f"FROM {_t('case_dependents')} WHERE id = :id"
                    ),
                    {"id": dependent_id},
                ).mappings().first()
                if dep_row:
                    resolved_person = dict(dep_row)
            elif person_id and case_row.get("employee_id") and str(person_id) == str(case_row["employee_id"]):
                prof_row = conn.execute(
                    text(
                        f"SELECT full_name, email "
                        f"FROM {_t('profiles')} WHERE id = :id"
                    ),
                    {"id": person_id},
                ).mappings().first()
                if prof_row:
                    resolved_person = dict(prof_row)
                    # Supplement with richer intake profile data if available
                    if not ctx["profile"]["legal_full_name"] and resolved_person.get("full_name"):
                        ctx["profile"]["legal_full_name"] = resolved_person["full_name"]

            ctx["person"] = {
                "full_name": resolved_person.get("full_name"),
                # Alias: seed templates use person.legal_full_name for child forms
                "legal_full_name": resolved_person.get("full_name"),
                "email": resolved_person.get("email"),
                "date_of_birth": resolved_person.get("date_of_birth"),
                "nationality": resolved_person.get("nationality"),
                # passport_expiry and relationship come from case_dependents rows
                "passport_expiry": resolved_person.get("passport_expiry"),
                "relationship": resolved_person.get("relationship"),
            }

            # ── family (spouse + children from case_dependents) ──────────────
            dep_rows = conn.execute(
                text(
                    f"SELECT relationship, full_name, date_of_birth, nationality, "
                    f"       passport_expiry "
                    f"FROM {_t('case_dependents')} WHERE case_id = :cid"
                ),
                {"cid": case_uuid},
            ).mappings().fetchall()

            for d in dep_rows:
                rel = (d.get("relationship") or "").lower()
                dep_dict = {
                    "full_name": d.get("full_name"),
                    # Alias: seed templates use family.spouse.legal_full_name
                    "legal_full_name": d.get("full_name"),
                    "date_of_birth": str(d["date_of_birth"]) if d.get("date_of_birth") else None,
                    "nationality": d.get("nationality"),
                    "passport_expiry": str(d["passport_expiry"]) if d.get("passport_expiry") else None,
                }
                if rel in ("spouse", "partner"):
                    ctx["family"]["spouse"] = dep_dict
                elif rel == "child":
                    ctx["family"]["children"].append(dep_dict)

    except Exception:
        logger.exception(
            "prefill_engine: failed to build context case_uuid=%s", case_uuid
        )

    return ctx


# ---------------------------------------------------------------------------
# Provenance map + lower-priority source overlays
# ---------------------------------------------------------------------------

def _build_sources_map(ctx: Dict[str, Any]) -> Dict[str, tuple]:
    """
    Walk the intake context and tag every non-empty leaf with its data origin.

    Returns {dotted_path: (source, confidence)}. The source is derived from the
    top-level key (profile/person/family → intake_profile, contract → contract,
    banking → banking, everything else → system). Lists are not descended into —
    _resolve_path can't index them, so they never become fillable paths.
    """
    sources: Dict[str, tuple] = {}

    def walk(node: Any, prefix: str) -> None:
        if not isinstance(node, dict):
            return
        for key, val in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                walk(val, path)
            elif val is not None and not (isinstance(val, str) and not val.strip()):
                top = path.split(".")[0]
                src = _KEY_SOURCE.get(top, SOURCE_SYSTEM)
                sources[path] = (src, _INTAKE_CONFIDENCE)

    walk(ctx, "")
    return sources


def _set_path(ctx: Dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted path in ctx, creating intermediate dicts as needed."""
    parts = path.split(".")
    node = ctx
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


# vault (imm_employee_profiles) scalar column → ctx path. legal name and the
# encrypted passport_number are handled specially below.
_VAULT_SCALAR_TO_PATH = {
    "date_of_birth": "profile.date_of_birth",
    "nationality": "profile.nationality",
    "passport_expiry": "profile.passport_expiry",
}


def _apply_passport_ocr(
    ctx: Dict[str, Any],
    sources: Dict[str, tuple],
    case_uuid: str,
) -> None:
    """
    Source 3 — passport / ID OCR extractions (imm_employee_profiles vault).

    Fills identity leaves that intake left empty, from vault columns whose
    field_sources marks them 'ocr'. passport_number is decrypted only at fill
    time (Postgres + key), fail-soft. Never raises — a vault read failure must
    not break prefill.
    """
    try:
        with db.engine.connect() as conn:
            case_row = conn.execute(
                text(f"SELECT employee_id FROM {_t('cases')} WHERE id = :id"),
                {"id": case_uuid},
            ).mappings().first()
            employee_id = case_row.get("employee_id") if case_row else None
            if not employee_id:
                return
            vault = conn.execute(
                text(
                    f"SELECT legal_first_name, legal_last_name, date_of_birth, "
                    f"       nationality, passport_expiry, passport_number, "
                    f"       field_sources "
                    f"FROM {_t('imm_employee_profiles')} "
                    f"WHERE case_id = :cid AND employee_id = :eid LIMIT 1"
                ),
                {"cid": case_uuid, "eid": employee_id},
            ).mappings().first()
    except Exception:
        logger.exception(
            "prefill_engine: passport-OCR vault read failed case_uuid=%s", case_uuid
        )
        return

    if not vault:
        return

    field_sources = _parse_json(vault.get("field_sources")) or {}

    def _is_ocr(col: str) -> bool:
        return field_sources.get(col) == "ocr"

    def _fill(path: str, value: Any) -> None:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            return
        if _resolve_path(ctx, path) is not None:
            return  # a higher source already supplied it
        _set_path(ctx, path, str(value))
        sources[path] = (SOURCE_PASSPORT_OCR, _PASSPORT_OCR_CONFIDENCE)

    # Scalar OCR fields.
    for col, path in _VAULT_SCALAR_TO_PATH.items():
        if _is_ocr(col):
            _fill(path, vault.get(col))

    # Legal full name — compose from first + last when either is OCR-sourced.
    if _is_ocr("legal_first_name") or _is_ocr("legal_last_name"):
        full = " ".join(
            p for p in (vault.get("legal_first_name"), vault.get("legal_last_name")) if p
        ).strip()
        _fill("profile.legal_full_name", full)

    # Passport number — decrypt at fill time only (never logged).
    if _is_ocr("passport_number") and vault.get("passport_number"):
        decrypted = _decrypt_vault_passport(vault.get("passport_number"))
        _fill("profile.passport_number", decrypted)


def _decrypt_vault_passport(enc: Any) -> Optional[str]:
    """
    Decrypt a vault passport_number blob at fill time via pgcrypto.

    Postgres-only and gated on IMMIGRATION_ENCRYPTION_KEY; returns None on any
    failure or when no key/dialect support exists. Never raises, never logs the
    plaintext (PII discipline, CLAUDE.md).
    """
    import os

    key = os.environ.get("IMMIGRATION_ENCRYPTION_KEY", "")
    if not key:
        return None
    try:
        if db.engine.dialect.name != "postgresql":
            return None
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT pgp_sym_decrypt(:enc::bytea, :key) AS d"),
                {"enc": enc, "key": key},
            ).mappings().first()
        return row["d"] if row and row.get("d") else None
    except Exception:
        logger.warning("prefill_engine: vault passport decrypt failed")
        return None


def _apply_prior_forms(
    ctx: Dict[str, Any],
    sources: Dict[str, tuple],
    person_id: Optional[str],
    current_case_form_id: str,
) -> None:
    """
    Source 4 — previously approved forms for the same person.

    Donates values from the person's other APPROVED case forms into leaves that
    every higher source left empty. Each donated value is mapped back to a ctx
    path via its donor template field's prefill_source, so donation stays on the
    same dotted-path model the rest of the engine uses. Latest-approved wins.
    Never raises.
    """
    if not person_id:
        return
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT cfv.field_id AS field_id, cfv.value AS value, "
                    f"       ft.fields AS fields "
                    f"FROM {_t('case_forms')} cf "
                    f"JOIN {_t('form_templates')} ft ON ft.id = cf.form_template_id "
                    f"JOIN {_t('case_form_field_values')} cfv "
                    f"       ON cfv.case_form_id = cf.id "
                    f"WHERE cf.person_id = :pid "
                    f"  AND cf.status = 'approved' "
                    f"  AND cf.id <> :cur "
                    f"ORDER BY cf.updated_at DESC"
                ),
                {"pid": person_id, "cur": current_case_form_id},
            ).mappings().fetchall()
    except Exception:
        logger.exception(
            "prefill_engine: prior-form source query failed person_id=%s", person_id
        )
        return

    for r in rows:
        try:
            value = r.get("value")
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            field_id = r.get("field_id")
            path: Optional[str] = None
            for f in _parse_json(r.get("fields")) or []:
                if (f.get("id") or f.get("field_id")) == field_id:
                    path = f.get("prefill_source")
                    break
            if not path:
                continue
            if _resolve_path(ctx, path) is not None:
                continue  # a higher source (or a newer donor) already filled it
            _set_path(ctx, path, str(value))
            sources[path] = (SOURCE_PRIOR_FORM, _PRIOR_FORM_CONFIDENCE)
        except Exception:
            logger.exception(
                "prefill_engine: prior-form donation failed field=%s", r.get("field_id")
            )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_path(context: Dict[str, Any], path: str) -> Optional[Any]:
    """
    Resolve a dotted path like 'profile.passport_number' against the context.
    Returns None if any segment is missing or the final value is falsy.
    """
    parts = path.split(".")
    node: Any = context
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
        if node is None:
            return None
    # Treat empty strings as missing
    if isinstance(node, str) and not node.strip():
        return None
    return node


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def _upsert_field_value(
    case_form_id: str,
    field_id: str,
    value: str,
    filled_by: str,
    ai_confidence: float,
    source: Optional[str] = None,
) -> None:
    """
    Insert or update a case_form_field_values row.
    ON CONFLICT updates value + filled_by + ai_confidence + source but only when
    overridden is false (checked at call site, but the WHERE clause is a
    safety net for Postgres).
    """
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {_t('case_form_field_values')} "
                    f"  (case_form_id, field_id, value, filled_by, ai_confidence, source) "
                    f"VALUES (:cfid, :fid, :val, :by, :conf, :src) "
                    f"ON CONFLICT (case_form_id, field_id) DO UPDATE "
                    f"  SET value = EXCLUDED.value, "
                    f"      filled_by = EXCLUDED.filled_by, "
                    f"      ai_confidence = EXCLUDED.ai_confidence, "
                    f"      source = EXCLUDED.source, "
                    f"      updated_at = {_now()} "
                    f"WHERE {_t('case_form_field_values')}.overridden = false"
                ),
                {
                    "cfid": case_form_id,
                    "fid": field_id,
                    "val": value,
                    "by": filled_by,
                    "conf": ai_confidence,
                    "src": source,
                },
            )
    except Exception:
        logger.exception(
            "prefill_engine: failed to upsert field_value cf=%s field=%s",
            case_form_id, field_id,
        )


def _insert_prefill_audit(case_form_id: str, field_ids: List[str]) -> None:
    """
    [P2-03d] Record one audit_logs row per pre-fill event.

    Follows the established form-audit convention (entity_type='case_form',
    semantic event in new_value) rather than a bespoke action_type:
    audit_logs.action_type is CHECK-constrained to insert/update/delete, and a
    pre-fill is the system inserting field values, so the 'prefill' semantics
    live in new_value.event alongside form_id + fields_filled[]. Never raises —
    an audit failure must not break the prefill.
    """
    try:
        with db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="case_form",
                entity_id=case_form_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_SYSTEM,
                new_value={
                    "event": "prefill",
                    "form_id": case_form_id,
                    "fields_filled": field_ids,
                    "field_count": len(field_ids),
                },
            )
    except Exception:
        logger.exception(
            "prefill_engine: failed to write prefill audit cf=%s", case_form_id
        )


def _update_completion(case_form_id: str, filled: int, total: int) -> None:
    pct = min(100, round(filled / total * 100)) if total > 0 else 0
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE {_t('case_forms')} "
                    f"SET completion_pct = :pct, updated_at = {_now()} "
                    f"WHERE id = :id"
                ),
                {"pct": pct, "id": case_form_id},
            )
    except Exception:
        logger.exception(
            "prefill_engine: failed to update completion_pct cf=%s", case_form_id
        )


def _update_status_to_auto_filled(case_form_id: str) -> None:
    """
    Advance status from 'not_started' → 'auto_filled'.
    Does not overwrite statuses that are further along (in_progress, ready,
    submitted, approved, rejected).
    """
    transitioned = False
    try:
        with db.engine.begin() as conn:
            result = conn.execute(
                text(
                    f"UPDATE {_t('case_forms')} "
                    f"SET status = 'auto_filled', updated_at = {_now()} "
                    f"WHERE id = :id AND status = 'not_started'"
                ),
                {"id": case_form_id},
            )
            transitioned = (result.rowcount or 0) > 0
    except Exception:
        logger.exception(
            "prefill_engine: failed to update status cf=%s", case_form_id
        )
        return
    # [P4-4] Notify employee that form is ready for review (fire-and-forget).
    # Only on the real not_started → auto_filled transition, so dependency
    # re-fills don't re-spam the employee with "ready for review".
    if not transitioned:
        return
    try:
        from .dossier_notifications import notify_form_auto_filled  # lazy import
        notify_form_auto_filled(case_form_id)
    except Exception:
        logger.exception("prefill_engine: notify_form_auto_filled failed cf=%s", case_form_id)


# ---------------------------------------------------------------------------
# Dependency re-fill (called when an upstream CaseForm is approved)
# ---------------------------------------------------------------------------

def run_prefill_for_dependents(approved_case_form_id: str, case_uuid: str) -> int:
    """
    When a CaseForm is approved, find all CaseForms blocked by it and
    re-run prefill for each — their pre-fill context may now be richer.
    Returns total number of fields written across all dependent forms.
    """
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id FROM {_t('case_forms')} "
                    f"WHERE blocker_form_id = :bid"
                ),
                {"bid": approved_case_form_id},
            ).fetchall()
        total = 0
        for row in rows:
            total += run_prefill(str(row[0]), case_uuid)
        return total
    except Exception:
        logger.exception(
            "prefill_engine: failed to find dependents for cf=%s", approved_case_form_id
        )
        return 0


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_json(value: Any) -> Any:
    """Parse a JSON value that may already be a dict/list or a JSON string."""
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
