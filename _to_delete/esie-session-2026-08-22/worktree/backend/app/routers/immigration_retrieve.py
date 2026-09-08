"""
Immigration-rule retrieval endpoint (W1 / AIQ-835).

POST /api/immigration/retrieve — wires `immigration_retriever.retrieve_for_profile`
into a live, authenticated endpoint so the corridor-aware retriever has a real
HTTP caller. Builds a structured UserProfile + PathClassification from the
request body (never raw strings) and returns corridor-scoped immigration-rule
chunks.

An uncovered/empty corpus returns an empty list with `corpus_empty: true`
(HTTP 200) — it never raises.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth_deps import get_current_user, require_case_access
from ..services import immigration_answer_engine, immigration_retriever
from ..services.immigration_answer_context import build_applicant_context
from ..services.immigration_source_reconciler import reconcile
from ..services.immigration_retriever import (
    PathClassification,
    UserProfile,
    _build_query,
    corridor_key,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/immigration", tags=["immigration-retrieve"])


def _profile_and_classification(body):
    """Build (corridor, UserProfile, PathClassification) from a request body.
    Shared by /retrieve and /answer — both bodies carry the same corridor fields."""
    corridor = corridor_key(body.corridor_from, body.corridor_to)
    profile = UserProfile(
        nationality=body.nationality,
        origin_country=body.corridor_from,
        destination_country=body.corridor_to,
        is_eea=body.is_eea,
    )
    classification = PathClassification(pathway_type=body.permit_type, corridor=corridor)
    return corridor, profile, classification


class ImmigrationRetrieveBody(BaseModel):
    corridor_from: str
    corridor_to: str
    nationality: str
    permit_type: str
    is_eea: Optional[bool] = None
    top_k: int = 5


@router.post("/retrieve")
def retrieve_immigration_rules(
    body: ImmigrationRetrieveBody,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve corridor-scoped immigration-rule chunks for a structured profile."""
    corridor, profile, classification = _profile_and_classification(body)
    query_string = _build_query(profile, classification, corridor)

    chunks: List[Dict[str, Any]] = immigration_retriever.retrieve_for_profile(
        profile=profile, classification=classification, top_k=body.top_k
    )
    return {
        "chunks": chunks,
        "corridor": corridor,
        "query_string": query_string,
        "corpus_empty": len(chunks) == 0,
    }


class ImmigrationAnswerBody(BaseModel):
    corridor_from: str
    corridor_to: str
    nationality: str
    permit_type: str
    is_eea: Optional[bool] = None
    query: str
    top_k: int = 8
    # Slice 3: when present, the answer is tailored to this case's anonymised
    # applicant context (family situation). Ownership is verified before use.
    case_id: Optional[str] = None


@router.post("/answer")
def answer_immigration_question(
    body: ImmigrationAnswerBody,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    N4/AIQ-843 — grounded, citation-enforced immigration answer.

    Retrieves corridor-scoped chunks (staleness-aware) and generates an answer
    sourced ONLY from them. Zero chunks -> refusal_insufficient_context at HTTP
    200 (no LLM call). Every response carries a trace_id.
    """
    # Slice 3: tailor the answer to the applicant's case context — but only after
    # verifying the caller owns this case (no cross-case context leak). Best-effort:
    # a context failure must never block the answer.
    applicant_context = None
    if body.case_id:
        require_case_access(body.case_id, user)
        try:
            applicant_context = build_applicant_context(body.case_id)
        except Exception:
            applicant_context = None

    corridor, profile, classification = _profile_and_classification(body)
    # N9/AIQ-849: multi-source triangulation. Retrieve official (tier-1) and
    # all-tier sets, reconcile by cross-tier embedding agreement, then generate
    # from the reconciled chunks (tagged with source_agreement).
    multi = immigration_retriever.retrieve_multi_source(
        profile=profile, classification=classification, top_k=body.top_k
    )
    recon = reconcile(multi["official_chunks"], multi["secondary_chunks"])
    # Drop the bulky embedding vectors before generation; keep source_agreement.
    chunks = sorted(
        ({k: v for k, v in c.items() if k != "embedding"} for c in recon["reconciled_chunks"]),
        key=lambda c: float(c.get("adjusted_score") or 0),
        reverse=True,
    )[: body.top_k]
    all_stale = bool(chunks) and all(c.get("is_stale") for c in chunks)
    fetched = [c.get("fetched_at") for c in chunks if c.get("fetched_at")]
    payload = {
        "chunks": chunks,
        "all_stale_warning": all_stale,
        "oldest_fetched_at": min(fetched) if fetched else None,
    }
    return immigration_answer_engine.generate_immigration_answer(
        payload, body.query, corridor, applicant_context=applicant_context
    )
