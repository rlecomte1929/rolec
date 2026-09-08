"""
RAG roadmap API (P1-01d) — the single internal endpoint that runs the
immigration roadmap pipeline end to end.

POST /api/internal/rag/generate-roadmap
    body: a classified UserProfile + PathClassification
    → retriever (P1-01a) → generator (P1-01b) → verifier (P1-01c)
    → CaseRoadmap with per-step verification verdicts.

Admin-only, mirroring the sibling /api/internal/specialist-review router. The
full LLM I/O audit trail is written by the pipeline's TraceSession.
"""
import json
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import crud
from ..auth_deps import require_admin
from ..db import SessionLocal
from ..services import rag_pipeline
from ..services.case_roadmap_profile import (
    generate_ai_roadmap_for_case,
    persist_generated_milestones,
)
from ..services.immigration_retriever import PathClassification, UserProfile

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/rag", tags=["rag-roadmap"])


class GenerateRoadmapBody(BaseModel):
    # Case-driven mode: pass case_id alone — the profile is derived from the case
    # and, on a successful generation, the AI steps are persisted into
    # case_milestones (so the employee roadmap shows corridor-specific content).
    case_id: Optional[str] = None
    # Legacy explicit-profile mode (no persistence) — still supported.
    nationality: Optional[str] = None
    origin_country: Optional[str] = None
    destination_country: Optional[str] = None
    pathway_type: Optional[str] = None
    is_eea: Optional[bool] = None
    corridor: Optional[str] = None
    top_k: int = 10


@router.post("/generate-roadmap")
def generate_roadmap(
    body: GenerateRoadmapBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    # ── Case-driven mode: derive profile from the case, generate, and persist ──
    if body.case_id:
        request_id = str(uuid.uuid4())
        with SessionLocal() as session:
            case = crud.get_case(session, body.case_id)
            if not case:
                raise HTTPException(status_code=404, detail="Case not found")
            try:
                draft = json.loads(case.draft_json or "{}")
            except (json.JSONDecodeError, TypeError, ValueError):
                draft = {}
        case_dict = {"id": body.case_id, "status": case.status, "draft": draft}
        roadmap = generate_ai_roadmap_for_case(case_dict)
        if roadmap is None:
            return {
                "result": "RULE_NOT_FOUND",
                "refusal_reason": "Case could not be mapped to a corridor (missing origin/destination).",
                "steps": [],
                "persisted_milestones": 0,
            }
        # Persist only when the generator produced grounded steps. The factual
        # verifier's approval (often False on strict grounding) does NOT gate
        # persistence — a result:OK roadmap with steps is corridor-specific
        # content worth showing; the approval is logged alongside the count.
        persisted = 0
        if roadmap.get("result") == "OK" and roadmap.get("steps"):
            from ...database import db  # legacy Database instance owns case_milestones
            try:
                persisted = persist_generated_milestones(
                    db, body.case_id, roadmap["steps"], roadmap.get("corridor"), request_id
                )
                log.info(
                    "generate-roadmap: persisted %d milestones for case %s (approved=%s)",
                    persisted, body.case_id, roadmap.get("approved"),
                )
            except Exception:
                log.warning(
                    "generate-roadmap: persist failed for case %s (deterministic seed kept)",
                    body.case_id, exc_info=True,
                )
                persisted = 0
        roadmap["persisted_milestones"] = persisted
        return roadmap

    # ── Legacy explicit-profile mode (no persistence) ──
    if not (body.nationality and body.origin_country and body.destination_country and body.pathway_type):
        raise HTTPException(
            status_code=422,
            detail="Provide case_id, or nationality + origin_country + destination_country + pathway_type.",
        )
    profile = UserProfile(
        nationality=body.nationality,
        origin_country=body.origin_country,
        destination_country=body.destination_country,
        is_eea=body.is_eea,
    )
    classification = PathClassification(
        pathway_type=body.pathway_type, corridor=body.corridor
    )
    return rag_pipeline.generate_roadmap(
        profile=profile, classification=classification, top_k=body.top_k
    )
