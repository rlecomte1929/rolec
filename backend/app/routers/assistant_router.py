"""
Assistant routing endpoint (policy-bridge, Slice 5 backend).

POST /api/assistant/route — classify a question's domain (immigration | policy |
ambiguous) for the unified relocation assistant, so the frontend routes to the
right grounded engine (or shows the clarifier). Deterministic, no LLM, no data
access — just the canonical domain router. Auth-required so only signed-in users
hit it; it reads no case/company data.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth_deps import get_current_user
from ..services.assistant_domain_router import classify_domain

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class RouteBody(BaseModel):
    question: str


@router.post("/route")
def route_assistant_question(
    body: RouteBody,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return classify_domain(body.question)
