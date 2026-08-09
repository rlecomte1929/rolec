"""
cases_write.py — POST/PATCH/PUT mutation handlers extracted from cases.py
(AUDIT-B9-cases-4 / AIQ-452).

Covers 14 mutation endpoints — §6 HR mutations (1) and §8 wizard/draft/dossier
mutations (13) per `backend/docs/cases-router-inventory.md`. The DELETE handler
for dossiers (`delete_dossier`) belongs to cases_admin.py and is intentionally
not in this module.

Pydantic models and private helpers (PDF / form summary / dossier storage) are
imported from cases.py — the canonical source until cases-6 — instead of being
duplicated. When cases-6 retires cases.py, those helpers will move into
`app/services/case_service.py` and the imports below will be updated in lockstep.

DORMANT: this router is NOT yet wired into backend/app/main.py.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import text as _sql_text

from .. import crud, schemas
from ..auth_deps import get_current_user
from ..db import SessionLocal
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
    insert_audit_log,
)
from ..services.case_service import (
    _assert_case_access,
    _audit_case,
    _case_dto,
    _deep_merge_case_drafts,
    _detect_sender_role,
    _pg_table,
    _sql_now,
    _sql_uuid_gen,
)
from ..services.prefill_engine import run_prefill_for_dependents
from ..services.relocation_plan_view_service import invalidate_relocation_plan_cache
from ..services.requirements_builder import compute_case_requirements
from ..services.requirements_purpose_key import assignment_type_from_purpose, to_purpose
from ..services.research import run_country_research
from ..services.test_drive_corridor import resolve_test_drive_route
from ..services.trigger_engine import fire_roadmap_events
from ...database import db as main_db

# Pydantic models + private helpers borrowed from cases.py.
# cases.py remains the canonical source of these definitions until cases-6,
# so importing keeps the two routers in lock-step instead of diverging.
from .cases_read import FormDocumentItem
from .cases import (
    BulkFieldUpdatePayload,
    CaseFormSummary,
    CommentCreate,
    CommentItem,
    CreateDossierPayload,
    DossierPackageDetailResponse,
    DossierPackageResponse,
    FlagPatchPayload,
    FormFlagResponse,
    FormStatusPatchPayload,
    HouseholdPayload,
    RegisterPrefilledPayload,
    _MessageBody,
    _QuoteRequestBody,
    _build_cover_page,
    _build_divider_page,
    _compute_completion,
    _fetch_form_pdf_bytes,
    _fetch_single_form_summary,
    _load_form_with_template,
    _merge_pdfs,
    _try_store_dossier_pdf,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _canonical_purpose(raw: Any) -> Any:
    """Normalise the relocation purpose ON WRITE.

    `purpose` is the other half of the requirements catalog key, and it is matched
    with `==`. Nothing validated it: three intakes wrote three vocabularies into a
    free-text field, and 616 of 780 production cases ended up with a purpose the
    catalog had never heard of — returning an empty requirements list that reads as
    "nothing is required of you".

    `_assignment_derived` below has normalised assignmentType on write since
    AIQ-1349. Purpose never got the same treatment. This is that.

    Keep accepting the messy values (an intake sending "Employment" or "lta" must
    not 400), but store the canonical one. An unresolvable value is stored AS-IS
    rather than dropped: the read path fails closed on it (`to_purpose` -> None ->
    "not covered"), and silently discarding it would destroy the only evidence of a
    new bad vocabulary.
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw
    return to_purpose(raw) or raw


def _assignment_derived(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Extract assignment-type signals from a case draft for the canonical-case
    bridge (AIQ-1349). Normalizes ``assignmentType`` to upper-case (STA / LTA /
    PERMANENT) and coerces ``expectedDurationMonths`` to int. These feed both the
    ``derived`` dict and the new ``public.cases`` columns so the (already
    STA/LTA-aware) policy resolver and roadmap generation can branch on them.
    Returns ``None`` values when absent so the deep-merge never clobbers.

    Also RECOVERS the assignment type when it is hiding in the purpose field. 272
    production cases store `lta`/`sta`/`permanent` as their relocation purpose
    while ``assignmentContext.assignmentType`` sits empty — the value is in the
    wrong axis. Recovering it here writes it to its proper home, so the STA waiver
    logic (which has never once fired in production) works from now on. An explicit
    assignmentType always wins; we only fill a hole."""
    ac = draft.get("assignmentContext") or {}
    at = ac.get("assignmentType")
    at = at.strip().upper() if isinstance(at, str) and at.strip() else None
    if not at:
        at = assignment_type_from_purpose(
            (draft.get("relocationBasics", {}) or {}).get("purpose")
        )
        if at:
            # Persist it into the draft, not just the derived column: apply_rules
            # reads draft["assignmentContext"]["assignmentType"], and the purpose
            # column is canonicalised on write, so the raw signal would otherwise
            # be lost the moment it is stored.
            draft.setdefault("assignmentContext", {})["assignmentType"] = at
    dur = ac.get("expectedDurationMonths")
    try:
        dur = int(dur) if dur is not None and str(dur).strip() != "" else None
    except (TypeError, ValueError):
        dur = None
    # AIQ-1603: carry the single-select commute preference onto public.cases.
    commute = ac.get("commutePreference")
    commute = commute if isinstance(commute, str) and commute.strip() else None
    return {"assignment_type": at, "expected_duration_months": dur, "commute_preference": commute}


# ─────────────────────────────────────────────────────────────────────────────
# Mutation handlers (14 total — 6× POST, 7× PATCH, 1× PUT)
# Order preserved from cases.py source.
# ─────────────────────────────────────────────────────────────────────────────


@router.patch("/{case_id}", response_model=schemas.CaseDTO)
def patch_case(
    case_id: str,
    patch: schemas.CaseDraftDTO,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user),
):
    with SessionLocal() as db:
        # Filter out None sections so partial payloads (e.g. from E2E runner) don't
        # overwrite existing draft sections with null.
        incoming = {k: v for k, v in patch.model_dump(mode="json").items() if v is not None}
        # TD-FIX-7 (AIQ-1510): a test-drive case is pinned to its session's corridor.
        # This is the real tamper surface — the employee intake submits the route here,
        # and a UI lock can be bypassed — so whatever the client sent for origin/
        # destination is overridden server-side. Applied to `incoming` (before the
        # create-vs-merge branch below) so it also covers the create-on-missing path,
        # which skips _assert_case_access. resolve_test_drive_route returns None for
        # every real user, leaving their route untouched.
        if incoming.get("relocationBasics"):
            td_route = resolve_test_drive_route(user)
            if td_route:
                incoming["relocationBasics"] = {
                    **incoming["relocationBasics"],
                    "originCountry": td_route["home_country"],
                    "originCity": td_route["home_city"],
                    "destCountry": td_route["host_country"],
                    "destCity": td_route["host_city"],
                }
        case = crud.get_case(db, case_id)
        if not case:
            # SEC-CASES-2: create-on-missing path — authentication (above) is the
            # gate; a brand-new case can't be access-checked. Preserves the
            # wizard's create-via-PATCH flow.
            case = crud.create_case(db, case_id, incoming)
            draft = incoming
        else:
            # SEC-CASES-2: existing case — enforce ownership / tenant access.
            _assert_case_access(user, case_id)
            try:
                existing = json.loads(case.draft_json or "{}")
            except (json.JSONDecodeError, TypeError, ValueError):
                existing = {}
            if not isinstance(existing, dict):
                existing = {}
            draft = _deep_merge_case_drafts(existing, incoming)
        basics = draft.get("relocationBasics", {})
        derived = {
            "origin_country": basics.get("originCountry"),
            "origin_city": basics.get("originCity"),
            "dest_country": basics.get("destCountry"),
            "dest_city": basics.get("destCity"),
            "purpose": _canonical_purpose(basics.get("purpose")),
            "target_move_date": basics.get("targetMoveDate"),
            **_assignment_derived(draft),  # AIQ-1349: assignment_type + duration
        }
        flags = {
            "hasDependents": basics.get("hasDependents"),
        }
        case = crud.update_case(db, case, draft, derived, flags)
        try:
            main_db.apply_wizard_patch_side_effects(case_id, draft, derived)
        except Exception:
            logger.exception("apply_wizard_patch_side_effects failed case_id=%s", case_id)
        # P1-3: Trigger Engine — auto-create CaseForms for matched templates.
        # [AIQ-1379 follow-up] fire_roadmap_events is heavy (~8s on prod) and was both slowing the wizard
        # save and (cold) 5xx-ing it. Defer it OFF the response path (like the assign endpoint) so the PATCH
        # returns the saved draft immediately; the roadmap events fire after the response and FastAPI logs
        # any background exception. The draft is already committed, so this is safe.
        background_tasks.add_task(fire_roadmap_events, case_id, draft, derived)
        # invalidate stays synchronous (it's fast) so the next read is fresh — but never 5xx the save.
        try:
            invalidate_relocation_plan_cache(case_id=case_id)
        except Exception:
            logger.exception("invalidate_relocation_plan_cache failed case_id=%s", case_id)
        _audit_case(entity_type="case", entity_id=case_id, action_type=ACTION_UPDATE)
        return _case_dto(case, draft)


@router.patch("/{case_id}/relocationBasics", response_model=schemas.CaseDTO)
def patch_case_relocation_basics(
    case_id: str,
    basics: schemas.RelocationBasicsDTO,
    user: Dict[str, Any] = Depends(get_current_user),
) -> schemas.CaseDTO:
    """Alias endpoint: wraps RelocationBasicsDTO into CaseDraftDTO (B17/WZ1a)."""
    wrapped = schemas.CaseDraftDTO(relocationBasics=basics)
    return patch_case(case_id, wrapped, user)


@router.patch("/{case_id}/serviceSelections", response_model=schemas.CaseDTO)
def patch_case_service_selections(
    case_id: str,
    body: schemas.CaseDraftDTO,
    user: Dict[str, Any] = Depends(get_current_user),
) -> schemas.CaseDTO:
    """Alias endpoint: accepts service selections payload (B19/WZ2)."""
    return patch_case(case_id, body, user)


@router.post("/{case_id}/research/start")
def start_research(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        # SEC-CASES-2: enforce ownership / tenant access before kicking off research.
        _assert_case_access(user, case_id)
        draft = json.loads(case.draft_json)
        basics = draft.get("relocationBasics", {})
        dest_country = basics.get("destCountry")
        if not dest_country:
            raise HTTPException(status_code=400, detail="Destination country required")

    run_country_research(dest_country, basics.get("purpose", "employment"), {})
    _audit_case(entity_type="case", entity_id=case_id, action_type=ACTION_UPDATE, new_value={"event": "research_started"})
    return {"jobId": str(uuid.uuid4())}


@router.post("/{case_id}/roadmap/validate")
def validate_roadmap(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Employee validates their roadmap (the 'start tasks' checkpoint). Idempotent."""
    _assert_case_access(user, case_id)
    # [AIQ-1606] "Under HR review" is a non-blocking, informational tag — the employee can
    # validate and start tasks while HR reviews. No action gate here.
    result = main_db.upsert_roadmap_validation(case_id, str(user.get("id") or ""))
    # Invalidate the cached plan view so the validated state shows immediately.
    try:
        invalidate_relocation_plan_cache(case_id)
    except Exception:
        pass
    _audit_case(
        entity_type="case", entity_id=case_id, action_type=ACTION_UPDATE,
        new_value={"event": "roadmap_validated"},
    )
    # [CASE_STATUS_CHANGED] Notify the assigned HR that the employee validated
    # their roadmap and started tasks — a real case-status milestone HR cares
    # about that previously fired nothing (the type was defined + had a settings
    # toggle but was never emitted anywhere). Recipient is HR, not the employee,
    # because this is the employee's own action. Best-effort: never fail the
    # validate. Mirrors the INTAKE_SUBMITTED → HR notify (AIQ-1342).
    try:
        assignment = main_db.get_assignment_by_case_id(case_id) or {}
        hr_user_id = assignment.get("hr_user_id")
        if hr_user_id:
            assignment_id = str(assignment.get("id") or "")
            emp_name = (
                assignment.get("employee_full_name")
                or assignment.get("employee_first_name")
                or "Your employee"
            )
            main_db.create_notification_with_preferences(
                user_id=hr_user_id,
                type_="CASE_STATUS_CHANGED",
                title="Employee started their relocation",
                body=f"{emp_name} validated their roadmap and started their tasks.",
                assignment_id=assignment_id or None,
                case_id=case_id,
                metadata={"event": "roadmap_validated", "case_id": case_id},
            )
    except Exception as exc:
        logger.warning(
            "validate_roadmap: HR notification failed case_id=%s error=%s",
            case_id, str(exc), exc_info=True,
        )
    return {
        "roadmap_validated": True,
        "roadmap_validated_at": result["validated_at"],
        "roadmap_validated_by": result["validated_by_user_id"],
    }


@router.post("/{case_id}/create")
def create_case(
    case_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        # SEC-CASES-2: enforce ownership / tenant access before finalising.
        _assert_case_access(user, case_id)

        draft = json.loads(case.draft_json)
        basics = draft.get("relocationBasics", {})
        missing = []
        for key in ["originCountry", "originCity", "destCountry", "destCity", "purpose", "targetMoveDate"]:
            if not basics.get(key):
                missing.append(f"relocationBasics.{key}")
        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Missing minimum required fields",
                    "missingFields": missing,
                    "suggestedStep": 1,
                },
            )

        requirements = compute_case_requirements(case_id)

        snapshot_id = str(uuid.uuid4())
        crud.create_snapshot(
            db,
            {
                "id": snapshot_id,
                "case_id": case_id,
                "dest_country": basics.get("destCountry"),
                "purpose": _canonical_purpose(basics.get("purpose")),
                "created_at": datetime.utcnow(),
                "snapshot_json": requirements.model_dump_json(),
                "sources_json": json.dumps([source.model_dump(mode="json") for source in requirements.sources]),
            },
        )

        case.status = "CREATED"
        case.requirements_snapshot_id = snapshot_id
        db.commit()

    _audit_case(entity_type="case", entity_id=case_id, action_type=ACTION_UPDATE, new_value={"status": "CREATED"})
    try:
        from ..services.analytics_service import emit_event, EVENT_CASE_CREATED
        req_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        emit_event(
            EVENT_CASE_CREATED,
            request_id=req_id,
            case_id=case_id,
            canonical_case_id=case_id,
            extra={"requirementsSnapshotId": snapshot_id},
        )
    except Exception:
        pass

    return {"createdCaseId": case_id, "requirementsSnapshotId": snapshot_id}


@router.post("/{case_id}/household")
def update_household(
    case_id: str,
    payload: HouseholdPayload,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 1b: Save structured household (family members + pets) to the case draft.
    Merges into familyMembers and pets sections of the draft.
    """
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        try:
            draft = json.loads(case.draft_json or "{}")
        except Exception:
            draft = {}

        if payload.family_members is not None:
            members = [m.model_dump(mode="json", exclude_none=True) for m in payload.family_members]
            spouse = next((m for m in members if m.get("type") == "spouse"), None)
            children = [m for m in members if m.get("type") == "child"]

            existing_family = draft.get("familyMembers", {})
            if spouse:
                existing_family["spouse"] = {
                    "fullName": spouse.get("full_name"),
                    "nationality": spouse.get("nationality"),
                    "dateOfBirth": spouse.get("date_of_birth"),
                }
                existing_family["maritalStatus"] = "partner_kids" if children else "partner"
            if children:
                existing_family["children"] = [
                    {
                        "fullName": c.get("full_name"),
                        "nationality": c.get("nationality"),
                        "dateOfBirth": c.get("date_of_birth"),
                    }
                    for c in children
                ]
                if not spouse:
                    existing_family["maritalStatus"] = "kids_only"
            if not spouse and not children:
                existing_family["maritalStatus"] = "solo"

            draft["familyMembers"] = existing_family

        if payload.pets is not None:
            draft["pets"] = [p.model_dump(mode="json", exclude_none=True) for p in payload.pets]
            basics = draft.get("relocationBasics", {})
            basics["hasDependents"] = bool(
                (draft.get("familyMembers") or {}).get("maritalStatus", "solo") != "solo"
                or draft.get("pets")
            )
            draft["relocationBasics"] = basics

        basics = draft.get("relocationBasics", {})
        derived = {
            "origin_country": basics.get("originCountry"),
            "origin_city": basics.get("originCity"),
            "dest_country": basics.get("destCountry"),
            "dest_city": basics.get("destCity"),
            "purpose": _canonical_purpose(basics.get("purpose")),
            "target_move_date": basics.get("targetMoveDate"),
            **_assignment_derived(draft),  # AIQ-1349: assignment_type + duration
        }
        flags = {"hasDependents": basics.get("hasDependents")}
        crud.update_case(db, case, draft, derived, flags)
        # Sync family -> case_dependents and re-fire the trigger so the
        # family-reunion forms generate from the household step (the basics PATCH
        # can't, because the family isn't known yet at that point).
        try:
            main_db.apply_wizard_patch_side_effects(case_id, draft, derived)
        except Exception:
            logger.exception("update_household: side-effects failed case_id=%s", case_id)
        fire_roadmap_events(case_id, draft, derived)
        invalidate_relocation_plan_cache(case_id=case_id)

    _audit_case(
        entity_type="case",
        entity_id=case_id,
        action_type=ACTION_UPDATE,
        actor_type=ACTOR_HUMAN,
        actor_id=user.get("id") or user.get("sub"),
        new_value={"event": "household_updated"},
    )
    return {
        "case_id": case_id,
        "household_updated": True,
        "family_member_count": len(payload.family_members or []),
        "pet_count": len(payload.pets or []),
    }


@router.put("/{case_id}/forms/{form_id}/fields", response_model=CaseFormSummary)
def bulk_update_form_fields(
    case_id: str,
    form_id: str,
    payload: BulkFieldUpdatePayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> CaseFormSummary:
    """
    Bulk upsert field values. Each field is written with filled_by='employee'
    and reviewed=True. AI-filled values get overridden=True. Recomputes
    completion_pct and returns the updated CaseFormSummary.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.begin() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            # [P4-6] Fetch value and ai_confidence for override audit logging
            existing_rows = conn.execute(
                _sql_text(f"SELECT field_id, filled_by, value, ai_confidence "
                          f"FROM {_pg_table('case_form_field_values')} WHERE case_form_id=:form_id"),
                {"form_id": form_id},
            ).mappings().all()
            existing_by_field: Dict[str, Any] = {
                str(r["field_id"]): dict(r) for r in existing_rows
            }

            _role = (user.get("role") or "employee").lower()
            _overridden_by = "specialist" if _role in ("hr", "admin", "specialist") else "employee"
            _form_template_id = str(form_row.get("template_id") or "")

            for item in payload.fields:
                fid = item.field_id
                prev = existing_by_field.get(fid) or {}
                # A machine-filled value is one the prefill engine wrote. The
                # engine tags provenance via filled_by='system' (and legacy 'ai'),
                # so both count — otherwise an employee edit to a system-prefilled
                # value would leave overridden=false and a later prefill re-run
                # could clobber it (AIQ-1756: keep provenance coherent).
                was_machine = prev.get("filled_by") in ("ai", "system")
                overridden = was_machine

                cf_tbl = _pg_table('case_form_field_values')
                conn.execute(
                    _sql_text(
                        f"INSERT INTO {cf_tbl} "
                        f"(id, case_form_id, field_id, value, filled_by, reviewed, overridden, updated_at) "
                        f"VALUES ({_sql_uuid_gen()}, :form_id, :field_id, :value, "
                        f"'employee', TRUE, :overridden, {_sql_now()}) "
                        f"ON CONFLICT (case_form_id, field_id) DO UPDATE "
                        f"SET value=EXCLUDED.value, filled_by='employee', reviewed=TRUE, "
                        f"overridden=CASE WHEN {cf_tbl}.filled_by IN ('ai','system') THEN TRUE "
                        f"ELSE {cf_tbl}.overridden END, updated_at={_sql_now()}"
                    ),
                    {"form_id": form_id, "field_id": fid, "value": item.value,
                     "overridden": overridden},
                )

                # [P4-6] Capture override audit record when replacing a machine value
                if was_machine and _form_template_id:
                    try:
                        conn.execute(
                            _sql_text(
                                f"INSERT INTO {_pg_table('field_value_overrides')} "
                                f"(id, case_form_id, form_template_id, field_id, "
                                f"original_value, corrected_value, original_confidence, "
                                f"overridden_by, created_at) "
                                f"VALUES ({_sql_uuid_gen()}, :form_id, :tmpl_id, :field_id, "
                                f":orig_val, :new_val, :orig_conf, :overridden_by, {_sql_now()})"
                            ),
                            {"form_id": form_id, "tmpl_id": _form_template_id, "field_id": fid,
                             "orig_val": prev.get("value"), "new_val": item.value,
                             "orig_conf": prev.get("ai_confidence"), "overridden_by": _overridden_by},
                        )
                    except Exception:
                        logger.exception(
                            "fields: failed to capture override audit cf=%s field=%s",
                            form_id, fid,
                        )

            raw_fields = form_row.get("template_fields") or []
            if isinstance(raw_fields, str):
                try:
                    raw_fields = json.loads(raw_fields)
                except (json.JSONDecodeError, TypeError):
                    raw_fields = []

            all_fv = conn.execute(
                _sql_text(f"SELECT field_id, value FROM {_pg_table('case_form_field_values')} "
                          f"WHERE case_form_id=:form_id"),
                {"form_id": form_id},
            ).mappings().all()
            stored_values: Dict[str, str] = {
                str(r["field_id"]): (r["value"] or "") for r in all_fv
            }
            pct = _compute_completion(raw_fields, stored_values)

            # Advance status from not_started → in_progress when the employee first saves
            current_status = str(form_row.get("status") or "")
            new_status = "in_progress" if current_status == "not_started" else current_status
            conn.execute(
                _sql_text(
                    f"UPDATE {_pg_table('case_forms')} SET completion_pct=:pct, "
                    f"status=:status, updated_at={_sql_now()} WHERE id=:form_id"
                ),
                {"pct": pct, "status": new_status, "form_id": form_id},
            )

            try:
                insert_audit_log(
                    conn,
                    entity_type="case_form",
                    entity_id=form_id,
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=user.get("id") or user.get("sub"),
                    new_value={"event": "fields_updated", "field_count": len(payload.fields)},
                )
            except Exception:
                logger.exception("audit: bulk_update_form_fields cf=%s", form_id)

    except HTTPException:
        raise
    except Exception:
        logger.exception("fields: bulk update failed case_id=%s form_id=%s", case_id, form_id)
        raise HTTPException(status_code=500, detail="Failed to update field values")

    return _fetch_single_form_summary(case_id, form_id)


@router.patch("/{case_id}/forms/{form_id}", response_model=CaseFormSummary)
def patch_form_status(
    case_id: str,
    form_id: str,
    payload: FormStatusPatchPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> CaseFormSummary:
    """
    Advance a case_form's lifecycle status.
    'ready' validates required fields; 'submitted' requires receipt_ref;
    'approved'/'rejected'/'not_started' are HR/ADMIN only.
    """
    _assert_case_access(user, case_id)

    # [P2-6/P4-2] 'approved'/'rejected'/'not_started' added for specialist + HR review.
    allowed_all = {"ready", "submitted", "approved", "rejected", "not_started"}
    hr_only = {"rejected", "not_started"}
    if payload.status not in allowed_all:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported status transition. Allowed: {sorted(allowed_all)}",
        )
    user_role = str(user.get("role") or "").upper()
    if payload.status in hr_only and user_role not in ("HR", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail=f"Only HR or ADMIN users can transition to '{payload.status}'.",
        )

    try:
        with main_db.engine.begin() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            raw_fields = form_row.get("template_fields") or []
            if isinstance(raw_fields, str):
                try:
                    raw_fields = json.loads(raw_fields)
                except (json.JSONDecodeError, TypeError):
                    raw_fields = []

            if payload.status == "ready":
                required_ids = [f["id"] for f in raw_fields if f.get("required")]
                if required_ids:
                    # IN (:fid0, :fid1, …) — works on both PostgreSQL and SQLite
                    in_placeholders = ", ".join(f":fid{i}" for i in range(len(required_ids)))
                    ready_params: Dict[str, Any] = {"form_id": form_id}
                    ready_params.update({f"fid{i}": fid for i, fid in enumerate(required_ids)})
                    filled_rows = conn.execute(
                        _sql_text(
                            f"SELECT field_id FROM {_pg_table('case_form_field_values')} "
                            f"WHERE case_form_id=:form_id AND field_id IN ({in_placeholders}) "
                            f"AND value IS NOT NULL AND value <> ''"
                        ),
                        ready_params,
                    ).mappings().all()
                    filled_ids = {str(r["field_id"]) for r in filled_rows}
                    missing = [fid for fid in required_ids if fid not in filled_ids]
                    if missing:
                        raise HTTPException(
                            status_code=422,
                            detail={"error": "Missing required fields", "missing_fields": missing},
                        )

                conn.execute(
                    _sql_text(f"UPDATE {_pg_table('case_forms')} SET status='ready', "
                              f"updated_at={_sql_now()} WHERE id=:form_id"),
                    {"form_id": form_id},
                )

            elif payload.status == "submitted":
                if not payload.receipt_ref:
                    raise HTTPException(status_code=422, detail="receipt_ref is required for status=submitted")
                conn.execute(
                    _sql_text(
                        f"UPDATE {_pg_table('case_forms')} SET status='submitted', "
                        f"receipt_ref=:receipt_ref, submitted_at={_sql_now()}, "
                        f"updated_at={_sql_now()} WHERE id=:form_id"
                    ),
                    {"receipt_ref": payload.receipt_ref, "form_id": form_id},
                )

            elif payload.status == "approved":
                # [P2-6] Specialist approves. Only allowed from 'submitted'.
                # DB trigger (handle_case_form_approval) unlocks blocked forms atomically.
                current_status = str(form_row.get("status") or "")
                if current_status != "submitted":
                    raise HTTPException(
                        status_code=422,
                        detail=(f"Cannot transition to 'approved' from '{current_status}'. "
                                "The form must be in 'submitted' status first."),
                    )
                conn.execute(
                    _sql_text(f"UPDATE {_pg_table('case_forms')} SET status='approved', "
                              f"updated_at={_sql_now()} WHERE id=:form_id"),
                    {"form_id": form_id},
                )

            elif payload.status == "rejected":
                # [P4-2/P4-5] Store rejection_reason so the employee can see it.
                conn.execute(
                    _sql_text(f"UPDATE {_pg_table('case_forms')} SET status='rejected', "
                              f"rejection_reason=:reason, updated_at={_sql_now()} WHERE id=:form_id"),
                    {"form_id": form_id, "reason": payload.rejection_reason or None},
                )

            elif payload.status == "not_started":
                # [P4-2] HR reset — return a form to not_started post-rejection.
                conn.execute(
                    _sql_text(f"UPDATE {_pg_table('case_forms')} SET status='not_started', "
                              f"updated_at={_sql_now()} WHERE id=:form_id"),
                    {"form_id": form_id},
                )

            # [P4-2] Enrich the trigger-written event row with actor_id and note.
            user_id = user.get("id") or user.get("sub")
            note_value = getattr(payload, "note", None)
            if user_id:
                try:
                    conn.execute(
                        _sql_text(
                            f"UPDATE {_pg_table('case_form_events')} SET actor_id=:actor_id, note=:note "
                            f"WHERE id = (SELECT id FROM {_pg_table('case_form_events')} "
                            f"WHERE case_form_id=:form_id AND event_type='status_change' "
                            f"ORDER BY created_at DESC LIMIT 1)"
                        ),
                        {"actor_id": user_id, "note": note_value, "form_id": form_id},
                    )
                except Exception:
                    pass  # case_form_events may not exist in legacy test schemas

            try:
                insert_audit_log(
                    conn,
                    entity_type="case_form",
                    entity_id=form_id,
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=user_id,
                    new_value={"status": payload.status},
                )
            except Exception:
                logger.exception("audit: patch_form_status cf=%s", form_id)

    except HTTPException:
        raise
    except Exception:
        logger.exception("forms: patch status failed case_id=%s form_id=%s", case_id, form_id)
        raise HTTPException(status_code=500, detail="Failed to update form status")

    # [P2-6] After approving, re-fill any forms that were blocked by this one.
    if payload.status == "approved":
        run_prefill_for_dependents(form_id, case_id)

    _post_form_status_notifications(case_id, form_id, payload)
    return _fetch_single_form_summary(case_id, form_id)


def _post_form_status_notifications(
    case_id: str, form_id: str, payload: FormStatusPatchPayload
) -> None:
    """[P4-4] Post-commit notifications — fire-and-forget, never block the response."""
    try:
        from ..services.dossier_notifications import (
            notify_blocker_resolved,
            notify_dossier_built,
            notify_form_ready,
            notify_form_rejected,
            notify_form_submitted,
        )
        if payload.status == "ready":
            notify_form_ready(form_id)
        elif payload.status == "submitted":
            notify_form_submitted(form_id, receipt_ref=payload.receipt_ref)
        elif payload.status == "rejected":
            notify_form_rejected(form_id, reason=getattr(payload, "note", None))
        elif payload.status == "approved":
            try:
                with main_db.engine.connect() as _conn:
                    unblocked_rows = _conn.execute(
                        _sql_text(
                            f"SELECT cf.id AS unblocked_id, ft.name AS unblocked_name "
                            f"FROM {_pg_table('case_forms')} cf "
                            f"JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id "
                            f"WHERE cf.blocker_form_id = :blocker_id AND cf.status = 'not_started'"
                        ),
                        {"blocker_id": form_id},
                    ).mappings().all()
                for ub in unblocked_rows:
                    notify_blocker_resolved(
                        str(ub["unblocked_id"]),
                        unblocked_form_name=str(ub["unblocked_name"]),
                    )
            except Exception:
                logger.exception("forms: blocker_resolved notification query failed cf=%s", form_id)
            try:
                with main_db.engine.connect() as _conn:
                    counts = _conn.execute(
                        _sql_text(
                            f"SELECT COUNT(*) AS total, "
                            f"COUNT(CASE WHEN status IN ('submitted','approved') THEN 1 END) AS done "
                            f"FROM {_pg_table('case_forms')} WHERE case_id = :case_id"
                        ),
                        {"case_id": case_id},
                    ).mappings().first()
                if counts and int(counts["total"]) > 0 and int(counts["total"]) == int(counts["done"]):
                    notify_dossier_built(case_id, form_count=int(counts["total"]))
            except Exception:
                logger.exception("forms: dossier_built check failed case_id=%s", case_id)
    except Exception:
        logger.exception("forms: post-commit notifications failed case_id=%s form_id=%s", case_id, form_id)


@router.post("/{case_id}/forms/{form_id}/comments", response_model=CommentItem, status_code=201)
def create_form_comment(
    case_id: str,
    form_id: str,
    payload: CommentCreate,
    user: Dict[str, Any] = Depends(get_current_user),
) -> CommentItem:
    """Post a comment on a CaseForm."""
    # [AIQ-1776] case_forms.case_id holds the canonical case id; this route's
    # {case_id} may be an assignment id. Key on the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)

    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=422, detail="Comment content cannot be empty")

    author_id = user.get("id") or user.get("sub")
    if not author_id:
        raise HTTPException(status_code=401, detail="Cannot determine author identity")

    try:
        with main_db.engine.begin() as conn:
            exists = conn.execute(
                _sql_text(f"SELECT id FROM {_pg_table('case_forms')} "
                          f"WHERE id=:form_id AND case_id=:case_id"),
                {"form_id": form_id, "case_id": resolved_case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            row = conn.execute(
                _sql_text(f"INSERT INTO {_pg_table('case_form_comments')} "
                          f"(case_form_id, author_id, content) "
                          f"VALUES (:form_id, :author_id, :content) "
                          f"RETURNING id, case_form_id, author_id, content, created_at"),
                {"form_id": form_id, "author_id": author_id, "content": payload.content.strip()},
            ).mappings().first()

            try:
                insert_audit_log(
                    conn,
                    entity_type="case_form_comment",
                    entity_id=str(row["id"]),
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=author_id,
                    new_value={"case_form_id": form_id},
                )
            except Exception:
                logger.exception("audit: create_form_comment form_id=%s", form_id)

    except HTTPException:
        raise
    except Exception:
        logger.exception("comments: create failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to save comment")

    author_name = None
    try:
        with main_db.engine.connect() as conn2:
            prow = conn2.execute(
                _sql_text(f"SELECT full_name FROM {_pg_table('profiles')} WHERE id=:uid"),
                {"uid": author_id},
            ).mappings().first()
            if prow:
                author_name = prow.get("full_name")
    except Exception:
        pass  # author_name is optional

    return CommentItem(
        id=str(row["id"]),
        case_form_id=str(row["case_form_id"]),
        author_id=str(row["author_id"]),
        author_name=author_name,
        content=str(row["content"]),
        created_at=str(row["created_at"]),
    )


# ── [P1-05c] Per-form supporting document upload / delete ────────────────────

_FORM_DOC_BUCKET = "case-documents"
_FORM_DOC_MAX_BYTES = 20 * 1024 * 1024  # 20 MiB — matches the bucket's file_size_limit
# The case-documents bucket enforces an allowed_mime_types list. Mirror it here
# so we reject unsupported files with a clear 415 (and never send a type the
# bucket will 400 on — notably the old 'application/octet-stream' fallback,
# which the bucket rejects and which surfaced as a misleading 502).
_FORM_DOC_ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/tiff",
}


def _resolve_doc_mime(declared: Optional[str], filename: Optional[str]) -> Optional[str]:
    """Best-effort content type for an uploaded doc, restricted to the bucket's
    allowed set. Prefer the client's declared type; when it is missing or the
    generic octet-stream, infer from the filename extension. Returns None when
    no allowed type can be determined."""
    import mimetypes

    ct = (declared or "").strip().lower()
    if ct in ("", "application/octet-stream"):
        guessed, _ = mimetypes.guess_type(filename or "")
        ct = (guessed or "").strip().lower()
    return ct if ct in _FORM_DOC_ALLOWED_MIME else None


def _safe_filename(name: str) -> str:
    # Map anything outside [alnum . _ -] to '_', then neutralise path-traversal
    # sequences (leading dots, runs of dots). Slashes are already gone, so the
    # result can never escape its storage prefix.
    cleaned = "".join(c if (c.isalnum() or c in "._-") else "_" for c in (name or "upload"))
    cleaned = cleaned.lstrip(".")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    return cleaned[:120] or "upload"


@router.post(
    "/{case_id}/forms/{form_id}/documents",
    response_model=FormDocumentItem,
    status_code=201,
)
async def upload_form_document(
    case_id: str,
    form_id: str,
    file: UploadFile = File(...),
    doc_key: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(get_current_user),
) -> FormDocumentItem:
    """
    [P1-05c] Upload a supporting document for a single case_form. The file is
    stored in the private `case-documents` bucket; a metadata row is written to
    case_form_documents scoped to (case_id, case_form_id).
    """
    # [AIQ-1776] case_forms.case_id / case_form_documents.case_id hold the canonical
    # case id; this route's {case_id} may be an assignment id. Both the ownership
    # check and the INSERT take the resolved value — storing the raw id here would
    # make the row invisible to every reader that resolves.
    resolved_case_id = _assert_case_access(user, case_id)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(contents) > _FORM_DOC_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB limit")

    uploaded_by = user.get("id") or user.get("sub")
    file_name = _safe_filename(file.filename or "upload")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    storage_path = f"case-forms/{form_id}/uploads/{ts}_{file_name}"
    # fix: [DOC-UPLOAD-502] the bucket only accepts PDF + common image types.
    # The old `file.content_type or 'application/octet-stream'` sent octet-stream
    # when the client omitted a type, which the bucket 400s — surfaced to users
    # as a generic 502 "Storage unavailable". Resolve to an allowed type (infer
    # from the filename when needed) and reject anything else with a clear 415.
    content_type = _resolve_doc_mime(file.content_type, file.filename)
    if content_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF or image (PNG, JPEG, WebP, TIFF).",
        )

    # Confirm the form belongs to this case before touching storage.
    with main_db.engine.connect() as conn:
        exists = conn.execute(
            _sql_text(
                f"SELECT id FROM {_pg_table('case_forms')} "
                f"WHERE id = :form_id AND case_id = :case_id"
            ),
            {"form_id": form_id, "case_id": resolved_case_id},
        ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Form not found")

    # Upload to Supabase Storage (service-role client).
    try:
        from ..services.supabase_client import get_supabase_admin_client  # lazy import
        sb = get_supabase_admin_client()
        sb.storage.from_(_FORM_DOC_BUCKET).upload(
            storage_path,
            contents,
            {"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:
        # Full traceback so the real storage error is diagnosable in prod logs.
        logger.exception("form_doc upload: storage error form_id=%s", form_id)
        # Defense in depth: a mime rejection that slips past the check above is a
        # client error (415), not a storage outage (502).
        if "mime" in str(exc).lower():
            raise HTTPException(
                status_code=415,
                detail="Unsupported file type. Upload a PDF or image (PNG, JPEG, WebP, TIFF).",
            )
        raise HTTPException(status_code=502, detail="Storage unavailable — upload failed")

    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(
                    f"INSERT INTO {_pg_table('case_form_documents')} "
                    f"(case_form_id, case_id, file_name, storage_path, content_type, size_bytes, uploaded_by, doc_key) "
                    f"VALUES (:fid, :cid, :name, :path, :ctype, :size, :uid, :dkey) "
                    f"RETURNING id, case_form_id, case_id, file_name, content_type, size_bytes, uploaded_by, doc_key, created_at"
                ),
                {
                    "fid": form_id, "cid": resolved_case_id, "name": file_name,
                    "path": storage_path, "ctype": content_type,
                    "size": len(contents), "uid": uploaded_by,
                    "dkey": (doc_key or None),
                },
            ).mappings().first()
    except Exception:
        logger.exception("form_doc upload: db insert failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to record uploaded document")

    return FormDocumentItem(
        id=str(row["id"]),
        case_form_id=str(row["case_form_id"]),
        case_id=str(row["case_id"]),
        file_name=str(row["file_name"]),
        content_type=row.get("content_type"),
        size_bytes=(int(row["size_bytes"]) if row.get("size_bytes") is not None else None),
        uploaded_by=(str(row["uploaded_by"]) if row.get("uploaded_by") else None),
        doc_key=(str(row["doc_key"]) if row.get("doc_key") else None),
        created_at=str(row["created_at"]),
        download_url=None,
    )


@router.post(
    "/{case_id}/forms/{form_id}/register-prefilled",
    response_model=FormDocumentItem,
    status_code=201,
)
def register_prefilled_document(
    case_id: str,
    form_id: str,
    payload: RegisterPrefilledPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> FormDocumentItem:
    """
    [AIQ-1758] Register a reviewed prefilled data-sheet as a durable case artifact.

    Closes the auto-fill loop: once the employee/HR has reviewed what the prefill
    engine produced, the result stops being transient field values and becomes a
    versioned document on the case, with an audit trail and a lifecycle advance.

    Three effects, in one transaction where it matters:
      1. a ``case_form_documents`` row with ``doc_kind='prefilled'`` and the
         ``fill_report`` snapshot,
      2. an ``audit_logs`` entry using the established prefill convention
         (``entity_type='case_form'``, semantic event in ``new_value``) — see
         ``prefill_engine._insert_prefill_audit``,
      3. the form advances to ``ready`` via the SAME required-field validation the
         status endpoint applies, so this cannot be used to bypass it.

    Storage note: unlike the upload endpoint there is no client file — the
    artifact is the reviewed field set. We record a deterministic
    ``storage_path`` for the rendered PDF; rendering it is the PDF-generation
    path's job (``TODO [AIQ-1759]``), so the row is the durable record and the
    binary can be produced later without changing this contract.
    """
    _assert_case_access(user, case_id)

    actor_id = user.get("id") or user.get("sub")
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    file_name = _safe_filename(payload.file_name or f"prefilled-data-sheet-{ts}.pdf")
    # Versioned by timestamp so re-registering never overwrites the prior artifact.
    storage_path = f"case-forms/{form_id}/prefilled/{ts}_{file_name}"

    try:
        with main_db.engine.begin() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            if payload.advance_status:
                raw_fields = form_row.get("template_fields") or []
                if isinstance(raw_fields, str):
                    try:
                        raw_fields = json.loads(raw_fields)
                    except (json.JSONDecodeError, TypeError):
                        raw_fields = []

                # Same gate as PATCH /status {status:'ready'} — registering a
                # reviewed sheet must not be a back door around required fields.
                required_ids = [f["id"] for f in raw_fields if f.get("required")]
                if required_ids:
                    in_placeholders = ", ".join(f":fid{i}" for i in range(len(required_ids)))
                    ready_params: Dict[str, Any] = {"form_id": form_id}
                    ready_params.update({f"fid{i}": fid for i, fid in enumerate(required_ids)})
                    filled_rows = conn.execute(
                        _sql_text(
                            f"SELECT field_id FROM {_pg_table('case_form_field_values')} "
                            f"WHERE case_form_id=:form_id AND field_id IN ({in_placeholders}) "
                            f"AND value IS NOT NULL AND value <> ''"
                        ),
                        ready_params,
                    ).mappings().all()
                    filled_ids = {str(r["field_id"]) for r in filled_rows}
                    missing = [fid for fid in required_ids if fid not in filled_ids]
                    if missing:
                        raise HTTPException(
                            status_code=422,
                            detail={"error": "Missing required fields", "missing_fields": missing},
                        )

                conn.execute(
                    _sql_text(
                        f"UPDATE {_pg_table('case_forms')} SET status='ready', "
                        f"updated_at={_sql_now()} WHERE id=:form_id"
                    ),
                    {"form_id": form_id},
                )

            row = conn.execute(
                _sql_text(
                    f"INSERT INTO {_pg_table('case_form_documents')} "
                    f"(case_form_id, case_id, file_name, storage_path, content_type, "
                    f" uploaded_by, doc_kind, fill_report) "
                    f"VALUES (:fid, :cid, :name, :path, :ctype, :uid, 'prefilled', :report) "
                    f"RETURNING id, case_form_id, case_id, file_name, content_type, "
                    f"          size_bytes, uploaded_by, doc_key, created_at"
                ),
                {
                    "fid": form_id, "cid": case_id, "name": file_name,
                    "path": storage_path, "ctype": "application/pdf",
                    "uid": actor_id,
                    "report": json.dumps(payload.fill_report or {}),
                },
            ).mappings().first()
    except HTTPException:
        raise
    except Exception:
        logger.exception("register_prefilled: failed case_id=%s form_id=%s", case_id, form_id)
        raise HTTPException(status_code=500, detail="Failed to register prefilled document")

    # Audit is best-effort and OUTSIDE the transaction, matching
    # prefill_engine._insert_prefill_audit: an audit failure must never roll back
    # or 500 the registration it is describing.
    try:
        with main_db.engine.begin() as conn:
            insert_audit_log(
                conn,
                entity_type="case_form",
                entity_id=form_id,
                action_type=ACTION_INSERT,
                actor_type=ACTOR_HUMAN,
                new_value={
                    "event": "prefill",
                    "form_id": form_id,
                    "document_id": str(row["id"]),
                    "doc_kind": "prefilled",
                    "storage_path": storage_path,
                    "status_advanced": bool(payload.advance_status),
                },
            )
    except Exception:
        logger.exception("register_prefilled: audit write failed form_id=%s", form_id)

    return FormDocumentItem(
        id=str(row["id"]),
        case_form_id=str(row["case_form_id"]),
        case_id=str(row["case_id"]),
        file_name=str(row["file_name"]),
        content_type=row.get("content_type"),
        size_bytes=(int(row["size_bytes"]) if row.get("size_bytes") is not None else None),
        uploaded_by=(str(row["uploaded_by"]) if row.get("uploaded_by") else None),
        doc_key=(str(row["doc_key"]) if row.get("doc_key") else None),
        created_at=str(row["created_at"]),
        download_url=None,
    )


@router.delete("/{case_id}/forms/{form_id}/documents/{document_id}", status_code=204)
def delete_form_document(
    case_id: str,
    form_id: str,
    document_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """[P1-05c] Delete a per-form supporting document (row + storage object)."""
    # [AIQ-1776] case_form_documents.case_id holds the canonical case id; this
    # route's {case_id} may be an assignment id. Key on the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)

    with main_db.engine.begin() as conn:
        row = conn.execute(
            _sql_text(
                f"SELECT storage_path FROM {_pg_table('case_form_documents')} "
                f"WHERE id = :id AND case_form_id = :fid AND case_id = :cid"
            ),
            {"id": document_id, "fid": form_id, "cid": resolved_case_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        conn.execute(
            _sql_text(f"DELETE FROM {_pg_table('case_form_documents')} WHERE id = :id"),
            {"id": document_id},
        )

    # Best-effort storage cleanup — the row is already gone, so don't fail here.
    try:
        from ..services.supabase_client import get_supabase_admin_client  # lazy import
        sb = get_supabase_admin_client()
        sb.storage.from_(_FORM_DOC_BUCKET).remove([str(row["storage_path"])])
    except Exception as exc:
        logger.warning("form_doc delete: storage cleanup failed doc_id=%s err=%s", document_id, exc)

    return Response(status_code=204)


@router.patch("/{case_id}/forms/{form_id}/flag", response_model=FormFlagResponse)
def patch_form_flag(
    case_id: str,
    form_id: str,
    payload: FlagPatchPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> FormFlagResponse:
    """
    Set or clear the flag on a CaseForm.
    flag_note='…' sets the flag; None/'' clears it. HR/ADMIN only.
    """
    # [AIQ-1776] case_forms.case_id holds the canonical case id; this route's
    # {case_id} may be an assignment id. Key on the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)

    user_role = str(user.get("role") or "").upper()
    if user_role not in ("HR", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only HR or ADMIN users can flag forms")

    user_id = user.get("id") or user.get("sub")
    clearing = not payload.flag_note or not payload.flag_note.strip()

    try:
        with main_db.engine.begin() as conn:
            exists = conn.execute(
                _sql_text(f"SELECT id FROM {_pg_table('case_forms')} "
                          f"WHERE id=:form_id AND case_id=:case_id"),
                {"form_id": form_id, "case_id": resolved_case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            if clearing:
                conn.execute(
                    _sql_text(f"UPDATE {_pg_table('case_forms')} SET flag_note=NULL, "
                              f"flagged_at=NULL, flagged_by=NULL, updated_at={_sql_now()} "
                              f"WHERE id=:form_id"),
                    {"form_id": form_id},
                )
                conn.execute(
                    _sql_text(f"INSERT INTO {_pg_table('case_form_events')} "
                              f"(case_form_id, event_type, actor_id) "
                              f"VALUES (:form_id, 'unflagged', :actor_id)"),
                    {"form_id": form_id, "actor_id": user_id},
                )
            else:
                conn.execute(
                    _sql_text(f"UPDATE {_pg_table('case_forms')} SET flag_note=:flag_note, "
                              f"flagged_at={_sql_now()}, flagged_by=:flagged_by, "
                              f"updated_at={_sql_now()} WHERE id=:form_id"),
                    {"flag_note": payload.flag_note.strip(), "flagged_by": user_id, "form_id": form_id},
                )
                conn.execute(
                    _sql_text(f"INSERT INTO {_pg_table('case_form_events')} "
                              f"(case_form_id, event_type, actor_id, note) "
                              f"VALUES (:form_id, 'flagged', :actor_id, :note)"),
                    {"form_id": form_id, "actor_id": user_id, "note": payload.flag_note.strip()},
                )

            updated = conn.execute(
                _sql_text(f"SELECT id, flag_note, flagged_at, flagged_by "
                          f"FROM {_pg_table('case_forms')} WHERE id=:form_id"),
                {"form_id": form_id},
            ).mappings().first()

            try:
                insert_audit_log(
                    conn,
                    entity_type="case_form",
                    entity_id=form_id,
                    action_type=ACTION_UPDATE,
                    actor_type=ACTOR_HUMAN,
                    actor_id=user_id,
                    new_value={"flagged": not clearing},
                )
            except Exception:
                logger.exception("audit: patch_form_flag cf=%s", form_id)

    except HTTPException:
        raise
    except Exception:
        logger.exception("flag: patch failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to update flag")

    return FormFlagResponse(
        id=str(updated["id"]),
        flag_note=updated.get("flag_note"),
        flagged_at=str(updated["flagged_at"]) if updated.get("flagged_at") else None,
        flagged_by=str(updated["flagged_by"]) if updated.get("flagged_by") else None,
    )


@router.post("/{case_id}/dossiers", response_model=DossierPackageResponse, status_code=201)
def create_dossier(
    case_id: str,
    payload: CreateDossierPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> DossierPackageResponse:
    """
    [P3-5] Merge a set of CaseForms into a single dossier PDF.

    Validates form ownership, generates filled PDFs (P3-1 helpers), inserts
    optional cover + divider pages, merges with pypdf, stores to Supabase,
    persists a dossier_packages row, and returns the record.
    """
    # [AIQ-1776] case_forms.case_id / dossier_packages.case_id hold the canonical
    # case id; this route's {case_id} may be an assignment id. Every statement and
    # helper below takes the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)

    if not payload.form_ids:
        raise HTTPException(status_code=422, detail="form_ids must not be empty")

    user_id = user.get("id") or user.get("sub")
    dossier_id = str(uuid.uuid4())

    try:
        with main_db.engine.begin() as conn:
            placeholders = ", ".join(f":fid{i}" for i in range(len(payload.form_ids)))
            params: Dict[str, Any] = {"case_id": resolved_case_id}
            params.update({f"fid{i}": fid for i, fid in enumerate(payload.form_ids)})
            valid_rows = conn.execute(
                _sql_text(
                    f"SELECT cf.id, COALESCE(ft.code, 'CUSTOM') AS code, "
                    f"COALESCE(ft.name, cf.adhoc_name, 'Custom document') AS name, "
                    f"ft.authority_code, "
                    f"COALESCE(ft.authority_name, cf.adhoc_authority) AS authority_name "
                    f"FROM {_pg_table('case_forms')} cf "
                    # [P4-3] LEFT JOIN so ad-hoc forms can be added to a package.
                    f"LEFT JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id "
                    f"WHERE cf.case_id=:case_id AND cf.id IN ({placeholders})"
                ),
                params,
            ).mappings().all()
            found_ids = {str(r["id"]) for r in valid_rows}
            missing = [fid for fid in payload.form_ids if fid not in found_ids]
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail=f"Form(s) not found in case: {', '.join(missing)}",
                )

            meta_by_id = {str(r["id"]): dict(r) for r in valid_rows}
            ordered_meta = [meta_by_id[fid] for fid in payload.form_ids]

            pdf_parts: List[bytes] = []

            if payload.cover_page:
                cover_bytes = _build_cover_page(
                    package_name=payload.name,
                    case_id=resolved_case_id,
                    forms_meta=ordered_meta,
                )
                pdf_parts.append(cover_bytes)

            for form_id, meta in zip(payload.form_ids, ordered_meta):
                divider = _build_divider_page(
                    form_code=meta.get("code") or "",
                    form_name=meta.get("name") or "",
                    authority_name=meta.get("authority_name"),
                )
                pdf_parts.append(divider)
                form_pdf = _fetch_form_pdf_bytes(conn, resolved_case_id, form_id)
                pdf_parts.append(form_pdf)

            try:
                merged_pdf = _merge_pdfs(pdf_parts)
            except Exception as exc:
                logger.exception("dossier: PDF merge failed case_id=%s: %s", case_id, exc)
                raise HTTPException(status_code=500, detail="PDF merge failed")

            form_ids_json = json.dumps(payload.form_ids)
            conn.execute(
                _sql_text(
                    f"INSERT INTO {_pg_table('dossier_packages')} "
                    f"(id, case_id, name, form_ids, cover_page, created_by, created_at) "
                    f"VALUES (:id, :case_id, :name, :form_ids, :cover_page, :created_by, {_sql_now()})"
                ),
                {"id": dossier_id, "case_id": resolved_case_id, "name": payload.name,
                 "form_ids": form_ids_json, "cover_page": payload.cover_page, "created_by": user_id},
            )

            pdf_url = _try_store_dossier_pdf(dossier_id, merged_pdf, conn)

            row = conn.execute(
                _sql_text(
                    f"SELECT id, case_id, name, form_ids, cover_page, pdf_url, generated_at, created_at "
                    f"FROM {_pg_table('dossier_packages')} WHERE id=:id"
                ),
                {"id": dossier_id},
            ).mappings().first()

            try:
                insert_audit_log(
                    conn,
                    entity_type="dossier_package",
                    entity_id=dossier_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=user_id,
                    new_value={"case_id": resolved_case_id, "form_count": len(payload.form_ids)},
                )
            except Exception:
                logger.exception("audit: create_dossier dossier_id=%s", dossier_id)

    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: create failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to create dossier")

    raw_form_ids = row["form_ids"]
    if isinstance(raw_form_ids, str):
        result_form_ids = json.loads(raw_form_ids)
    else:
        result_form_ids = list(raw_form_ids) if raw_form_ids else []

    return DossierPackageResponse(
        id=str(row["id"]),
        case_id=str(row["case_id"]),
        name=str(row["name"]),
        form_ids=result_form_ids,
        cover_page=bool(row["cover_page"]),
        pdf_url=pdf_url or row.get("pdf_url"),
        generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
        created_at=str(row["created_at"]),
    )


@router.post("/{case_id}/dossiers/{dossier_id}/regenerate", response_model=DossierPackageDetailResponse)
def regenerate_dossier(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> DossierPackageDetailResponse:
    """
    [P3-6] Rebuild the merged PDF for an existing DossierPackage using the
    latest FieldValues, then update generated_at and pdf_url.
    """
    # [AIQ-1776] dossier_packages.case_id / case_forms.case_id hold the canonical
    # case id; this route's {case_id} may be an assignment id. The lookup and every
    # helper below take the resolved value.
    resolved_case_id = _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(f"SELECT id, case_id, name, form_ids, cover_page "
                          f"FROM {_pg_table('dossier_packages')} WHERE id=:did AND case_id=:cid"),
                {"did": dossier_id, "cid": resolved_case_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            raw_ids = row["form_ids"]
            form_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            if not form_ids:
                raise HTTPException(status_code=422, detail="Dossier has no forms")

            pdf_parts: List[bytes] = []

            if row["cover_page"]:
                cover_meta: List[Dict[str, Any]] = []
                for fid in form_ids:
                    fr = _load_form_with_template(conn, resolved_case_id, fid)
                    if fr:
                        cover_meta.append({
                            "code": fr.get("template_code"),
                            "name": fr.get("template_name"),
                            "authority_code": fr.get("authority_code"),
                        })
                pdf_parts.append(_build_cover_page(str(row["name"]), resolved_case_id, cover_meta))

            for fid in form_ids:
                fr = _load_form_with_template(conn, resolved_case_id, fid)
                if fr:
                    pdf_parts.append(
                        _build_divider_page(
                            str(fr.get("template_code") or ""),
                            str(fr.get("template_name") or ""),
                            fr.get("authority_name"),
                        )
                    )
                pdf_parts.append(_fetch_form_pdf_bytes(conn, resolved_case_id, fid))

            merged_pdf = _merge_pdfs(pdf_parts)

            conn.execute(
                _sql_text(f"UPDATE {_pg_table('dossier_packages')} "
                          f"SET generated_at={_sql_now()} WHERE id=:did"),
                {"did": dossier_id},
            )

            new_pdf_url = _try_store_dossier_pdf(dossier_id, merged_pdf, conn)

            updated_row = conn.execute(
                _sql_text(
                    f"SELECT id, case_id, name, form_ids, cover_page, pdf_url, generated_at, created_at "
                    f"FROM {_pg_table('dossier_packages')} WHERE id=:did"
                ),
                {"did": dossier_id},
            ).mappings().first()

            raw_ids2 = updated_row["form_ids"]
            form_ids2 = json.loads(raw_ids2) if isinstance(raw_ids2, str) else list(raw_ids2 or [])

            return DossierPackageDetailResponse(
                id=str(updated_row["id"]),
                case_id=str(updated_row["case_id"]),
                name=str(updated_row["name"]),
                form_ids=form_ids2,
                cover_page=bool(updated_row["cover_page"]),
                pdf_url=new_pdf_url or updated_row.get("pdf_url"),
                generated_at=str(updated_row["generated_at"]) if updated_row.get("generated_at") else None,
                created_at=str(updated_row["created_at"]),
                is_stale=False,  # just regenerated
            )

    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: regenerate failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to regenerate dossier")


@router.post("/{case_id}/quote-request", status_code=410)
def create_case_quote_request(
    case_id: str,
    body: _QuoteRequestBody,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """RETIRED — [AIQ-1525].

    Employee quote requests are consolidated onto the canonical RFQ system; submit via
    POST /api/rfqs (a vendor shortlist that writes rfqs + rfq_recipients). This handler,
    and the `POST /api/employee/steps/4` alias that delegates to it, no longer write
    `quote_requests`. The table's historical rows stay readable.

    The tenant guard runs first and unchanged: a non-assignee still gets 403, so the
    retirement never becomes an information leak about which cases exist.
    """
    _assert_case_access(user, case_id)
    raise HTTPException(
        status_code=410,
        detail="This endpoint is retired. Submit quote requests via POST /api/rfqs.",
    )


@router.post("/{case_id}/messages", status_code=201)
def post_case_message(
    case_id: str,
    body: _MessageBody,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Post a message to the case thread (Step 5 / WZ5).
    Any authenticated user linked to the case (employee or HR) can post.
    """
    # Tenant isolation: enforce that the caller is actually linked to the case
    # (assignee / HR in-company / admin) — previously this endpoint had no check.
    _assert_case_access(user, case_id)
    if not body.content.strip():
        raise HTTPException(status_code=422, detail="content must not be empty")

    sender_id = str(user["id"])
    sender_role = _detect_sender_role(user)
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    try:
        with main_db.engine.begin() as conn:
            conn.execute(
                _sql_text(
                    "INSERT INTO public.case_messages "
                    "(id, case_id, sender_id, sender_role, content, created_at) "
                    "VALUES (:id, :case_id, :sender_id, :sender_role, :content, :now)"
                ),
                {"id": new_id, "case_id": case_id, "sender_id": sender_id,
                 "sender_role": sender_role, "content": body.content, "now": now},
            )
            row = conn.execute(
                _sql_text("SELECT * FROM public.case_messages WHERE id = :id"),
                {"id": new_id},
            ).mappings().first()
    except Exception:
        logger.exception("messages: insert failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to post message")

    if row is None:
        raise HTTPException(status_code=500, detail="Message not found after insert")

    d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)
    return {
        "id": str(d["id"]),
        "case_id": str(d["case_id"]),
        "sender_id": str(d["sender_id"]),
        "sender_role": d["sender_role"],
        "content": d["content"],
        "created_at": d["created_at"],
    }
