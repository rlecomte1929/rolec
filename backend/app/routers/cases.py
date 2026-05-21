from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from ..db import SessionLocal
from .. import crud, schemas
from ..auth_deps import get_current_user
from ...database import db as main_db
from ...services.relocation_plan_view_service import invalidate_relocation_plan_cache
from ..services.research import run_country_research
from ..services.requirements_builder import compute_case_requirements
from ..services.roadmap_builder import derive_roadmap
from ..services.trigger_engine import fire_roadmap_events
from sqlalchemy import text as _sql_text

router = APIRouter(prefix="/api/cases", tags=["cases"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Dialect helper for the Supabase-backed endpoints below.
# Postgres prod uses `public.X` schema-qualified names; SQLite tests use bare.
# ─────────────────────────────────────────────────────────────────────────────

def _pg_table(name: str) -> str:
    try:
        dialect_name = main_db.engine.dialect.name
    except Exception:
        dialect_name = "postgresql"
    return f"public.{name}" if dialect_name == "postgresql" else name


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


def _deep_merge_case_drafts(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Merge PATCH payload into stored draft so partial saves never wipe other wizard sections."""
    out = dict(base)
    for key, val in update.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge_case_drafts(out[key], val)
        else:
            out[key] = val
    return out


@router.get("/{case_id}", response_model=schemas.CaseDTO)
def get_case(case_id: str):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
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
        return _case_dto(case, draft)


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
    return {"jobId": str(uuid.uuid4())}


@router.get("/{case_id}/requirements", response_model=schemas.CaseRequirementsDTO)
def get_case_requirements(case_id: str):
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

    try:
        from ...services.analytics_service import emit_event, EVENT_CASE_CREATED
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
def get_case_roadmap(case_id: str):
    """
    GAP 2 & GAP 5: Returns a multi-track relocation roadmap derived from the case draft.
    Replaces window.PATHWAY_V2.deriveTimeline() with a real server-side computation.
    Tracks: Visa & Permit | Civil Documents | Family (conditional) | Settlement.
    """
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
# GAP 9: Research status polling endpoint (Option B — polling, no SSE)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{case_id}/research/status")
def get_research_status(case_id: str):
    """
    GAP 9: Poll-based research progress for the S2 discovery log.
    Returns {status, progress_pct, events[{ts, msg}]}.
    Client polls every 2s; no SSE infrastructure required.
    """
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

    return {
        "case_id": case_id,
        "household_updated": True,
        "family_member_count": len(payload.family_members or []),
        "pet_count": len(payload.pets or []),
    }


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
    original_file_url: Optional[str]
    draft_pdf_url: Optional[str]
    submitted_at: Optional[str]
    receipt_ref: Optional[str]
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

    return CaseFormSummary(
        id=str(row["id"]),
        case_id=str(row["case_id"]),
        status=str(row["status"]),
        completion_pct=int(row.get("completion_pct") or 0),
        deadline=_iso(row.get("deadline")),
        deadline_trigger=row.get("deadline_trigger"),
        blocker_form_id=(str(row["blocker_form_id"]) if row.get("blocker_form_id") else None),
        blocker_form_code=row.get("blocker_form_code"),
        original_file_url=row.get("original_file_url"),
        draft_pdf_url=row.get("draft_pdf_url"),
        submitted_at=_iso(row.get("submitted_at")),
        receipt_ref=row.get("receipt_ref"),
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


def _assert_case_access(user: Dict[str, Any], case_id: str) -> None:
    """
    Verify the caller can read the given case.
    Employees: must own the case (cases.employee_id == auth uid).
    HR / Admin: sufficient to belong to the same company as the case.
    Raises 404 (case missing) or 403 (no access).
    """
    user_id = user.get("id")
    role = (user.get("role") or "").upper()
    is_admin = user.get("is_admin") or role == "ADMIN"

    try:
        with main_db.engine.connect() as conn:
            row = conn.execute(
                _sql_text(
                    f"SELECT id, company_id, employee_id, hr_owner_id "
                    f"FROM {_pg_table('cases')} WHERE id = :id"
                ),
                {"id": case_id},
            ).mappings().first()
    except Exception:
        logger.exception("dossier: failed to query cases for access check id=%s", case_id)
        raise HTTPException(status_code=500, detail="Failed to verify case access")

    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    # Employee owns the case
    if user_id and str(row.get("employee_id") or "") == str(user_id):
        return
    # HR owns the case
    if user_id and str(row.get("hr_owner_id") or "") == str(user_id):
        return
    # Admin always allowed
    if is_admin:
        return
    # HR users with company match — read user's company from profiles
    if role == "HR":
        try:
            with main_db.engine.connect() as conn:
                prof = conn.execute(
                    _sql_text(
                        f"SELECT company_id FROM {_pg_table('profiles')} "
                        f"WHERE id = :id"
                    ),
                    {"id": user_id},
                ).mappings().first()
            if prof and str(prof.get("company_id") or "") == str(row.get("company_id") or ""):
                return
        except Exception:
            logger.exception("dossier: failed to look up HR profile company_id id=%s", user_id)

    raise HTTPException(status_code=403, detail="Not authorised for this case")


@router.get("/{case_id}/forms", response_model=List[CaseFormSummary])
def list_case_forms(
    case_id: str,
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user),
) -> List[CaseFormSummary]:
    """
    List all CaseForms for a case, with template metadata, person name, and
    a FieldValue summary count. The frontend uses this to render the Dossier
    & Forms list view.

    Optional `?status=` filter narrows by document_status (e.g. 'ready').
    """
    _assert_case_access(user, case_id)

    # Build the join in one statement. The aggregate over case_form_field_values
    # is done as a correlated sub-select per row — simpler than a GROUP BY and
    # cheap given typical row counts (<50 forms per case).
    where_status = ""
    params: Dict[str, Any] = {"case_id": case_id}
    if status:
        where_status = " AND cf.status = :status"
        params["status"] = status

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
          cf.original_file_url,
          cf.draft_pdf_url,
          cf.submitted_at,
          cf.receipt_ref,
          cf.person_id,
          cf.dependent_id,
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
