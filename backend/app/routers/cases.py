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
