from __future__ import annotations

import json
import uuid
from typing import Any, Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException

from ..db import SessionLocal
from .. import crud, schemas
from ..services.research import run_country_research
from ..services.requirements_builder import compute_case_requirements

router = APIRouter(prefix="/api/cases", tags=["cases"])


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
        case = crud.get_case(db, case_id)
        if not case:
            case = crud.create_case(db, case_id, patch.model_dump(mode="json"))

        draft = patch.model_dump(mode="json")
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
def create_case(case_id: str):
    with SessionLocal() as db:
        case = crud.get_case(db, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        draft = json.loads(case.draft_json)
        basics = draft.get("relocationBasics", {})
        if not basics.get("originCountry") or not basics.get("destCountry") or not basics.get("purpose"):
            raise HTTPException(status_code=400, detail="Missing minimum required fields")

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
                "sources_json": json.dumps([source.model_dump() for source in requirements.sources]),
            },
        )
        case.status = "CREATED"
        case.requirements_snapshot_id = snapshot_id
        db.commit()

    return {"createdCaseId": case_id, "requirementsSnapshotId": snapshot_id}


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
