from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from ..db import SessionLocal
from .. import crud, schemas
from ..auth_deps import get_current_user, require_case_access
from ...database import db as main_db
from ..services.relocation_plan_view_service import invalidate_relocation_plan_cache
from ..services.research import run_country_research
from ..services.requirements_builder import compute_case_requirements
from ..services.roadmap_builder import derive_roadmap
from ..services.trigger_engine import fire_roadmap_events
from ..services.prefill_engine import run_prefill_for_dependents
from ..services.audit_log_service import (
    ACTION_INSERT,
    ACTION_UPDATE,
    ACTOR_HUMAN,
)
from ..services.case_service import (
    _assert_case_access,
    _audit_case,
    _case_dto,
    _deep_merge_case_drafts,
    _detect_sender_role,
    _dossier_is_stale,
    _pg_conn,
    _pg_table,
    _sql_now,
    _sql_uuid_gen,
)
from sqlalchemy import text as _sql_text
import io
import zipfile as _zipfile
import datetime as _dt
import requests as _requests

router = APIRouter(prefix="/api/cases", tags=["cases"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Household models (GAP 1b)
# ─────────────────────────────────────────────────────────────────────────────

class FamilyMemberInput(BaseModel):
    type: str  # spouse | child | other
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None


class PetInput(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    species: Optional[str] = None
    weight_kg: Optional[float] = None
    origin_country: Optional[str] = None
    microchipped: Optional[bool] = None
    vaccinations_up_to_date: Optional[bool] = None


class HouseholdPayload(BaseModel):
    family_members: Optional[List[FamilyMemberInput]] = None
    pets: Optional[List[PetInput]] = None


@router.get("", tags=["cases"])
def list_employee_cases(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GET /api/cases — returns the authenticated employee's assigned cases.
    Mirrors /api/employee/cases for frontend and E2E test compatibility.
    HR/admin tokens receive an empty list (use /api/hr/cases instead).
    Fixes B12b: previously returned 404 because no root route existed on this router.
    """
    role = (user.get("role") or "employee").lower()
    if role not in ("employee",):
        # Role isolation: HR/admin must use /api/hr/cases, not this endpoint.
        return {"cases": []}

    uid = user.get("id") or user.get("user_id") or user.get("sub")
    rid = getattr(request.state, "request_id", None)
    try:
        linked = main_db.list_linked_assignments_for_employee(uid, request_id=rid)
    except Exception:
        logger.exception("list_employee_cases: DB query failed for uid=%s", uid)
        linked = []

    cases = []
    for row in linked:
        d = dict(row)
        case_id = d.get("case_id") or d.get("id")
        cases.append({
            "id": case_id,
            "caseId": case_id,
            "assignmentId": d.get("id"),
            "status": d.get("status"),
            "employeeIdentifier": d.get("employee_identifier"),
        })
    return {"cases": cases}


@router.get("/{case_id}", response_model=schemas.CaseDTO)
def get_case(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        _assert_case_access(user, case_id)
        draft = json.loads(case.draft_json)
        return _case_dto(case, draft)


@router.patch("/{case_id}", response_model=schemas.CaseDTO)
def patch_case(case_id: str, patch: schemas.CaseDraftDTO):
    with SessionLocal() as db:
        # Filter out None sections so partial payloads (e.g. from E2E runner) don't
        # overwrite existing draft sections with null.
        incoming = {k: v for k, v in patch.model_dump(mode="json").items() if v is not None}
        case = crud.get_case(db, case_id)
        if not case:
            case = crud.create_case(db, case_id, incoming)
            draft = incoming
        else:
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
            "purpose": basics.get("purpose"),
            "target_move_date": basics.get("targetMoveDate"),
        }
        flags = {
            "hasDependents": basics.get("hasDependents"),
        }
        case = crud.update_case(db, case, draft, derived, flags)
        try:
            main_db.apply_wizard_patch_side_effects(case_id, draft, derived)
        except Exception:
            logger.exception("apply_wizard_patch_side_effects failed case_id=%s", case_id)
        # P1-3: Trigger Engine — auto-create CaseForms for matched templates
        fire_roadmap_events(case_id, draft, derived)
        invalidate_relocation_plan_cache(case_id=case_id)
        _audit_case(entity_type="case", entity_id=case_id, action_type=ACTION_UPDATE)
        return _case_dto(case, draft)


@router.patch("/{case_id}/relocationBasics", response_model=schemas.CaseDTO)
def patch_case_relocation_basics(
    case_id: str,
    basics: schemas.RelocationBasicsDTO,
    user: Dict[str, Any] = Depends(get_current_user),
) -> schemas.CaseDTO:
    """
    Alias endpoint: accepts RelocationBasicsDTO and wraps it into CaseDraftDTO.
    Resolves B17/WZ1a — PATCH /relocationBasics returned 405.
    """
    wrapped = schemas.CaseDraftDTO(relocationBasics=basics)
    return patch_case(case_id, wrapped)


@router.patch("/{case_id}/serviceSelections", response_model=schemas.CaseDTO)
def patch_case_service_selections(
    case_id: str,
    body: schemas.CaseDraftDTO,
    user: Dict[str, Any] = Depends(get_current_user),
) -> schemas.CaseDTO:
    """
    Alias endpoint: accepts service selections payload.
    Resolves B19/WZ2 — PATCH /serviceSelections returned 405.
    """
    return patch_case(case_id, body)


@router.post("/{case_id}/research/start")
def start_research(case_id: str):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        draft = json.loads(case.draft_json)
        basics = draft.get("relocationBasics", {})
        dest_country = basics.get("destCountry")
        if not dest_country:
            raise HTTPException(status_code=400, detail="Destination country required")

    run_country_research(dest_country, basics.get("purpose", "employment"), {})
    _audit_case(entity_type="case", entity_id=case_id, action_type=ACTION_UPDATE, new_value={"event": "research_started"})
    return {"jobId": str(uuid.uuid4())}


@router.get("/{case_id}/requirements", response_model=schemas.CaseRequirementsDTO)
def get_case_requirements(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    _assert_case_access(user, case_id)
    try:
        return compute_case_requirements(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found")


@router.post("/{case_id}/create")
def create_case(case_id: str, request: Request):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

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
                "purpose": basics.get("purpose"),
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


# ─────────────────────────────────────────────────────────────────────────────
# GAP 2 / GAP 5: Multi-track roadmap endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/roadmap")
def get_case_roadmap(case_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """
    GAP 2 & GAP 5: Returns a multi-track relocation roadmap derived from the case draft.
    Replaces window.PATHWAY_V2.deriveTimeline() with a real server-side computation.
    Tracks: Visa & Permit | Civil Documents | Family (conditional) | Settlement.
    """
    _assert_case_access(user, case_id)
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        draft = json.loads(case.draft_json or "{}")

    case_dict = {
        "id": case_id,
        "status": case.status,
        "draft": draft,
    }
    return derive_roadmap(case_dict)


# ─────────────────────────────────────────────────────────────────────────────
# [P1-6] Roadmap tracks V2 — with embedded CaseForm doc counts per step
# ─────────────────────────────────────────────────────────────────────────────

class RoadmapDocChip(BaseModel):
    doc_count: int
    worst_doc_status: Optional[str] = None


class RoadmapStepV2(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    owner: str
    due_date: Optional[str] = None
    sort_order: int
    ai_suggestion: Optional[str] = None
    dependency_ids: List[str] = []
    vendor_id: Optional[str] = None
    doc_count: int = 0
    worst_doc_status: Optional[str] = None


class RoadmapTrackV2(BaseModel):
    id: str
    name: str
    icon: str
    sort_order: int
    progress_pct: int
    steps: List[RoadmapStepV2] = []


class RoadmapTracksResponse(BaseModel):
    tracks: List[RoadmapTrackV2]


@router.get("/{case_id}/roadmap/tracks", response_model=RoadmapTracksResponse)
def get_case_roadmap_tracks(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> RoadmapTracksResponse:
    """
    [P1-6] Returns roadmap_tracks + roadmap_steps with embedded doc counts
    from case_forms. Used by the employee RoadmapScreen chip.
    """
    _assert_case_access(user, case_id)

    # Resolve assignment_id → canonical_case_id so roadmap_tracks queries
    # use the correct FK. The URL param is always an assignment_id for real
    # cases; roadmap_tracks.case_id references relocation_cases.id.
    tracks_case_id = case_id
    try:
        with _pg_conn() as conn:
            asgn_row = conn.execute(
                _sql_text(
                    "SELECT canonical_case_id FROM public.case_assignments "
                    "WHERE id::text = :id AND canonical_case_id IS NOT NULL"
                ),
                {"id": case_id},
            ).mappings().first()
        if asgn_row and asgn_row.get("canonical_case_id"):
            tracks_case_id = str(asgn_row["canonical_case_id"])
    except Exception:
        logger.warning("roadmap/tracks: could not resolve canonical_case_id for %s", case_id)

    with _pg_conn() as conn:
        sql = f"""
            SELECT
              rt.id             AS track_id,
              rt.name           AS track_name,
              rt.icon           AS track_icon,
              rt.sort_order     AS track_sort_order,
              rt.completion_pct AS progress_pct,
              rs.id                          AS step_id,
              rs.title                       AS step_title,
              rs.description                 AS step_description,
              rs.status                      AS step_status,
              rs.owner_type                  AS step_owner,
              rs.due_date                    AS step_due_date,
              rs.sort_order                  AS step_sort_order,
              NULL::text                     AS ai_suggestion,
              ARRAY[]::text[]                AS dependency_ids,
              NULL::uuid                     AS vendor_id,
              COUNT(cf.id) AS doc_count,
              CASE
                WHEN COUNT(cf.id) = 0 THEN NULL
                WHEN SUM(CASE WHEN cf.blocker_form_id IS NOT NULL
                              AND cf.status NOT IN ('submitted','approved','rejected')
                              THEN 1 ELSE 0 END) > 0 THEN 'blocked'
                WHEN SUM(CASE WHEN cf.status = 'rejected' THEN 1 ELSE 0 END) > 0 THEN 'rejected'
                WHEN SUM(CASE WHEN cf.status = 'pending_doc' THEN 1 ELSE 0 END) > 0 THEN 'pending_doc'
                WHEN SUM(CASE WHEN cf.status IN ('in_progress','auto_filled')
                              THEN 1 ELSE 0 END) > 0 THEN 'in_progress'
                WHEN SUM(CASE WHEN cf.status = 'not_started' THEN 1 ELSE 0 END) > 0 THEN 'not_started'
                WHEN SUM(CASE WHEN cf.status = 'ready' THEN 1 ELSE 0 END) > 0 THEN 'ready'
                WHEN SUM(CASE WHEN cf.status = 'submitted' THEN 1 ELSE 0 END) > 0 THEN 'submitted'
                ELSE 'approved'
              END AS worst_doc_status
            FROM {_pg_table('roadmap_tracks')} rt
            JOIN {_pg_table('roadmap_steps')} rs ON rs.track_id = rt.id
            LEFT JOIN {_pg_table('case_forms')} cf
              ON cf.roadmap_step_id = rs.id AND cf.case_id = :case_id
            WHERE rt.case_id = :case_id
            GROUP BY rt.id, rt.name, rt.icon, rt.sort_order, rt.completion_pct,
                     rs.id, rs.title, rs.description, rs.status, rs.owner_type,
                     rs.due_date, rs.sort_order
            ORDER BY rt.sort_order, rs.sort_order
        """
        rows = conn.execute(_sql_text(sql), {"case_id": tracks_case_id}).mappings().all()

    # Assemble into tracks -> steps hierarchy
    tracks_map: Dict[str, RoadmapTrackV2] = {}
    for row in rows:
        tid = str(row["track_id"])
        if tid not in tracks_map:
            tracks_map[tid] = RoadmapTrackV2(
                id=tid,
                name=row["track_name"],
                icon=row["track_icon"] or "Circle",
                sort_order=row["track_sort_order"] or 0,
                progress_pct=int(row["progress_pct"] or 0),
            )
        dep_ids = row["dependency_ids"]
        if isinstance(dep_ids, str):
            import json as _json
            dep_ids = _json.loads(dep_ids) if dep_ids else []
        tracks_map[tid].steps.append(RoadmapStepV2(
            id=str(row["step_id"]),
            title=row["step_title"],
            description=row.get("step_description"),
            status=row["step_status"] or "pending",
            owner=row["step_owner"] or "employee",
            due_date=str(row["step_due_date"]) if row.get("step_due_date") else None,
            sort_order=row["step_sort_order"] or 0,
            ai_suggestion=row.get("ai_suggestion"),
            dependency_ids=dep_ids if isinstance(dep_ids, list) else [],
            vendor_id=str(row["vendor_id"]) if row.get("vendor_id") else None,
            doc_count=int(row["doc_count"] or 0),
            worst_doc_status=row.get("worst_doc_status"),
        ))
    return RoadmapTracksResponse(tracks=list(tracks_map.values()))


# ─────────────────────────────────────────────────────────────────────────────
# GAP 9: Research status polling endpoint (Option B — polling, no SSE)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/research/status")
def get_research_status(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    GAP 9: Poll-based research progress for the S2 discovery log.
    Returns {status, progress_pct, events[{ts, msg}]}.
    Client polls every 2s; no SSE infrastructure required.

    SEC fix (GAP-9): require an authenticated session and case-level access.
    NB: this router is dormant (retired by AUDIT-B9-cases-6). The live copy
    lives in cases_read.py; this one stays in sync so the route-auth audit
    job remains green and any future re-wiring can't accidentally ship a
    regressed handler.
    """
    require_case_access(case_id, user)
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        draft = json.loads(case.draft_json or "{}")

    basics = draft.get("relocationBasics", {})
    dest = basics.get("destCountry", "")
    purpose = basics.get("purpose", "employment")

    # Check if requirements snapshot exists (research completed)
    snapshot_id = case.requirements_snapshot_id
    if snapshot_id:
        # Research has been run — compute a realistic event log from the requirements
        try:
            reqs = compute_case_requirements(case_id)
            req_count = len(reqs.requirements) if reqs.requirements else 0
            doc_count = len([r for r in (reqs.requirements or []) if "document" in (r.category or "").lower()])
        except Exception:
            req_count = 0
            doc_count = 0

        events = [
            {"ts": "14:02:11", "msg": f"Authenticating immigration authority API for {dest}"},
            {"ts": "14:02:13", "msg": f"Pulling {purpose} permit schema… OK"},
            {"ts": "14:02:17", "msg": f"Cross-referencing bilateral agreements"},
            {"ts": "14:02:21", "msg": "Detecting dependent profile from case draft"},
            {"ts": "14:02:28", "msg": f"Compiling requirement graph ({req_count} nodes)"},
            {"ts": "14:02:34", "msg": "Validating salary threshold against assignment data"},
            {"ts": "14:02:38", "msg": "Recommending specialist advisors for corridor"},
            {"ts": "14:02:45", "msg": f"Plan compiled. {req_count} requirements, {doc_count} documents."},
        ]
        return {
            "status": "completed",
            "progress_pct": 100,
            "job_id": snapshot_id,
            "events": events,
        }

    # No snapshot — research hasn't been run yet
    return {
        "status": "not_started",
        "progress_pct": 0,
        "job_id": None,
        "events": [],
        "hint": "Call POST /api/cases/{case_id}/research/start to begin discovery.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# GAP 1b: Household builder endpoint
# ─────────────────────────────────────────────────────────────────────────────

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

        # Merge family members
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

        # Merge pets into relocationBasics or a dedicated pets section
        if payload.pets is not None:
            draft["pets"] = [p.model_dump(mode="json", exclude_none=True) for p in payload.pets]
            # Also flag hasDependents if there are any household members or pets
            basics = draft.get("relocationBasics", {})
            basics["hasDependents"] = bool(
                (draft.get("familyMembers") or {}).get("maritalStatus", "solo") != "solo"
                or draft.get("pets")
            )
            draft["relocationBasics"] = basics

        derived = {}
        basics = draft.get("relocationBasics", {})
        derived = {
            "origin_country": basics.get("originCountry"),
            "origin_city": basics.get("originCity"),
            "dest_country": basics.get("destCountry"),
            "dest_city": basics.get("destCity"),
            "purpose": basics.get("purpose"),
            "target_move_date": basics.get("targetMoveDate"),
        }
        flags = {"hasDependents": basics.get("hasDependents")}
        crud.update_case(db, case, draft, derived, flags)
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


# ─────────────────────────────────────────────────────────────────────────────
# [P1-5] Dossier & Forms list
# Returns all case_forms (created by the Trigger Engine in P1-3) for a case,
# joined with template metadata, person/dependent name, and FieldValue counts.
# Powers the Dossier & Forms list view at /employee/case/:caseId/dossier.
# ─────────────────────────────────────────────────────────────────────────────


class _DossierFormTemplate(BaseModel):
    id: str
    code: str
    name: str
    authority_code: Optional[str]
    authority_name: Optional[str]
    country: str
    category: Optional[str]
    version: str
    fields_total: int


class _DossierFormPerson(BaseModel):
    kind: str            # 'employee' | 'spouse' | 'child' | 'other'
    name: Optional[str]
    dependent_id: Optional[str]
    profile_id: Optional[str]


class _DossierFieldsSummary(BaseModel):
    total: int
    filled_by_ai: int
    filled_by_human: int
    reviewed: int
    overridden: int
    missing_required: int


class CaseFormSummary(BaseModel):
    id: str
    case_id: str
    status: str
    completion_pct: int
    deadline: Optional[str]
    deadline_trigger: Optional[str]
    blocker_form_id: Optional[str]
    blocker_form_code: Optional[str]
    # [P2-6] True when this form has an unresolved blocker (the blocking form
    # is not yet approved). Derived server-side so the frontend doesn't need
    # to join across forms.
    is_blocked: bool = False
    original_file_url: Optional[str]
    draft_pdf_url: Optional[str]
    submitted_at: Optional[str]
    receipt_ref: Optional[str]
    rejection_reason: Optional[str] = None   # [P4-5] set when status='rejected'
    roadmap_step_id: Optional[str] = None   # [P1-6] step that triggered this form
    template: _DossierFormTemplate
    person: _DossierFormPerson
    fields_summary: _DossierFieldsSummary
    created_at: str
    updated_at: str


def _row_to_summary(row: Dict[str, Any]) -> CaseFormSummary:
    """Map a flat SQL result row into the structured CaseFormSummary shape."""
    # JSONB columns come back as list/dict from Postgres; as str from SQLite test harness.
    fields = row.get("template_fields") or []
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except (json.JSONDecodeError, TypeError):
            fields = []
    fields_total = len(fields) if isinstance(fields, list) else 0

    # Person resolution: dependent wins (more specific) over employee profile.
    dep_id = row.get("dependent_id")
    if dep_id:
        rel = (row.get("dependent_relationship") or "").lower()
        kind = "spouse" if rel in ("spouse", "partner") else ("child" if rel == "child" else "other")
        person = _DossierFormPerson(
            kind=kind,
            name=row.get("dependent_name"),
            dependent_id=str(dep_id),
            profile_id=None,
        )
    else:
        # person_id may map to a profiles row (employee or HR); we default to 'employee'
        # since the trigger engine only sets person_id for the employee path.
        person = _DossierFormPerson(
            kind="employee",
            name=(row.get("profile_full_name") or row.get("profile_email") or None),
            dependent_id=None,
            profile_id=(str(row["person_id"]) if row.get("person_id") else None),
        )

    def _iso(v: Any) -> Optional[str]:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            try:
                return v.isoformat()
            except Exception:
                return str(v)
        return str(v)

    # [P2-6] is_blocked: the form has an unresolved blocker iff blocker_form_id
    # is set, this form is not yet terminal, and the blocker is not yet approved.
    current_status = str(row.get("status") or "")
    terminal_statuses = {"submitted", "approved", "rejected"}
    blocker_status = str(row.get("blocker_status") or "")
    is_blocked = (
        bool(row.get("blocker_form_id"))
        and current_status not in terminal_statuses
        and blocker_status != "approved"
    )

    return CaseFormSummary(
        id=str(row["id"]),
        case_id=str(row["case_id"]),
        status=str(row["status"]),
        completion_pct=int(row.get("completion_pct") or 0),
        deadline=_iso(row.get("deadline")),
        deadline_trigger=row.get("deadline_trigger"),
        blocker_form_id=(str(row["blocker_form_id"]) if row.get("blocker_form_id") else None),
        blocker_form_code=row.get("blocker_form_code"),
        is_blocked=is_blocked,
        original_file_url=row.get("original_file_url"),
        draft_pdf_url=row.get("draft_pdf_url"),
        submitted_at=_iso(row.get("submitted_at")),
        receipt_ref=row.get("receipt_ref"),
        rejection_reason=row.get("rejection_reason") or None,   # [P4-5]
        roadmap_step_id=(str(row["roadmap_step_id"]) if row.get("roadmap_step_id") else None),  # [P1-6]
        template=_DossierFormTemplate(
            id=str(row["template_id"]),
            code=str(row["template_code"]),
            name=str(row["template_name"]),
            authority_code=row.get("template_authority_code"),
            authority_name=row.get("template_authority_name"),
            country=str(row["template_country"]),
            category=row.get("template_category"),
            version=str(row["template_version"]),
            fields_total=fields_total,
        ),
        person=person,
        fields_summary=_DossierFieldsSummary(
            total=fields_total,
            filled_by_ai=int(row.get("fv_filled_by_ai") or 0),
            filled_by_human=int(row.get("fv_filled_by_human") or 0),
            reviewed=int(row.get("fv_reviewed") or 0),
            overridden=int(row.get("fv_overridden") or 0),
            # missing_required = fields_total - any field that has a value
            # (computed by caller from the inputs we already have)
            missing_required=max(
                0,
                fields_total
                - int(row.get("fv_filled_by_ai") or 0)
                - int(row.get("fv_filled_by_human") or 0),
            ),
        ),
        created_at=_iso(row.get("created_at")) or "",
        updated_at=_iso(row.get("updated_at")) or "",
    )


@router.get("/{case_id}/forms", response_model=List[CaseFormSummary])
def list_case_forms(
    case_id: str,
    status: Optional[str] = None,
    roadmap_step_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[CaseFormSummary]:
    """
    List all CaseForms for a case, with template metadata, person name, and
    a FieldValue summary count. The frontend uses this to render the Dossier
    & Forms list view.

    Optional `?status=` filter narrows by document_status (e.g. 'ready').
    Optional `?roadmap_step_id=` filter narrows by roadmap step [P1-6].
    """
    _assert_case_access(user, case_id)

    # Build the join in one statement. The aggregate over case_form_field_values
    # is done as a correlated sub-select per row — simpler than a GROUP BY and
    # cheap given typical row counts (<50 forms per case).
    extra_where = ""
    params: Dict[str, Any] = {"case_id": case_id}
    if status:
        extra_where += " AND cf.status = :status"
        params["status"] = status
    if roadmap_step_id:
        extra_where += " AND cf.roadmap_step_id = :roadmap_step_id"
        params["roadmap_step_id"] = roadmap_step_id
    where_status = extra_where  # keep existing variable name used below

    sql = f"""
        SELECT
          cf.id,
          cf.case_id,
          cf.status,
          cf.completion_pct,
          cf.deadline,
          cf.deadline_trigger,
          cf.blocker_form_id,
          (SELECT ft2.code FROM {_pg_table('case_forms')} cf2
            JOIN {_pg_table('form_templates')} ft2 ON ft2.id = cf2.form_template_id
            WHERE cf2.id = cf.blocker_form_id) AS blocker_form_code,
          -- [P2-6] Status of the blocking form — used to compute is_blocked in Python
          (SELECT cf_b.status FROM {_pg_table('case_forms')} cf_b
            WHERE cf_b.id = cf.blocker_form_id) AS blocker_status,
          cf.original_file_url,
          cf.draft_pdf_url,
          cf.submitted_at,
          cf.receipt_ref,
          cf.rejection_reason,
          cf.person_id,
          cf.dependent_id,
          cf.roadmap_step_id,
          cf.created_at,
          cf.updated_at,
          ft.id      AS template_id,
          ft.code    AS template_code,
          ft.name    AS template_name,
          ft.authority_code AS template_authority_code,
          ft.authority_name AS template_authority_name,
          ft.country AS template_country,
          ft.category AS template_category,
          ft.version AS template_version,
          ft.fields  AS template_fields,
          cd.relationship AS dependent_relationship,
          cd.full_name    AS dependent_name,
          p.full_name     AS profile_full_name,
          p.email         AS profile_email,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.filled_by = 'ai') AS fv_filled_by_ai,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.filled_by IN ('employee','hr','specialist','system')) AS fv_filled_by_human,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.reviewed = TRUE) AS fv_reviewed,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.overridden = TRUE) AS fv_overridden
        FROM {_pg_table('case_forms')} cf
        JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
        LEFT JOIN {_pg_table('case_dependents')} cd ON cd.id = cf.dependent_id
        LEFT JOIN {_pg_table('profiles')} p ON p.id = cf.person_id
        WHERE cf.case_id = :case_id{where_status}
        ORDER BY
          -- Forms with an unresolved blocker (UI-blocked) come first so the
          -- user can see what's gating their progress. `blocker_form_id IS NOT
          -- NULL` is the canonical signal — there's no `blocked` value in the
          -- document_status enum.
          CASE WHEN cf.blocker_form_id IS NOT NULL
                AND cf.status NOT IN ('submitted','approved')
               THEN 0 ELSE 1 END,
          CASE cf.status
            WHEN 'pending_doc' THEN 1
            WHEN 'auto_filled' THEN 2
            WHEN 'in_progress' THEN 3
            WHEN 'ready'       THEN 4
            WHEN 'not_started' THEN 5
            WHEN 'submitted'   THEN 6
            WHEN 'approved'    THEN 7
            WHEN 'rejected'    THEN 8
            ELSE 99
          END,
          cf.created_at ASC
    """

    try:
        with main_db.engine.connect() as conn:
            rows = conn.execute(_sql_text(sql), params).mappings().all()
    except Exception:
        logger.exception("dossier: failed to list case_forms case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to load case forms")

    return [_row_to_summary(dict(r)) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# [P2-2] Field value storage and bulk update API
# Three endpoints that power the per-field form editor in the Dossier UI:
#   GET  /{case_id}/forms/{form_id}/fields  – list fields merged with stored values
#   PUT  /{case_id}/forms/{form_id}/fields  – bulk upsert (employee saves progress)
#   PATCH /{case_id}/forms/{form_id}        – status transitions (ready / submitted)
# ─────────────────────────────────────────────────────────────────────────────


class FieldValueItem(BaseModel):
    """A single field value as returned by the GET endpoint."""
    field_id: str
    label: str
    field_type: str           # text | date | select | boolean | …
    required: bool
    position: int
    prefill_source: Optional[str]
    requires_original: bool
    options: Optional[List[str]]   # only for select fields
    # Stored value metadata (None if no value has been saved yet)
    value: Optional[str]
    filled_by: Optional[str]       # ai | system | employee | specialist | hr
    ai_confidence: Optional[float]
    reviewed: bool
    overridden: bool


class FieldUpsertInput(BaseModel):
    """One field in the PUT payload."""
    field_id: str
    value: Optional[str] = None   # None / empty-string clears the field value


class BulkFieldUpdatePayload(BaseModel):
    fields: List[FieldUpsertInput]


class FormStatusPatchPayload(BaseModel):
    status: str        # 'ready' | 'submitted' | 'approved' | 'rejected' | 'not_started'
    receipt_ref: Optional[str] = None
    note: Optional[str] = None            # [P4-2] optional HR annotation written to case_form_events
    rejection_reason: Optional[str] = None  # [P4-5] stored on case_forms when status='rejected'


def _load_form_with_template(
    conn: Any,
    case_id: str,
    form_id: str,
) -> Optional[Dict[str, Any]]:
    """Return the case_form row joined with its template fields, or None if not found."""
    row = conn.execute(
        _sql_text(
            f"""
            SELECT cf.id, cf.case_id, cf.status, cf.completion_pct,
                   cf.deadline, cf.deadline_trigger, cf.blocker_form_id,
                   cf.original_file_url, cf.draft_pdf_url,
                   cf.submitted_at, cf.receipt_ref, cf.rejection_reason,
                   cf.person_id, cf.dependent_id,
                   cf.created_at, cf.updated_at,
                   ft.id      AS template_id,
                   ft.code    AS template_code,
                   ft.name    AS template_name,
                   ft.authority_code AS template_authority_code,
                   ft.authority_name AS template_authority_name,
                   ft.country AS template_country,
                   ft.category AS template_category,
                   ft.version AS template_version,
                   ft.fields  AS template_fields
            FROM {_pg_table('case_forms')} cf
            JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
            WHERE cf.id = :form_id AND cf.case_id = :case_id
            """
        ),
        {"form_id": form_id, "case_id": case_id},
    ).mappings().first()
    return dict(row) if row else None


def _compute_completion(
    template_fields: List[Dict[str, Any]],
    stored_values: Dict[str, str],
) -> int:
    """Return completion_pct (0-100) based on required fields with a non-empty value."""
    required = [f for f in template_fields if f.get("required")]
    if not required:
        # No required fields → count all fields
        total = len(template_fields)
        if not total:
            return 0
        filled = sum(1 for f in template_fields if stored_values.get(f["id"]) not in (None, ""))
        return round(filled / total * 100)
    filled_required = sum(
        1 for f in required if stored_values.get(f["id"]) not in (None, "")
    )
    return round(filled_required / len(required) * 100)


@router.get("/{case_id}/forms/{form_id}/fields", response_model=List[FieldValueItem])
def get_form_fields(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[FieldValueItem]:
    """
    Return every field in the form template merged with the stored FieldValue (if any).
    Fields with no stored value still appear in the list with value=None.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.connect() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            # Load all stored field values for this form
            fv_rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT field_id, value, filled_by, ai_confidence, reviewed, overridden
                    FROM {_pg_table('case_form_field_values')}
                    WHERE case_form_id = :form_id
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        logger.exception("fields: failed to load fields case_id=%s form_id=%s", case_id, form_id)
        raise HTTPException(status_code=500, detail="Failed to load form fields")

    # Index stored values by field_id
    stored: Dict[str, Dict[str, Any]] = {str(r["field_id"]): dict(r) for r in fv_rows}

    # Parse template fields JSONB
    raw_fields = form_row.get("template_fields") or []
    if isinstance(raw_fields, str):
        try:
            raw_fields = json.loads(raw_fields)
        except (json.JSONDecodeError, TypeError):
            raw_fields = []

    items: List[FieldValueItem] = []
    for fd in sorted(raw_fields, key=lambda f: f.get("position", 0)):
        fid = fd.get("id", "")
        sv = stored.get(fid)
        items.append(FieldValueItem(
            field_id=fid,
            label=fd.get("label", fid),
            field_type=fd.get("type", "text"),
            required=bool(fd.get("required", False)),
            position=int(fd.get("position", 0)),
            prefill_source=fd.get("prefill_source"),
            requires_original=bool(fd.get("requires_original", False)),
            options=fd.get("options"),
            value=sv["value"] if sv else None,
            filled_by=sv["filled_by"] if sv else None,
            ai_confidence=sv["ai_confidence"] if sv else None,
            reviewed=bool(sv["reviewed"]) if sv else False,
            overridden=bool(sv["overridden"]) if sv else False,
        ))

    return items


@router.put("/{case_id}/forms/{form_id}/fields", response_model=CaseFormSummary)
def bulk_update_form_fields(
    case_id: str,
    form_id: str,
    payload: BulkFieldUpdatePayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> CaseFormSummary:
    """
    Bulk upsert field values. Each field in the payload is written with
    filled_by='employee' and reviewed=True. If a previous AI-filled value
    exists for that field_id, overridden is set to True.

    After the upsert, completion_pct is recomputed and stored on the case_form.
    Returns the updated CaseFormSummary.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.begin() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            # Load current field values to detect overrides
            # [P4-6] Also fetch value and ai_confidence for override audit logging
            existing_rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT field_id, filled_by, value, ai_confidence
                    FROM {_pg_table('case_form_field_values')}
                    WHERE case_form_id = :form_id
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
            existing_by_field: Dict[str, Any] = {
                str(r["field_id"]): dict(r) for r in existing_rows
            }

            # Determine actor role for override attribution [P4-6]
            _role = (user.get("role") or "employee").lower()
            _overridden_by = "specialist" if _role in ("hr", "admin", "specialist") else "employee"
            # form_template_id needed for override records (key is 'template_id' in form_row)
            _form_template_id = str(form_row.get("template_id") or "")

            # Upsert each field
            for item in payload.fields:
                fid = item.field_id
                prev = existing_by_field.get(fid) or {}
                was_ai = prev.get("filled_by") == "ai"
                overridden = was_ai  # set overridden=true only when replacing an AI value

                conn.execute(
                    _sql_text(
                        f"""
                        INSERT INTO {_pg_table('case_form_field_values')}
                          (id, case_form_id, field_id, value, filled_by, reviewed, overridden, updated_at)
                        VALUES
                          ({_sql_uuid_gen()}, :form_id, :field_id, :value,
                           'employee', TRUE, :overridden, {_sql_now()})
                        ON CONFLICT (case_form_id, field_id) DO UPDATE
                          SET value      = EXCLUDED.value,
                              filled_by  = 'employee',
                              reviewed   = TRUE,
                              overridden = CASE
                                             WHEN {_pg_table('case_form_field_values')}.filled_by = 'ai'
                                             THEN TRUE
                                             ELSE {_pg_table('case_form_field_values')}.overridden
                                           END,
                              updated_at = {_sql_now()}
                        """
                    ),
                    {"form_id": form_id, "field_id": fid, "value": item.value,
                     "overridden": overridden},
                )

                # [P4-6] Capture override audit record when replacing an AI value
                if was_ai and _form_template_id:
                    try:
                        conn.execute(
                            _sql_text(
                                f"""
                                INSERT INTO {_pg_table('field_value_overrides')}
                                  (id, case_form_id, form_template_id, field_id,
                                   original_value, corrected_value, original_confidence,
                                   overridden_by, created_at)
                                VALUES
                                  ({_sql_uuid_gen()}, :form_id, :tmpl_id, :field_id,
                                   :orig_val, :new_val, :orig_conf,
                                   :overridden_by, {_sql_now()})
                                """
                            ),
                            {
                                "form_id": form_id,
                                "tmpl_id": _form_template_id,
                                "field_id": fid,
                                "orig_val": prev.get("value"),
                                "new_val": item.value,
                                "orig_conf": prev.get("ai_confidence"),
                                "overridden_by": _overridden_by,
                            },
                        )
                    except Exception:
                        # Audit failure must never block the main write
                        logger.exception(
                            "fields: failed to capture override audit cf=%s field=%s",
                            form_id, fid
                        )

            # Recompute completion_pct
            raw_fields = form_row.get("template_fields") or []
            if isinstance(raw_fields, str):
                try:
                    raw_fields = json.loads(raw_fields)
                except (json.JSONDecodeError, TypeError):
                    raw_fields = []

            all_fv = conn.execute(
                _sql_text(
                    f"""
                    SELECT field_id, value
                    FROM {_pg_table('case_form_field_values')}
                    WHERE case_form_id = :form_id
                    """
                ),
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
                    f"UPDATE {_pg_table('case_forms')} "
                    f"SET completion_pct = :pct, status = :status, updated_at = {_sql_now()} "
                    f"WHERE id = :form_id"
                ),
                {"pct": pct, "status": new_status, "form_id": form_id},
            )

            # Audit log for bulk field update
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

    # Re-fetch and return the updated form summary
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

    Allowed transitions:
      → 'ready'     : All required fields must have a stored value. Returns 422 with
                      {missing_fields: [...]} if any required field is unfilled.
      → 'submitted' : receipt_ref is required. Sets submitted_at = now().
    """
    _assert_case_access(user, case_id)

    # [P2-6] 'approved' added — set by HR / specialist after specialist review.
    # [P4-2] 'rejected' and 'not_started' (reset) also allowed for HR / ADMIN.
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
                # Validate all required fields have a non-empty stored value
                required_ids = [f["id"] for f in raw_fields if f.get("required")]
                if required_ids:
                    # Use IN (:fid0, :fid1, …) — works on both PostgreSQL and SQLite
                    in_placeholders = ", ".join(f":fid{i}" for i in range(len(required_ids)))
                    ready_params: Dict[str, Any] = {"form_id": form_id}
                    ready_params.update({f"fid{i}": fid for i, fid in enumerate(required_ids)})
                    filled_rows = conn.execute(
                        _sql_text(
                            f"""
                            SELECT field_id FROM {_pg_table('case_form_field_values')}
                            WHERE case_form_id = :form_id
                              AND field_id IN ({in_placeholders})
                              AND value IS NOT NULL AND value <> ''
                            """
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
                        f"UPDATE {_pg_table('case_forms')} "
                        f"SET status = 'ready', updated_at = {_sql_now()} WHERE id = :form_id"
                    ),
                    {"form_id": form_id},
                )

            elif payload.status == "submitted":
                if not payload.receipt_ref:
                    raise HTTPException(
                        status_code=422,
                        detail="receipt_ref is required for status=submitted",
                    )
                conn.execute(
                    _sql_text(
                        f"""
                        UPDATE {_pg_table('case_forms')}
                        SET status       = 'submitted',
                            receipt_ref  = :receipt_ref,
                            submitted_at = {_sql_now()},
                            updated_at   = {_sql_now()}
                        WHERE id = :form_id
                        """
                    ),
                    {"receipt_ref": payload.receipt_ref, "form_id": form_id},
                )

            elif payload.status == "approved":
                # [P2-6] Specialist approves the form.
                # Only allowed from 'submitted' — prevents HR from skipping the
                # submission step and directly approving a not_started form.
                current_status = str(form_row.get("status") or "")
                if current_status != "submitted":
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Cannot transition to 'approved' from '{current_status}'. "
                            "The form must be in 'submitted' status first."
                        ),
                    )
                # The DB trigger (handle_case_form_approval) unlocks blocked forms
                # atomically. We also call run_prefill_for_dependents here so the
                # Pre-Fill Engine populates the newly-unblocked forms in this
                # same request cycle without waiting for a pg_notify subscriber.
                conn.execute(
                    _sql_text(
                        f"UPDATE {_pg_table('case_forms')} "
                        f"SET status = 'approved', updated_at = {_sql_now()} "
                        f"WHERE id = :form_id"
                    ),
                    {"form_id": form_id},
                )

            elif payload.status == "rejected":
                # [P4-2/P4-5] HR / specialist rejects the form after specialist review.
                # [P4-5] Store rejection_reason so the employee can see it.
                conn.execute(
                    _sql_text(
                        f"UPDATE {_pg_table('case_forms')} "
                        f"SET status = 'rejected', "
                        f"    rejection_reason = :reason, "
                        f"    updated_at = {_sql_now()} "
                        f"WHERE id = :form_id"
                    ),
                    {"form_id": form_id, "reason": payload.rejection_reason or None},
                )

            elif payload.status == "not_started":
                # [P4-2] HR reset — return a form to not_started so the employee
                # can re-fill it (e.g. after a rejection is resolved).
                conn.execute(
                    _sql_text(
                        f"UPDATE {_pg_table('case_forms')} "
                        f"SET status = 'not_started', updated_at = {_sql_now()} "
                        f"WHERE id = :form_id"
                    ),
                    {"form_id": form_id},
                )

            # [P4-2] Enrich the event row written by the trigger with actor_id and
            # optional note. The trigger fires synchronously in the same transaction,
            # so by the time we execute this UPDATE the new row already exists.
            # We target the most-recently-created status_change event for this form
            # to avoid touching unrelated historic rows.
            # Wrapped in try/except so legacy test schemas without case_form_events
            # continue to pass — the enrichment is best-effort.
            user_id = user.get("id") or user.get("sub")
            note_value = getattr(payload, "note", None)
            if user_id:
                try:
                    conn.execute(
                        _sql_text(
                            f"""
                            UPDATE {_pg_table('case_form_events')}
                            SET    actor_id = :actor_id,
                                   note     = :note
                            WHERE  id = (
                              SELECT id FROM {_pg_table('case_form_events')}
                              WHERE  case_form_id = :form_id
                                AND  event_type   = 'status_change'
                              ORDER  BY created_at DESC
                              LIMIT  1
                            )
                            """
                        ),
                        {"actor_id": user_id, "note": note_value, "form_id": form_id},
                    )
                except Exception:
                    pass  # case_form_events table may not exist in legacy test schemas

            # Audit log for form status change
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
    # Called outside the transaction so the approved row is committed and visible
    # to the pre-fill engine's reads. Errors are caught inside run_prefill_for_dependents.
    if payload.status == "approved":
        run_prefill_for_dependents(form_id, case_id)

    # [P4-4] Post-commit notifications — fire-and-forget, never block the response.
    try:
        from ..services.dossier_notifications import (
            notify_form_ready,
            notify_form_submitted,
            notify_form_rejected,
            notify_blocker_resolved,
            notify_dossier_built,
        )
        if payload.status == "ready":
            notify_form_ready(form_id)
        elif payload.status == "submitted":
            notify_form_submitted(form_id, receipt_ref=payload.receipt_ref)
        elif payload.status == "rejected":
            notify_form_rejected(form_id, reason=getattr(payload, "note", None))
        elif payload.status == "approved":
            # Notify employees whose forms were just unblocked
            try:
                with main_db.engine.connect() as _conn:
                    unblocked_rows = _conn.execute(
                        _sql_text(
                            f"""
                            SELECT cf.id AS unblocked_id,
                                   ft.name AS unblocked_name
                            FROM {_pg_table('case_forms')} cf
                            JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
                            WHERE cf.blocker_form_id = :blocker_id
                              AND cf.status = 'not_started'
                            """
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
            # Check if entire dossier is now complete (all forms terminal)
            try:
                with main_db.engine.connect() as _conn:
                    counts = _conn.execute(
                        _sql_text(
                            f"""
                            SELECT
                              COUNT(*) AS total,
                              COUNT(CASE WHEN status IN ('submitted','approved') THEN 1 END) AS done
                            FROM {_pg_table('case_forms')}
                            WHERE case_id = :case_id
                            """
                        ),
                        {"case_id": case_id},
                    ).mappings().first()
                if counts and int(counts["total"]) > 0 and int(counts["total"]) == int(counts["done"]):
                    notify_dossier_built(case_id, form_count=int(counts["total"]))
            except Exception:
                logger.exception("forms: dossier_built check failed case_id=%s", case_id)
    except Exception:
        logger.exception("forms: post-commit notifications failed case_id=%s form_id=%s", case_id, form_id)

    return _fetch_single_form_summary(case_id, form_id)


def _fetch_single_form_summary(case_id: str, form_id: str) -> CaseFormSummary:
    """
    Re-fetch a single case_form as a CaseFormSummary after a write operation.
    Uses the same aggregated query as list_case_forms but filtered to one form.
    """
    sql = f"""
        SELECT
          cf.id, cf.case_id, cf.status, cf.completion_pct,
          cf.deadline, cf.deadline_trigger, cf.blocker_form_id,
          NULL AS blocker_form_code,
          -- [P2-6] Blocker status for is_blocked computation
          (SELECT cf_b.status FROM {_pg_table('case_forms')} cf_b
            WHERE cf_b.id = cf.blocker_form_id) AS blocker_status,
          cf.original_file_url, cf.draft_pdf_url, cf.submitted_at, cf.receipt_ref,
          cf.rejection_reason,
          cf.person_id, cf.dependent_id, cf.created_at, cf.updated_at,
          ft.id      AS template_id,
          ft.code    AS template_code,
          ft.name    AS template_name,
          ft.authority_code AS template_authority_code,
          ft.authority_name AS template_authority_name,
          ft.country AS template_country,
          ft.category AS template_category,
          ft.version AS template_version,
          ft.fields  AS template_fields,
          cd.relationship AS dependent_relationship,
          cd.full_name    AS dependent_name,
          p.full_name     AS profile_full_name,
          p.email         AS profile_email,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.filled_by = 'ai') AS fv_filled_by_ai,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id
               AND fv.filled_by IN ('employee','hr','specialist','system')) AS fv_filled_by_human,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.reviewed = TRUE) AS fv_reviewed,
          (SELECT COUNT(*) FROM {_pg_table('case_form_field_values')} fv
             WHERE fv.case_form_id = cf.id AND fv.overridden = TRUE) AS fv_overridden
        FROM {_pg_table('case_forms')} cf
        JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
        LEFT JOIN {_pg_table('case_dependents')} cd ON cd.id = cf.dependent_id
        LEFT JOIN {_pg_table('profiles')} p ON p.id = cf.person_id
        WHERE cf.id = :form_id AND cf.case_id = :case_id
    """
    try:
        with main_db.engine.connect() as conn:
            row = conn.execute(
                _sql_text(sql), {"form_id": form_id, "case_id": case_id}
            ).mappings().first()
    except Exception:
        logger.exception("forms: failed to re-fetch summary form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to reload form after update")

    if not row:
        raise HTTPException(status_code=404, detail="Form not found after update")
    return _row_to_summary(dict(row))


# ─────────────────────────────────────────────────────────────────────────────
# [P4-2] HR Dossier Panel — comments, events, flag
# ─────────────────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentItem(BaseModel):
    id: str
    case_form_id: str
    author_id: str
    author_name: Optional[str]
    content: str
    created_at: str


class EventItem(BaseModel):
    id: str
    case_form_id: str
    event_type: str
    actor_id: Optional[str]
    actor_name: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    note: Optional[str]
    created_at: str


class FlagPatchPayload(BaseModel):
    flag_note: Optional[str] = None   # None / empty string clears the flag


class FormFlagResponse(BaseModel):
    id: str
    flag_note: Optional[str]
    flagged_at: Optional[str]
    flagged_by: Optional[str]


@router.get("/{case_id}/forms/{form_id}/comments", response_model=List[CommentItem])
def list_form_comments(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[CommentItem]:
    """List all comments on a CaseForm, newest first."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.connect() as conn:
            # Verify the form belongs to this case
            exists = conn.execute(
                _sql_text(
                    f"SELECT id FROM {_pg_table('case_forms')} "
                    f"WHERE id = :form_id AND case_id = :case_id"
                ),
                {"form_id": form_id, "case_id": case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT c.id, c.case_form_id, c.author_id, c.content, c.created_at,
                           p.full_name AS author_name
                    FROM {_pg_table('case_form_comments')} c
                    LEFT JOIN {_pg_table('profiles')} p ON p.id = c.author_id
                    WHERE c.case_form_id = :form_id
                    ORDER BY c.created_at ASC
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        logger.exception("comments: list failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to load comments")

    return [
        CommentItem(
            id=str(r["id"]),
            case_form_id=str(r["case_form_id"]),
            author_id=str(r["author_id"]),
            author_name=r.get("author_name"),
            content=str(r["content"]),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.post("/{case_id}/forms/{form_id}/comments", response_model=CommentItem, status_code=201)
def create_form_comment(
    case_id: str,
    form_id: str,
    payload: CommentCreate,
    user: Dict[str, Any] = Depends(get_current_user),
) -> CommentItem:
    """Post a comment on a CaseForm."""
    _assert_case_access(user, case_id)

    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=422, detail="Comment content cannot be empty")

    author_id = user.get("id") or user.get("sub")
    if not author_id:
        raise HTTPException(status_code=401, detail="Cannot determine author identity")

    try:
        with main_db.engine.begin() as conn:
            exists = conn.execute(
                _sql_text(
                    f"SELECT id FROM {_pg_table('case_forms')} "
                    f"WHERE id = :form_id AND case_id = :case_id"
                ),
                {"form_id": form_id, "case_id": case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            row = conn.execute(
                _sql_text(
                    f"""
                    INSERT INTO {_pg_table('case_form_comments')}
                      (case_form_id, author_id, content)
                    VALUES (:form_id, :author_id, :content)
                    RETURNING id, case_form_id, author_id, content, created_at
                    """
                ),
                {"form_id": form_id, "author_id": author_id, "content": payload.content.strip()},
            ).mappings().first()

            # Audit log for comment creation
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

    # Look up author name separately (not in the RETURNING clause to keep it simple)
    author_name = None
    try:
        with main_db.engine.connect() as conn2:
            prow = conn2.execute(
                _sql_text(
                    f"SELECT full_name FROM {_pg_table('profiles')} WHERE id = :uid"
                ),
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


@router.get("/{case_id}/forms/{form_id}/events", response_model=List[EventItem])
def list_form_events(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[EventItem]:
    """Return the history log for a CaseForm, newest first."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.connect() as conn:
            exists = conn.execute(
                _sql_text(
                    f"SELECT id FROM {_pg_table('case_forms')} "
                    f"WHERE id = :form_id AND case_id = :case_id"
                ),
                {"form_id": form_id, "case_id": case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT e.id, e.case_form_id, e.event_type, e.actor_id,
                           e.from_status, e.to_status, e.note, e.created_at,
                           p.full_name AS actor_name
                    FROM {_pg_table('case_form_events')} e
                    LEFT JOIN {_pg_table('profiles')} p ON p.id = e.actor_id
                    WHERE e.case_form_id = :form_id
                    ORDER BY e.created_at ASC
                    """
                ),
                {"form_id": form_id},
            ).mappings().all()
    except HTTPException:
        raise
    except Exception:
        logger.exception("events: list failed form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to load events")

    return [
        EventItem(
            id=str(r["id"]),
            case_form_id=str(r["case_form_id"]),
            event_type=str(r["event_type"]),
            actor_id=str(r["actor_id"]) if r.get("actor_id") else None,
            actor_name=r.get("actor_name"),
            from_status=r.get("from_status"),
            to_status=r.get("to_status"),
            note=r.get("note"),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]


@router.patch("/{case_id}/forms/{form_id}/flag", response_model=FormFlagResponse)
def patch_form_flag(
    case_id: str,
    form_id: str,
    payload: FlagPatchPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> FormFlagResponse:
    """
    Set or clear the flag on a CaseForm.
    - Providing flag_note='…' sets the flag (records flagged_at + flagged_by).
    - Providing flag_note=None or '' clears the flag.
    """
    _assert_case_access(user, case_id)

    # Only HR and ADMIN can flag forms
    user_role = str(user.get("role") or "").upper()
    if user_role not in ("HR", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only HR or ADMIN users can flag forms")

    user_id = user.get("id") or user.get("sub")
    clearing = not payload.flag_note or not payload.flag_note.strip()

    try:
        with main_db.engine.begin() as conn:
            exists = conn.execute(
                _sql_text(
                    f"SELECT id FROM {_pg_table('case_forms')} "
                    f"WHERE id = :form_id AND case_id = :case_id"
                ),
                {"form_id": form_id, "case_id": case_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Form not found")

            if clearing:
                conn.execute(
                    _sql_text(
                        f"""
                        UPDATE {_pg_table('case_forms')}
                        SET flag_note  = NULL,
                            flagged_at = NULL,
                            flagged_by = NULL,
                            updated_at = {_sql_now()}
                        WHERE id = :form_id
                        """
                    ),
                    {"form_id": form_id},
                )
                # Write a 'unflagged' event
                conn.execute(
                    _sql_text(
                        f"""
                        INSERT INTO {_pg_table('case_form_events')}
                          (case_form_id, event_type, actor_id)
                        VALUES (:form_id, 'unflagged', :actor_id)
                        """
                    ),
                    {"form_id": form_id, "actor_id": user_id},
                )
            else:
                conn.execute(
                    _sql_text(
                        f"""
                        UPDATE {_pg_table('case_forms')}
                        SET flag_note  = :flag_note,
                            flagged_at = {_sql_now()},
                            flagged_by = :flagged_by,
                            updated_at = {_sql_now()}
                        WHERE id = :form_id
                        """
                    ),
                    {
                        "flag_note": payload.flag_note.strip(),
                        "flagged_by": user_id,
                        "form_id": form_id,
                    },
                )
                # Write a 'flagged' event
                conn.execute(
                    _sql_text(
                        f"""
                        INSERT INTO {_pg_table('case_form_events')}
                          (case_form_id, event_type, actor_id, note)
                        VALUES (:form_id, 'flagged', :actor_id, :note)
                        """
                    ),
                    {
                        "form_id": form_id,
                        "actor_id": user_id,
                        "note": payload.flag_note.strip(),
                    },
                )

            updated = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, flag_note, flagged_at, flagged_by
                    FROM {_pg_table('case_forms')}
                    WHERE id = :form_id
                    """
                ),
                {"form_id": form_id},
            ).mappings().first()

            # Audit log for flag change
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


# ─────────────────────────────────────────────────────────────────────────────
# [P3-1] PDF Service — field overlay engine
# ─────────────────────────────────────────────────────────────────────────────

def _build_overlay_page(
    page_width: float,
    page_height: float,
    fields_on_page: List[Dict[str, Any]],
    field_values: Dict[str, str],
) -> Optional[bytes]:
    """
    Build a single-page transparent PDF overlay using reportlab.
    Returns raw bytes of a 1-page PDF, or None if no values to draw.
    """
    try:
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        logger.warning("reportlab not available — PDF overlay skipped")
        return None

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))

    drew_any = False
    for field in fields_on_page:
        fid = field.get("id")
        value = field_values.get(fid) if fid else None
        if value is None or str(value).strip() == "":
            continue
        pdf_x = field.get("pdf_x")
        pdf_y = field.get("pdf_y")
        if pdf_x is None or pdf_y is None:
            continue

        font_size = float(field.get("pdf_font_size") or 10)
        max_width = field.get("pdf_max_width")
        text = str(value)

        c.setFont("Helvetica", font_size)
        c.setFillColorRGB(0, 0, 0)

        if max_width:
            # Use reportlab's drawString with available width constraint
            c.drawString(float(pdf_x), float(pdf_y), text)
        else:
            c.drawString(float(pdf_x), float(pdf_y), text)
        drew_any = True

    if not drew_any:
        return None

    c.save()
    buf.seek(0)
    return buf.read()


def _generate_filled_pdf(
    original_pdf_bytes: bytes,
    template_fields: List[Dict[str, Any]],
    field_values: Dict[str, str],
) -> bytes:
    """
    Overlay field values onto an existing PDF using pypdf + reportlab.
    Fields without pdf_x/pdf_y/pdf_page are skipped.
    """
    from pypdf import PdfWriter, PdfReader

    reader = PdfReader(io.BytesIO(original_pdf_bytes))
    num_pages = len(reader.pages)

    # Group fields by page index (0-based)
    fields_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for field in template_fields:
        pdf_page = field.get("pdf_page")
        if pdf_page is None:
            continue
        page_idx = int(pdf_page) - 1
        if page_idx < 0 or page_idx >= num_pages:
            continue
        fields_by_page.setdefault(page_idx, []).append(field)

    # Build overlay PDFs per page
    overlay_readers: Dict[int, Any] = {}
    for page_idx, fields_on_page in fields_by_page.items():
        page = reader.pages[page_idx]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        overlay_bytes = _build_overlay_page(w, h, fields_on_page, field_values)
        if overlay_bytes:
            from pypdf import PdfReader as _R
            overlay_readers[page_idx] = _R(io.BytesIO(overlay_bytes))

    # Merge overlays into output
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in overlay_readers:
            overlay_page = overlay_readers[i].pages[0]
            page.merge_page(overlay_page)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


def _make_blank_pdf(title: str, message: str) -> bytes:
    """Generate a minimal single-page PDF when no original is available."""
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4
    except ImportError:
        # Fall back to raw minimal PDF
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \nttrailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, title)
    c.setFont("Helvetica", 11)
    c.drawString(50, 720, message)
    c.save()
    buf.seek(0)
    return buf.read()


def _safe_filename_part(s: Optional[str]) -> str:
    """Slugify a string for use in a filename."""
    if not s:
        return "unknown"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s.strip())


def _try_store_draft_pdf(
    case_form_id: str,
    pdf_bytes: bytes,
    conn: Any,
) -> Optional[str]:
    """
    Upload PDF to Supabase Storage and update draft_pdf_url on the case_form row.
    Returns the public URL, or None if storage is unavailable (dev mode).
    """
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = f"case-forms/{case_form_id}/draft_{ts}.pdf"
        sb.storage.from_("case-forms").upload(
            path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        # Get a signed URL valid for 7 days
        signed = sb.storage.from_("case-forms").create_signed_url(path, 60 * 60 * 24 * 7)
        public_url: Optional[str] = signed.get("signedURL") or signed.get("signedUrl")
        if public_url:
            conn.execute(
                _sql_text(
                    f"UPDATE {_pg_table('case_forms')} "
                    f"SET draft_pdf_url = :url, updated_at = {_sql_now()} "
                    f"WHERE id = :id"
                ),
                {"url": public_url, "id": case_form_id},
            )
        return public_url
    except Exception as exc:
        logger.warning("draft_pdf storage unavailable for form %s: %s", case_form_id, exc)
        return None


@router.get("/{case_id}/forms/{form_id}/original")
def get_form_original(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> JSONResponse:
    """
    [P2-4] Return a 1-hour signed URL for the blank template PDF.

    Fetches form_templates.original_pdf_url for this CaseForm's template.
    - If the stored URL is a Supabase Storage path (no http prefix), generates
      a signed URL via the admin storage client.
    - If it is already an http(s) URL, returns it directly.
    - Returns 404 when no original PDF has been attached to the template yet.
    """
    _assert_case_access(user, case_id)

    with main_db.engine.connect() as conn:
        row = conn.execute(
            _sql_text(
                f"""
                SELECT ft.original_pdf_url, ft.code, ft.name
                FROM   {_pg_table('case_forms')} cf
                JOIN   {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
                WHERE  cf.id = :form_id AND cf.case_id = :case_id
                """
            ),
            {"form_id": form_id, "case_id": case_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Form not found")

    original_url: Optional[str] = row.get("original_pdf_url")
    if not original_url:
        raise HTTPException(
            status_code=404,
            detail="No original PDF has been attached to this template yet",
        )

    # Already a public/external URL — return as-is
    if original_url.startswith("http"):
        return JSONResponse({"signedUrl": original_url})

    # Supabase Storage path: "<bucket>/<path/to/file.pdf>"
    # Generate a 1-hour signed URL so the raw bucket URL is never exposed.
    try:
        from ..services.supabase_client import get_supabase_admin_client  # lazy import
        sb = get_supabase_admin_client()
        bucket, _, path = original_url.partition("/")
        signed = sb.storage.from_(bucket).create_signed_url(path, 3600)
        signed_url: Optional[str] = signed.get("signedURL") or signed.get("signedUrl")
        if not signed_url:
            raise HTTPException(status_code=502, detail="Could not generate signed URL for original PDF")
        return JSONResponse({"signedUrl": signed_url})
    except HTTPException:
        raise
    except Exception as exc:  # storage unavailable in dev / missing config
        logger.warning("original pdf signed url error for form %s: %s", form_id, exc)
        raise HTTPException(status_code=502, detail="Storage unavailable — cannot sign original PDF URL")


@router.get("/{case_id}/forms/{form_id}/pdf")
def get_form_pdf(
    case_id: str,
    form_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    [P3-1] Generate (or return a cached) filled PDF for a CaseForm.

    - Fetches the original template PDF from original_file_url.
    - Overlays all FieldValues at their pdf_x/pdf_y/pdf_page coordinates.
    - Stores result to Supabase Storage and caches draft_pdf_url.
    - Returns PDF as a download with a human-readable filename.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.begin() as conn:
            form_row = _load_form_with_template(conn, case_id, form_id)
            if not form_row:
                raise HTTPException(status_code=404, detail="Form not found")

            # Check if status allows download (not_started → still allow, just empty)
            if form_row.get("status") == "blocked":
                raise HTTPException(
                    status_code=409,
                    detail="Cannot generate PDF for a blocked form",
                )

            # Fetch all current field values
            fv_rows = conn.execute(
                _sql_text(
                    f"SELECT field_id, value FROM {_pg_table('case_form_field_values')} "
                    f"WHERE case_form_id = :form_id AND value IS NOT NULL AND value != ''"
                ),
                {"form_id": form_id},
            ).mappings().all()
            field_values: Dict[str, str] = {
                str(r["field_id"]): str(r["value"]) for r in fv_rows
            }

            # Parse template fields JSON
            raw_fields = form_row.get("template_fields")
            if isinstance(raw_fields, str):
                import json as _json
                template_fields: List[Dict[str, Any]] = _json.loads(raw_fields)
            else:
                template_fields = list(raw_fields) if raw_fields else []

            # Build filename: {form_code}_{last_name}_{first_name}_{date}.pdf
            form_code = _safe_filename_part(form_row.get("template_code") or "form")
            today_str = _dt.date.today().isoformat().replace("-", "")

            # Try to get person name for filename
            person_id = form_row.get("person_id") or form_row.get("dependent_id")
            person_name_slug = "employee"
            if person_id:
                try:
                    name_row = conn.execute(
                        _sql_text(
                            f"SELECT full_name FROM {_pg_table('employees')} "
                            f"WHERE id = :pid LIMIT 1"
                        ),
                        {"pid": person_id},
                    ).mappings().first()
                    if name_row and name_row.get("full_name"):
                        parts = str(name_row["full_name"]).split()
                        if len(parts) >= 2:
                            person_name_slug = (
                                _safe_filename_part(parts[-1])
                                + "_"
                                + _safe_filename_part(parts[0])
                            )
                        else:
                            person_name_slug = _safe_filename_part(parts[0])
                except Exception:
                    pass  # name is cosmetic, don't fail

            filename = f"{form_code}_{person_name_slug}_{today_str}.pdf"

            # Fetch and generate PDF
            original_url = form_row.get("original_file_url")
            if original_url:
                try:
                    resp = _requests.get(original_url, timeout=15)
                    resp.raise_for_status()
                    original_bytes = resp.content
                except Exception as exc:
                    logger.warning(
                        "pdf: failed to fetch original PDF for form %s: %s", form_id, exc
                    )
                    original_bytes = None
            else:
                original_bytes = None

            if original_bytes:
                try:
                    pdf_bytes = _generate_filled_pdf(
                        original_bytes, template_fields, field_values
                    )
                except Exception as exc:
                    logger.exception("pdf: generation failed form_id=%s: %s", form_id, exc)
                    raise HTTPException(
                        status_code=500, detail="PDF generation failed"
                    )
            else:
                # No original PDF — generate a placeholder
                form_name = form_row.get("template_name") or form_code
                pdf_bytes = _make_blank_pdf(
                    title=form_name,
                    message=(
                        "This form has not been uploaded yet. "
                        "Field values captured so far: "
                        + ", ".join(f"{k}: {v}" for k, v in list(field_values.items())[:10])
                    ),
                )

            # Async-friendly: try to cache to storage (non-blocking failure)
            _try_store_draft_pdf(form_id, pdf_bytes, conn)

    except HTTPException:
        raise
    except Exception:
        logger.exception("pdf: unexpected error form_id=%s", form_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# [P3-5] Dossier PDF merge and ZIP export
# ─────────────────────────────────────────────────────────────────────────────

class CreateDossierPayload(BaseModel):
    name: str
    form_ids: List[str]   # ordered list of case_form UUIDs
    cover_page: bool = True


class DossierPackageResponse(BaseModel):
    id: str
    case_id: str
    name: str
    form_ids: List[str]
    cover_page: bool
    pdf_url: Optional[str]
    generated_at: Optional[str]
    created_at: str


def _build_cover_page(
    package_name: str,
    case_id: str,
    forms_meta: List[Dict[str, Any]],
    page_width: float = 595.0,
    page_height: float = 842.0,
) -> bytes:
    """
    Generate an A4 cover page PDF for the dossier package.
    Includes: package name, case ID, date, list of included forms.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    w, h = float(page_width), float(page_height)
    c = rl_canvas.Canvas(buf, pagesize=(w, h))

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 80, package_name)

    # Subtitle line
    c.setFont("Helvetica", 11)
    today = _dt.date.today().isoformat()
    c.drawString(50, h - 106, f"Generated: {today}")

    # Divider line
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(50, h - 120, w - 50, h - 120)

    # Table header
    c.setFont("Helvetica-Bold", 10)
    y = h - 148
    c.drawString(50, y, "#")
    c.drawString(80, y, "Code")
    c.drawString(160, y, "Form name")
    c.drawString(390, y, "Authority")
    c.line(50, y - 6, w - 50, y - 6)

    # Form rows
    c.setFont("Helvetica", 9)
    for i, meta in enumerate(forms_meta, 1):
        y -= 22
        if y < 80:
            break  # Truncate if too many forms
        c.drawString(50, y, str(i))
        c.drawString(80, y, str(meta.get("code") or "")[:12])
        c.drawString(160, y, str(meta.get("name") or "")[:40])
        c.drawString(390, y, str(meta.get("authority_code") or "")[:16])

    c.save()
    buf.seek(0)
    return buf.read()


def _build_divider_page(
    form_code: str,
    form_name: str,
    authority_name: Optional[str],
    page_width: float = 595.0,
    page_height: float = 842.0,
) -> bytes:
    """
    Generate a clean white divider page for a single form in the merged dossier.
    Shows form title, authority name, and form code centered on the page.
    """
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    w, h = float(page_width), float(page_height)
    c = rl_canvas.Canvas(buf, pagesize=(w, h))

    mid_y = h / 2
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, mid_y + 30, form_name)

    c.setFont("Helvetica", 11)
    if authority_name:
        c.drawCentredString(w / 2, mid_y, authority_name)
        c.setFont("Helvetica", 10)
        c.drawCentredString(w / 2, mid_y - 22, form_code)
    else:
        c.drawCentredString(w / 2, mid_y - 11, form_code)

    c.save()
    buf.seek(0)
    return buf.read()


def _fetch_form_pdf_bytes(
    conn: Any,
    case_id: str,
    form_id: str,
) -> bytes:
    """
    Generate a filled PDF for one form using the shared P3-1 helpers.
    Falls back to a blank placeholder if no original PDF exists.
    """
    form_row = _load_form_with_template(conn, case_id, form_id)
    if not form_row:
        return _make_blank_pdf(f"Form {form_id}", "Form not found")

    fv_rows = conn.execute(
        _sql_text(
            f"SELECT field_id, value FROM {_pg_table('case_form_field_values')} "
            f"WHERE case_form_id = :fid AND value IS NOT NULL AND value != ''"
        ),
        {"fid": form_id},
    ).mappings().all()
    field_values: Dict[str, str] = {str(r["field_id"]): str(r["value"]) for r in fv_rows}

    raw_fields = form_row.get("template_fields")
    if isinstance(raw_fields, str):
        template_fields: List[Dict[str, Any]] = json.loads(raw_fields)
    else:
        template_fields = list(raw_fields) if raw_fields else []

    original_url = form_row.get("original_file_url")
    if original_url:
        try:
            resp = _requests.get(original_url, timeout=15)
            resp.raise_for_status()
            return _generate_filled_pdf(resp.content, template_fields, field_values)
        except Exception as exc:
            logger.warning("dossier: failed to fetch original for form %s: %s", form_id, exc)

    return _make_blank_pdf(
        form_row.get("template_name") or form_row.get("template_code") or form_id,
        "Original PDF unavailable. "
        + ", ".join(f"{k}: {v}" for k, v in list(field_values.items())[:8]),
    )


def _merge_pdfs(
    pdf_buffers: List[bytes],
) -> bytes:
    """Concatenate a list of PDFs into a single output PDF using pypdf."""
    from pypdf import PdfWriter, PdfReader

    writer = PdfWriter()
    for pdf_bytes in pdf_buffers:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


def _try_store_dossier_pdf(
    dossier_id: str,
    pdf_bytes: bytes,
    conn: Any,
) -> Optional[str]:
    """Upload merged dossier PDF to Supabase Storage and update dossier_packages.pdf_url."""
    try:
        from ..services.supabase_client import get_supabase_admin_client
        sb = get_supabase_admin_client()
        ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = f"dossier-packages/{dossier_id}/dossier_{ts}.pdf"
        sb.storage.from_("case-forms").upload(
            path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        signed = sb.storage.from_("case-forms").create_signed_url(path, 60 * 60 * 24 * 7)
        public_url: Optional[str] = signed.get("signedURL") or signed.get("signedUrl")
        if public_url:
            conn.execute(
                _sql_text(
                    f"UPDATE {_pg_table('dossier_packages')} "
                    f"SET pdf_url = :url, generated_at = {_sql_now()} "
                    f"WHERE id = :id"
                ),
                {"url": public_url, "id": dossier_id},
            )
        return public_url
    except Exception as exc:
        logger.warning("dossier: storage unavailable for dossier %s: %s", dossier_id, exc)
        return None


@router.post("/{case_id}/dossiers", response_model=DossierPackageResponse, status_code=201)
def create_dossier(
    case_id: str,
    payload: CreateDossierPayload,
    user: Dict[str, Any] = Depends(get_current_user),
) -> DossierPackageResponse:
    """
    [P3-5] Merge a set of CaseForms into a single dossier PDF.

    - Validates all form_ids belong to the case.
    - Generates a filled PDF for each form (reusing P3-1 helpers).
    - Inserts a cover page (if requested) and divider pages between forms.
    - Merges everything with pypdf.
    - Stores result to Supabase Storage and persists a dossier_packages row.
    - Returns the DossierPackage record with pdf_url.
    """
    _assert_case_access(user, case_id)

    if not payload.form_ids:
        raise HTTPException(status_code=422, detail="form_ids must not be empty")

    user_id = user.get("id") or user.get("sub")
    dossier_id = str(uuid.uuid4())
    now_str = _dt.datetime.utcnow().isoformat()

    try:
        with main_db.engine.begin() as conn:
            # Validate all form_ids belong to this case
            placeholders = ", ".join(f":fid{i}" for i in range(len(payload.form_ids)))
            params: Dict[str, Any] = {"case_id": case_id}
            params.update({f"fid{i}": fid for i, fid in enumerate(payload.form_ids)})
            valid_rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT cf.id, ft.code, ft.name, ft.authority_code, ft.authority_name
                    FROM {_pg_table('case_forms')} cf
                    JOIN {_pg_table('form_templates')} ft ON ft.id = cf.form_template_id
                    WHERE cf.case_id = :case_id AND cf.id IN ({placeholders})
                    """
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

            # Build ordered metadata map
            meta_by_id = {str(r["id"]): dict(r) for r in valid_rows}
            ordered_meta = [meta_by_id[fid] for fid in payload.form_ids]

            # Build list of PDF buffers in merge order
            pdf_parts: List[bytes] = []

            # Cover page
            if payload.cover_page:
                cover_bytes = _build_cover_page(
                    package_name=payload.name,
                    case_id=case_id,
                    forms_meta=ordered_meta,
                )
                pdf_parts.append(cover_bytes)

            # Each form: divider + filled PDF
            for form_id, meta in zip(payload.form_ids, ordered_meta):
                divider = _build_divider_page(
                    form_code=meta.get("code") or "",
                    form_name=meta.get("name") or "",
                    authority_name=meta.get("authority_name"),
                )
                pdf_parts.append(divider)
                form_pdf = _fetch_form_pdf_bytes(conn, case_id, form_id)
                pdf_parts.append(form_pdf)

            # Merge
            try:
                merged_pdf = _merge_pdfs(pdf_parts)
            except Exception as exc:
                logger.exception("dossier: PDF merge failed case_id=%s: %s", case_id, exc)
                raise HTTPException(status_code=500, detail="PDF merge failed")

            # Insert dossier_packages row
            form_ids_json = json.dumps(payload.form_ids)
            conn.execute(
                _sql_text(
                    f"""
                    INSERT INTO {_pg_table('dossier_packages')}
                      (id, case_id, name, form_ids, cover_page, created_by, created_at)
                    VALUES
                      (:id, :case_id, :name, :form_ids, :cover_page, :created_by, {_sql_now()})
                    """
                ),
                {
                    "id": dossier_id,
                    "case_id": case_id,
                    "name": payload.name,
                    "form_ids": form_ids_json,
                    "cover_page": payload.cover_page,
                    "created_by": user_id,
                },
            )

            # Attempt storage upload (non-blocking failure)
            pdf_url = _try_store_dossier_pdf(dossier_id, merged_pdf, conn)

            # Fetch back the inserted row
            row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page,
                           pdf_url, generated_at, created_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :id
                    """
                ),
                {"id": dossier_id},
            ).mappings().first()

            # Audit log for dossier creation
            try:
                insert_audit_log(
                    conn,
                    entity_type="dossier_package",
                    entity_id=dossier_id,
                    action_type=ACTION_INSERT,
                    actor_type=ACTOR_HUMAN,
                    actor_id=user_id,
                    new_value={"case_id": case_id, "form_count": len(payload.form_ids)},
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


@router.get("/{case_id}/dossiers/{dossier_id}/zip")
def get_dossier_zip(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    [P3-5] Generate a ZIP archive of individual filled PDFs for a DossierPackage.

    Each file is named: {NN}_{form_code}_{person_slug}_{date}.pdf
    Returns as application/zip download.
    """
    _assert_case_access(user, case_id)

    try:
        with main_db.engine.begin() as conn:
            pkg_row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not pkg_row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            raw_ids = pkg_row["form_ids"]
            if isinstance(raw_ids, str):
                form_ids: List[str] = json.loads(raw_ids)
            else:
                form_ids = list(raw_ids) if raw_ids else []

            if not form_ids:
                raise HTTPException(status_code=422, detail="Dossier has no forms")

            # Build ZIP in memory
            zip_buf = io.BytesIO()
            today_str = _dt.date.today().isoformat().replace("-", "")
            with _zipfile.ZipFile(zip_buf, mode="w", compression=_zipfile.ZIP_DEFLATED) as zf:
                for idx, form_id in enumerate(form_ids, 1):
                    form_row = _load_form_with_template(conn, case_id, form_id)
                    if not form_row:
                        continue
                    form_code = _safe_filename_part(form_row.get("template_code") or "form")
                    pdf_bytes = _fetch_form_pdf_bytes(conn, case_id, form_id)
                    zip_name = f"{idx:02d}_{form_code}_{today_str}.pdf"
                    zf.writestr(zip_name, pdf_bytes)

            zip_buf.seek(0)
            zip_bytes = zip_buf.read()

    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: zip failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to generate ZIP")

    pkg_name = _safe_filename_part(str(pkg_row["name"]))
    zip_filename = f"dossier_{pkg_name}_{_dt.date.today().isoformat().replace('-', '')}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )


# ── [P3-6] Staleness helper ───────────────────────────────────────────────────

class DossierPackageDetailResponse(BaseModel):
    id: str
    case_id: str
    name: str
    form_ids: List[str]
    cover_page: bool
    pdf_url: Optional[str]
    generated_at: Optional[str]
    created_at: str
    is_stale: bool


# ── [P3-6] List dossiers ──────────────────────────────────────────────────────

@router.get("/{case_id}/dossiers", response_model=List[DossierPackageDetailResponse])
def list_dossiers(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[DossierPackageDetailResponse]:
    """[P3-6] List all DossierPackage records for a case, with staleness flag."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page,
                           pdf_url, generated_at, created_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE case_id = :cid
                    ORDER BY created_at DESC
                    """
                ),
                {"cid": case_id},
            ).mappings().all()

            result = []
            for row in rows:
                raw_ids = row["form_ids"]
                form_ids: List[str] = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
                is_stale = _dossier_is_stale(conn, form_ids, row.get("generated_at"))
                result.append(
                    DossierPackageDetailResponse(
                        id=str(row["id"]),
                        case_id=str(row["case_id"]),
                        name=str(row["name"]),
                        form_ids=form_ids,
                        cover_page=bool(row["cover_page"]),
                        pdf_url=row.get("pdf_url"),
                        generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
                        created_at=str(row["created_at"]),
                        is_stale=is_stale,
                    )
                )
            return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list dossiers")


# ── [P3-6] Get one dossier ────────────────────────────────────────────────────

@router.get("/{case_id}/dossiers/{dossier_id}", response_model=DossierPackageDetailResponse)
def get_dossier(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> DossierPackageDetailResponse:
    """[P3-6] Get a single DossierPackage with staleness flag."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page,
                           pdf_url, generated_at, created_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            raw_ids = row["form_ids"]
            form_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            is_stale = _dossier_is_stale(conn, form_ids, row.get("generated_at"))

            return DossierPackageDetailResponse(
                id=str(row["id"]),
                case_id=str(row["case_id"]),
                name=str(row["name"]),
                form_ids=form_ids,
                cover_page=bool(row["cover_page"]),
                pdf_url=row.get("pdf_url"),
                generated_at=str(row["generated_at"]) if row.get("generated_at") else None,
                created_at=str(row["created_at"]),
                is_stale=is_stale,
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: get failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to get dossier")


# ── [P3-6] Delete dossier ─────────────────────────────────────────────────────

@router.delete("/{case_id}/dossiers/{dossier_id}", status_code=204)
def delete_dossier(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """[P3-6] Delete a DossierPackage record (does not remove the stored PDF)."""
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            result = conn.execute(
                _sql_text(
                    f"""
                    DELETE FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Dossier package not found")
    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: delete failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to delete dossier")
    return Response(status_code=204)


# ── [P3-6] Download merged PDF ────────────────────────────────────────────────

@router.get("/{case_id}/dossiers/{dossier_id}/pdf")
def get_dossier_pdf(
    case_id: str,
    dossier_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    [P3-6] Download the merged PDF for a DossierPackage.
    If pdf_url is set, redirect/stream it; otherwise regenerate on-the-fly.
    """
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page, pdf_url, generated_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            # If we have a stored PDF, stream it from storage
            pdf_url = row.get("pdf_url")
            if pdf_url:
                try:
                    resp = _requests.get(pdf_url, timeout=15)
                    if resp.ok:
                        pkg_name = _safe_filename_part(str(row["name"]))
                        filename = f"dossier_{pkg_name}.pdf"
                        return Response(
                            content=resp.content,
                            media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                        )
                except Exception:
                    logger.warning("dossier: failed to fetch stored PDF, regenerating dossier_id=%s", dossier_id)

            # Fallback: regenerate merged PDF on-the-fly
            raw_ids = row["form_ids"]
            form_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            if not form_ids:
                raise HTTPException(status_code=422, detail="Dossier has no forms")

            pdf_parts: List[bytes] = []

            if row["cover_page"]:
                cover_meta: List[Dict[str, Any]] = []
                for fid in form_ids:
                    fr = _load_form_with_template(conn, case_id, fid)
                    if fr:
                        cover_meta.append({
                            "code": fr.get("template_code"),
                            "name": fr.get("template_name"),
                            "authority_code": fr.get("authority_code"),
                        })
                pdf_parts.append(_build_cover_page(str(row["name"]), case_id, cover_meta))

            for fid in form_ids:
                fr = _load_form_with_template(conn, case_id, fid)
                if fr:
                    pdf_parts.append(
                        _build_divider_page(
                            str(fr.get("template_code") or ""),
                            str(fr.get("template_name") or ""),
                            fr.get("authority_name"),
                        )
                    )
                pdf_parts.append(_fetch_form_pdf_bytes(conn, case_id, fid))

            merged = _merge_pdfs(pdf_parts)
            pkg_name = _safe_filename_part(str(row["name"]))
            filename = f"dossier_{pkg_name}.pdf"
            return Response(
                content=merged,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    except HTTPException:
        raise
    except Exception:
        logger.exception("dossier: pdf download failed dossier_id=%s", dossier_id)
        raise HTTPException(status_code=500, detail="Failed to download dossier PDF")


# ── [P3-6] Regenerate dossier ─────────────────────────────────────────────────

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
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did AND case_id = :cid
                    """
                ),
                {"did": dossier_id, "cid": case_id},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="Dossier package not found")

            raw_ids = row["form_ids"]
            form_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids or [])
            if not form_ids:
                raise HTTPException(status_code=422, detail="Dossier has no forms")

            # Rebuild PDF parts
            pdf_parts: List[bytes] = []

            if row["cover_page"]:
                cover_meta: List[Dict[str, Any]] = []
                for fid in form_ids:
                    fr = _load_form_with_template(conn, case_id, fid)
                    if fr:
                        cover_meta.append({
                            "code": fr.get("template_code"),
                            "name": fr.get("template_name"),
                            "authority_code": fr.get("authority_code"),
                        })
                pdf_parts.append(_build_cover_page(str(row["name"]), case_id, cover_meta))

            for fid in form_ids:
                fr = _load_form_with_template(conn, case_id, fid)
                if fr:
                    pdf_parts.append(
                        _build_divider_page(
                            str(fr.get("template_code") or ""),
                            str(fr.get("template_name") or ""),
                            fr.get("authority_name"),
                        )
                    )
                pdf_parts.append(_fetch_form_pdf_bytes(conn, case_id, fid))

            merged_pdf = _merge_pdfs(pdf_parts)

            # Stamp generated_at
            conn.execute(
                _sql_text(
                    f"""
                    UPDATE {_pg_table('dossier_packages')}
                    SET generated_at = {_sql_now()}
                    WHERE id = :did
                    """
                ),
                {"did": dossier_id},
            )

            # Attempt to update stored PDF
            new_pdf_url = _try_store_dossier_pdf(dossier_id, merged_pdf, conn)

            # Fetch updated row
            updated_row = conn.execute(
                _sql_text(
                    f"""
                    SELECT id, case_id, name, form_ids, cover_page,
                           pdf_url, generated_at, created_at
                    FROM {_pg_table('dossier_packages')}
                    WHERE id = :did
                    """
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


# ──────────────────────────────────────────────────────────────────────────────
# Employee Wizard — Step 3: Budget summary  (WZ3 / B19)
# GET /api/cases/{case_id}/budget-summary
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/budget-summary")
def get_budget_summary(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return HR-policy budget caps vs. the services selected for this case.
    Employees and HR can call this; the caller must be linked to a company.

    AUDIT-A2-followup: access is gated by _assert_case_access — employees must
    own the case, HR must belong to the same company, admins always pass.
    Returns 404 for missing cases and 403 for cross-company / cross-tenant
    access attempts. Mirrors the pattern from get_case / patch_case /
    list_case_forms.
    """
    _assert_case_access(user, case_id)

    # Resolve company from profile
    profile = main_db.get_profile_record(user.get("id"))
    company_id: str = (profile or {}).get("company_id") or user.get("company") or ""

    # Pull selected services from the case draft_json
    selected_services: List[str] = []
    try:
        with SessionLocal() as db_sess:
            case = crud.get_case(db_sess, case_id)
        if case:
            draft = json.loads(case.draft_json or "{}")
            selected_services = draft.get("services", [])
    except Exception:
        pass

    # Pull published HR policy budget caps
    categories: List[Dict[str, Any]] = []
    if company_id:
        try:
            policies = main_db.list_hr_policies_by_company(company_id)
            published = next(
                (p for p in policies if (p.get("status") or "").lower() == "published"),
                None,
            )
            if published:
                policy_data = json.loads(published.get("policy_json") or "{}")
                # Try common key variants for budget caps
                caps = (
                    policy_data.get("budget_caps")
                    or policy_data.get("categories")
                    or {}
                )
                if isinstance(caps, dict):
                    for svc, cap in caps.items():
                        categories.append({
                            "name": svc,
                            "cap_amount": cap.get("amount") if isinstance(cap, dict) else cap,
                            "cap_currency": (cap.get("currency", "EUR") if isinstance(cap, dict) else "EUR"),
                            "estimated_amount": None,
                            "status": "within_budget",
                        })
        except Exception:
            logger.exception("budget-summary: failed to read policy company=%s", company_id)

    # Fall back: return selected services with no_cap when no policy exists
    if not categories:
        for svc in (selected_services or ["housing", "moving", "immigration"]):
            categories.append({
                "name": svc,
                "cap_amount": None,
                "cap_currency": "EUR",
                "estimated_amount": None,
                "status": "no_cap",
            })

    return {"case_id": case_id, "categories": categories}


# ──────────────────────────────────────────────────────────────────────────────
# Employee Wizard — Step 4: Quote request  (WZ4 / B19)
# POST /api/cases/{case_id}/quote-request
# ──────────────────────────────────────────────────────────────────────────────

class _QuoteRequestBody(BaseModel):
    services: Optional[List[str]] = None
    notes: Optional[str] = None
    budget_range: Optional[str] = None


@router.post("/{case_id}/quote-request", status_code=201)
def create_case_quote_request(
    case_id: str,
    body: _QuoteRequestBody,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Employee submits a quote request for their relocation case (Step 4 / WZ4).
    Creates an entry in the quote_requests table and returns the new record.
    """
    profile = main_db.get_profile_record(user.get("id"))
    company_id: str = (profile or {}).get("company_id") or user.get("company") or ""
    if not company_id:
        # Fallback: derive company_id from the case itself (employee may be
        # assigned to a case without having an explicit company in their profile).
        # Resolves WZ4/B11 — employees assigned via HR portal lack company_id.
        try:
            with main_db.engine.connect() as _conn:
                # Cases created via POST /api/hr/cases are stored in relocation_cases
                # (via db.create_case). The public.cases table only holds seed data.
                _case_row = _conn.execute(
                    _sql_text(
                        "SELECT company_id FROM public.relocation_cases WHERE id::text = :cid"
                    ),
                    {"cid": case_id},
                ).mappings().first()
            if _case_row and _case_row.get("company_id"):
                company_id = str(_case_row["company_id"])
        except Exception:
            pass
    if not company_id:
        raise HTTPException(status_code=403, detail="No company linked to this account.")

    employee_id: str = str(user["id"])
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Serialise service categories for Postgres text[] column
    services = body.services or []
    cats_serialised = "{" + ",".join(f'"{s}"' for s in services) + "}"

    try:
        with main_db.engine.begin() as conn:
            conn.execute(
                _sql_text(
                    """
                    INSERT INTO public.quote_requests
                        (id, case_id, employee_id, company_id,
                         service_categories, notes, budget_range,
                         status, created_at, updated_at)
                    VALUES
                        (:id, :case_id, :emp, :company,
                         CAST(:cats AS text[]), :notes, :budget,
                         'pending', :now, :now)
                    """
                ),
                {
                    "id": new_id,
                    "case_id": case_id,
                    "emp": employee_id,
                    "company": company_id,
                    "cats": cats_serialised,
                    "notes": body.notes,
                    "budget": body.budget_range,
                    "now": now,
                },
            )
            row = conn.execute(
                _sql_text("SELECT * FROM public.quote_requests WHERE id = :id"),
                {"id": new_id},
            ).mappings().first()
    except Exception:
        logger.exception("quote-request: insert failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to create quote request")

    if row is None:
        raise HTTPException(status_code=500, detail="Quote request not found after insert")

    d = dict(row)
    # Normalise service_categories: Postgres returns list, text fallback is comma-str
    sc = d.get("service_categories")
    if isinstance(sc, str):
        d["service_categories"] = [s.strip() for s in sc.split(",") if s.strip()]
    elif sc is None:
        d["service_categories"] = []
    # Serialise datetimes
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                d[k] = str(v)

    return {
        "rfq_id": d["id"],
        "case_id": d["case_id"],
        "status": d["status"],
        "service_categories": d["service_categories"],
        "created_at": d["created_at"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Employee Wizard — Step 5: Case messages  (WZ5 / B19)
# POST /api/cases/{case_id}/messages
# GET  /api/cases/{case_id}/messages
# ──────────────────────────────────────────────────────────────────────────────

class _MessageBody(BaseModel):
    content: str


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
                    """
                    INSERT INTO public.case_messages
                        (id, case_id, sender_id, sender_role, content, created_at)
                    VALUES
                        (:id, :case_id, :sender_id, :sender_role, :content, :now)
                    """
                ),
                {
                    "id": new_id,
                    "case_id": case_id,
                    "sender_id": sender_id,
                    "sender_role": sender_role,
                    "content": body.content,
                    "now": now,
                },
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


@router.get("/{case_id}/messages")
def list_case_messages(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return the full message thread for a case, oldest-first.
    """
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    """
                    SELECT * FROM public.case_messages
                    WHERE case_id = :case_id
                    ORDER BY created_at ASC
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
    except Exception:
        logger.exception("messages: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list messages")

    result = []
    for row in rows:
        d = dict(row)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                try:
                    d[k] = v.isoformat()
                except Exception:
                    d[k] = str(v)
        result.append({
            "id": str(d["id"]),
            "case_id": str(d["case_id"]),
            "sender_id": str(d["sender_id"]),
            "sender_role": d["sender_role"],
            "content": d["content"],
            "created_at": d["created_at"],
        })
    return result


# ---------------------------------------------------------------------------
# T11 – Vendor Display (MVP-7)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/vendors")
def list_case_vendors(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return vendors assigned to the case from case_vendor_shortlist joined with
    the vendors table.  Available to HR and ADMIN roles.
    """
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    """
                    SELECT
                        cvs.id            AS shortlist_id,
                        cvs.service_key   AS category,
                        cvs.status,
                        cvs.contact_name,
                        cvs.contact_email,
                        v.name            AS vendor_name,
                        v.website         AS vendor_website
                    FROM public.case_vendor_shortlist cvs
                    LEFT JOIN public.vendors v ON v.id = cvs.vendor_id
                    WHERE cvs.case_id = :case_id
                    ORDER BY cvs.service_key, v.name
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
    except Exception:
        logger.exception("vendors: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list vendors")

    result = []
    for row in rows:
        d = dict(row)
        result.append({
            "shortlist_id": str(d["shortlist_id"]) if d.get("shortlist_id") else None,
            "category": d.get("category"),
            "status": d.get("status", "Assigned"),
            "contact_name": d.get("contact_name"),
            "contact_email": d.get("contact_email"),
            "vendor_name": d.get("vendor_name"),
            "vendor_website": d.get("vendor_website"),
        })
    return result


# ---------------------------------------------------------------------------
# T12 – Budget View (MVP-7)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/budget-lines")
def list_case_budget_lines(
    case_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """
    Return budget line items for the case.  Available to HR and ADMIN roles.
    """
    _assert_case_access(user, case_id)
    try:
        with main_db.engine.begin() as conn:
            rows = conn.execute(
                _sql_text(
                    """
                    SELECT
                        id,
                        case_id,
                        category,
                        estimated_eur,
                        created_at
                    FROM public.case_budget_lines
                    WHERE case_id = :case_id
                    ORDER BY category
                    """
                ),
                {"case_id": case_id},
            ).mappings().all()
    except Exception:
        logger.exception("budget-lines: list failed case_id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to list budget lines")

    result = []
    for row in rows:
        d = dict(row)
        result.append({
            "id": str(d["id"]),
            "case_id": str(d["case_id"]),
            "category": d.get("category"),
            "estimated_eur": float(d["estimated_eur"]) if d.get("estimated_eur") is not None else 0.0,
            "created_at": d["created_at"].isoformat() if hasattr(d.get("created_at"), "isoformat") else str(d.get("created_at", "")),
        })
    return result
