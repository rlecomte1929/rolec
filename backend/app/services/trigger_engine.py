"""
[P1-3] Trigger Engine
=====================
Watches roadmap events derived from a PATCH /api/cases/{id} save and
upserts CaseForm records for each matched FormTemplate.

Called inline from patch_case() in cases.py — no HTTP round-trip, no polling.

Design:
  - Declarative: re-evaluates all events on every save; idempotency comes
    from ON CONFLICT DO NOTHING on the (case_id, form_template_id,
    person_id, dependent_id) UNIQUE NULLS NOT DISTINCT constraint.
  - Two-pass: first pass creates all CaseForms, second pass wires up
    blocker_form_id for forms with blocked_by_template_code.
  - Uses db.engine (Supabase/Postgres), NOT SessionLocal (legacy SQLite wizard).

Event taxonomy (matches seed in 20260521010000_seed_norway_form_templates.sql):
  roadmap.destination_confirmed  — destination + visa type known
  roadmap.profile_completed      — profile + family composition known
  roadmap.arrival_confirmed      — employee has arrived at destination
  roadmap.contract_details_saved — employer/salary details saved (future)

for_persons values:
  "employee"   → person_id = cases.employee_id,  dependent_id = NULL
  "spouse"     → person_id = NULL, dependent_id = first spouse/partner dep
  "each_child" → person_id = NULL, dependent_id = each child dep (one row each)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from ...database import db
from .prefill_engine import run_prefill  # [P2-1] Pre-Fill Engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dialect-aware table-name helper.
# Postgres production uses schema-qualified names (public.X). The SQLite test
# harness has no schemas. Returning the bare name on SQLite keeps the same
# SQL strings portable across both backends.
# ---------------------------------------------------------------------------

def _t(name: str) -> str:
    try:
        dialect_name = db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fire_roadmap_events(
    case_id: str,
    draft: Dict[str, Any],
    derived: Dict[str, Any],
) -> int:
    """
    Derive roadmap events from the current case save, evaluate all
    FormTemplate trigger rules, and upsert CaseForms for each match.

    Returns the number of new CaseForm rows created (0 on re-trigger).
    Errors are logged but never raised — a trigger failure must never
    block the primary case save.
    """
    try:
        return _run(case_id, draft, derived)
    except Exception:
        logger.exception("trigger_engine: unhandled error for case_id=%s", case_id)
        return 0


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _run(case_id: str, draft: Dict[str, Any], derived: Dict[str, Any]) -> int:
    case_uuid = _to_uuid(case_id)
    if not case_uuid:
        logger.warning("trigger_engine: invalid case_id=%r — skipping", case_id)
        return 0

    # ── 1. Build case context from the Supabase cases row ──────────────────
    context = _build_context(case_uuid, draft, derived)
    if not context:
        return 0  # case row not found in public.cases yet

    # ── 2. Load dependents BEFORE event derivation so context can carry
    #     accurate has_spouse / has_children flags. (UTL-2011F / UTL-2011B
    #     trigger rules check these — they MUST be set before condition
    #     matching runs.)
    dependents = _load_dependents(case_uuid)
    context["has_spouse"] = any(
        d["relationship"] in ("spouse", "partner") for d in dependents
    )
    context["has_children"] = any(
        d["relationship"] == "child" for d in dependents
    )

    # ── 3. Derive which events apply right now ──────────────────────────────
    events = _derive_events(context, draft, derived)
    if not events:
        return 0

    # ── 4. Load all active form templates ──────────────────────────────────
    templates = _load_form_templates()
    if not templates:
        return 0

    # ── 5. First pass — upsert CaseForms for all matched rules ────────────
    created_ids: List[Tuple[str, str]] = []   # (case_form_id, template_code)
    for template in templates:
        trigger_rules = template.get("trigger_rules") or []
        if isinstance(trigger_rules, str):
            try:
                trigger_rules = json.loads(trigger_rules)
            except (json.JSONDecodeError, TypeError):
                trigger_rules = []

        for rule in trigger_rules:
            fired_event = rule.get("event", "")
            if fired_event not in events:
                continue
            if not _matches_conditions(rule.get("conditions") or {}, context):
                continue

            persons = _resolve_persons(
                rule.get("for_persons") or ["employee"],
                context["employee_id"],
                dependents,
            )

            for person_id, dependent_id in persons:
                cf_id = _upsert_case_form(
                    case_uuid=case_uuid,
                    form_template_id=template["id"],
                    person_id=person_id,
                    dependent_id=dependent_id,
                )
                if cf_id:
                    created_ids.append((cf_id, template["code"]))
                    logger.info(
                        "trigger_engine: created case_form id=%s template=%s case=%s",
                        cf_id, template["code"], case_id,
                    )
                    # Emit case_form.created event to the light audit log
                    # (case_events). This is the trigger-source breadcrumb the
                    # task's validation criterion calls for ("Event log shows
                    # the trigger source").
                    _emit_case_form_created(
                        case_uuid=case_uuid,
                        case_form_id=cf_id,
                        template_code=template["code"],
                        fired_event=fired_event,
                    )
                    # [P2-1] Pre-Fill Engine — populate FieldValues immediately
                    run_prefill(cf_id, case_uuid)

    # ── 6. Second pass — wire up blocker_form_id ───────────────────────────
    if created_ids:
        _resolve_blockers(case_uuid, templates)

    return len(created_ids)


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def _build_context(
    case_uuid: str,
    draft: Dict[str, Any],
    derived: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Build the condition-matching context from the Supabase cases row
    merged with the in-flight wizard draft.
    """
    try:
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, employee_id, dest_country_code, purpose "
                    f"FROM {_t('cases')} WHERE id = :id"
                ),
                {"id": case_uuid},
            ).mappings().first()
    except Exception:
        logger.exception("trigger_engine: failed to query cases id=%s", case_uuid)
        return None

    if not row:
        # Case row may not exist in cases yet (legacy wizard path)
        logger.debug("trigger_engine: case %s not found in cases — skipping", case_uuid)
        return None

    # Destination: prefer derived (from in-flight PATCH) over DB row
    dest_country = (
        (derived.get("dest_country") or "").strip()
        or (row["dest_country_code"] or "").strip()
    ).upper() or None

    # visa_type: map purpose values to trigger-rule vocabulary
    purpose = (row["purpose"] or "").strip()
    basics  = draft.get("relocationBasics") or {}
    visa_type = _purpose_to_visa_type(
        purpose or (basics.get("purpose") or "").strip()
    )

    return {
        "case_uuid":        case_uuid,
        "employee_id":      str(row["employee_id"]) if row["employee_id"] else None,
        "destination_country": dest_country,
        "visa_type":        visa_type,
        # family flags populated later from case_dependents
        "has_spouse":       False,
        "has_children":     False,
    }


def _purpose_to_visa_type(purpose: str) -> Optional[str]:
    return {
        "work":                    "skilled_worker",
        "intra_company_transfer":  "intra_company_transfer",
        "family_join":             "family_join",
        "remote_work":             "remote_work",
    }.get(purpose)


# ---------------------------------------------------------------------------
# Event derivation
# ---------------------------------------------------------------------------

def _derive_events(
    context: Dict[str, Any],
    draft: Dict[str, Any],
    derived: Dict[str, Any],
) -> set:
    """
    Return the set of event names that should be treated as fired
    given the current case state.
    """
    events: set = set()
    dest = context.get("destination_country")
    basics = draft.get("relocationBasics") or {}

    # roadmap.destination_confirmed — destination country is known
    if dest:
        events.add("roadmap.destination_confirmed")

    # roadmap.profile_completed — origin + destination + at least one
    # other meaningful field is present
    origin = (
        (derived.get("origin_country") or "").strip()
        or (basics.get("originCountry") or "").strip()
    )
    if dest and origin:
        events.add("roadmap.profile_completed")

    # roadmap.contract_details_saved — employer name is known
    contract = draft.get("contract") or draft.get("employmentDetails") or {}
    if contract.get("employerName") or contract.get("employer_name"):
        events.add("roadmap.contract_details_saved")

    # roadmap.arrival_confirmed — employee has physically arrived
    arrival = draft.get("arrival") or {}
    if arrival.get("confirmed") or arrival.get("actualMoveDate") or arrival.get("actual_move_date"):
        events.add("roadmap.arrival_confirmed")

    return events


# ---------------------------------------------------------------------------
# Condition matching
# ---------------------------------------------------------------------------

def _matches_conditions(conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Check each condition key/value against the case context.
    All conditions must match (implicit AND).
    """
    for key, expected in conditions.items():
        actual = context.get(key)
        if actual is None:
            return False
        if isinstance(expected, bool):
            if bool(actual) != expected:
                return False
        else:
            if str(actual).lower() != str(expected).lower():
                return False
    return True


# ---------------------------------------------------------------------------
# Person resolution
# ---------------------------------------------------------------------------

def _load_dependents(case_uuid: str) -> List[Dict[str, Any]]:
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, relationship FROM {_t('case_dependents')} "
                    "WHERE case_id = :cid"
                ),
                {"cid": case_uuid},
            ).mappings().all()
        return [{"id": str(r["id"]), "relationship": r["relationship"]} for r in rows]
    except Exception:
        logger.exception("trigger_engine: failed to load dependents case=%s", case_uuid)
        return []


def _resolve_persons(
    for_persons: List[str],
    employee_id: Optional[str],
    dependents: List[Dict[str, Any]],
) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    Resolve for_persons tags to (person_id, dependent_id) tuples.
    Returns a list because "each_child" produces one entry per child.
    """
    result: List[Tuple[Optional[str], Optional[str]]] = []
    for tag in for_persons:
        if tag == "employee":
            result.append((employee_id, None))

        elif tag == "spouse":
            spouses = [
                d for d in dependents
                if d["relationship"] in ("spouse", "partner")
            ]
            for s in spouses:
                result.append((None, s["id"]))

        elif tag == "each_child":
            children = [
                d for d in dependents
                if d["relationship"] == "child"
            ]
            for c in children:
                result.append((None, c["id"]))

        else:
            # Unknown tag — treat as employee
            logger.warning("trigger_engine: unknown for_persons tag %r", tag)
            result.append((employee_id, None))

    return result if result else [(employee_id, None)]


# ---------------------------------------------------------------------------
# CaseForm upsert
# ---------------------------------------------------------------------------

def _load_form_templates() -> List[Dict[str, Any]]:
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, code, trigger_rules "
                    f"FROM {_t('form_templates')} "
                    "ORDER BY created_at"
                )
            ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("trigger_engine: failed to load form_templates")
        return []


def _upsert_case_form(
    case_uuid: str,
    form_template_id: str,
    person_id: Optional[str],
    dependent_id: Optional[str],
) -> Optional[str]:
    """
    Insert a CaseForm row, ignoring conflicts (idempotent).
    Returns the new row's id, or None if the row already existed.
    """
    new_id = str(uuid.uuid4())
    try:
        with db.engine.begin() as conn:
            # ON CONFLICT clause differs slightly between Postgres and SQLite:
            # Postgres uses the named constraint; SQLite uses the index columns.
            # Both end up routed to the same dedup logic; SQLite's COALESCE-based
            # index in the test schema emulates UNIQUE NULLS NOT DISTINCT.
            try:
                dialect_name = db.engine.dialect.name
            except Exception:
                dialect_name = "postgresql"
            if dialect_name == "postgresql":
                on_conflict = (
                    "ON CONFLICT ON CONSTRAINT case_forms_unique_person_dep DO NOTHING"
                )
            else:
                on_conflict = (
                    "ON CONFLICT (case_id, form_template_id, "
                    "COALESCE(person_id, '__null__'), "
                    "COALESCE(dependent_id, '__null__')) DO NOTHING"
                )
            result = conn.execute(
                text(
                    f"INSERT INTO {_t('case_forms')} "
                    "  (id, case_id, form_template_id, person_id, dependent_id, status) "
                    "VALUES "
                    "  (:id, :case_id, :ftid, :pid, :did, 'not_started') "
                    f"{on_conflict} "
                    "RETURNING id"
                ),
                {
                    "id":     new_id,
                    "case_id": case_uuid,
                    "ftid":   str(form_template_id),
                    "pid":    person_id,
                    "did":    dependent_id,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
    except Exception:
        logger.exception(
            "trigger_engine: upsert failed case=%s template=%s",
            case_uuid, form_template_id,
        )
        return None


# ---------------------------------------------------------------------------
# Blocker resolution (second pass)
# ---------------------------------------------------------------------------

def _resolve_blockers(case_uuid: str, templates: List[Dict[str, Any]]) -> None:
    """
    For any CaseForm whose template has blocked_by_template_code set,
    find the blocking CaseForm's id and write it to blocker_form_id.
    Sets status = 'not_started' (already the default, but explicit is safe).
    """
    # Build code → id map for templates that might be blockers
    code_to_template_id: Dict[str, str] = {
        t["code"]: str(t["id"]) for t in templates
    }

    # Find templates that have a blocking dependency
    blocking_pairs: List[Tuple[str, str]] = []  # (blocked_template_code, blocker_template_code)
    for t in templates:
        rules = t.get("trigger_rules") or []
        if isinstance(rules, str):
            try:
                rules = json.loads(rules)
            except (json.JSONDecodeError, TypeError):
                rules = []
        for rule in rules:
            blocker_code = rule.get("blocked_by_template_code")
            if blocker_code:
                blocking_pairs.append((t["code"], blocker_code))

    if not blocking_pairs:
        return

    try:
        with db.engine.begin() as conn:
            for blocked_code, blocker_code in blocking_pairs:
                blocked_tmpl_id = code_to_template_id.get(blocked_code)
                blocker_tmpl_id = code_to_template_id.get(blocker_code)
                if not blocked_tmpl_id or not blocker_tmpl_id:
                    continue

                # Find the blocker CaseForm for this case
                blocker_row = conn.execute(
                    text(
                        f"SELECT id FROM {_t('case_forms')} "
                        "WHERE case_id = :cid AND form_template_id = :ftid "
                        "LIMIT 1"
                    ),
                    {"cid": case_uuid, "ftid": blocker_tmpl_id},
                ).fetchone()

                if not blocker_row:
                    continue

                # Update blocked CaseForms to point at the blocker
                # IS DISTINCT FROM is Postgres-only; SQLite uses != with COALESCE
                try:
                    dialect_name = db.engine.dialect.name
                except Exception:
                    dialect_name = "postgresql"
                distinct_clause = (
                    "blocker_form_id IS DISTINCT FROM :bfid"
                    if dialect_name == "postgresql"
                    else "(blocker_form_id IS NULL OR blocker_form_id != :bfid)"
                )
                conn.execute(
                    text(
                        f"UPDATE {_t('case_forms')} "
                        "SET blocker_form_id = :bfid "
                        "WHERE case_id = :cid "
                        "  AND form_template_id = :ftid "
                        f"  AND {distinct_clause}"
                    ),
                    {
                        "bfid": str(blocker_row[0]),
                        "cid":  case_uuid,
                        "ftid": blocked_tmpl_id,
                    },
                )
    except Exception:
        logger.exception(
            "trigger_engine: blocker resolution failed case=%s", case_uuid
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _to_uuid(value: str) -> Optional[str]:
    """Validate and normalise a UUID string. Returns None if invalid."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Event emission (light audit log)
# ---------------------------------------------------------------------------

def _emit_case_form_created(
    case_uuid: str,
    case_form_id: str,
    template_code: str,
    fired_event: str,
) -> None:
    """
    Write a `case_form.created` row to public.case_events. Never raises —
    a failed audit write must not block CaseForm creation.

    case_events.case_id is TEXT (legacy schema) so the uuid is coerced.
    actor_user_id is NULL because the trigger fires from inline server
    code, not on behalf of a specific user (the PATCH itself records the
    user-actor audit separately).
    """
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {_t('case_events')} "
                    "  (case_id, event_type, description) "
                    "VALUES "
                    "  (:case_id, 'case_form.created', :description)"
                ),
                {
                    "case_id":     str(case_uuid),
                    "description": (
                        f"Created CaseForm {case_form_id} from template "
                        f"{template_code} (triggered by {fired_event})"
                    ),
                },
            )
    except Exception:
        logger.exception(
            "trigger_engine: failed to emit case_form.created event "
            "case=%s template=%s", case_uuid, template_code,
        )
