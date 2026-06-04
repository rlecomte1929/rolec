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
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth_deps import require_admin
from ..services import rag_pipeline
from ..services.immigration_retriever import PathClassification, UserProfile

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/rag", tags=["rag-roadmap"])


class GenerateRoadmapBody(BaseModel):
    nationality: str
    origin_country: str
    destination_country: str
    pathway_type: str
    is_eea: Optional[bool] = None
    corridor: Optional[str] = None
    top_k: int = 10


@router.post("/generate-roadmap")
def generate_roadmap(
    body: GenerateRoadmapBody,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
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
