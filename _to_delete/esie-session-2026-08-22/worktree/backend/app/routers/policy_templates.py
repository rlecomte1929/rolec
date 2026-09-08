"""
DEPRECATED (N12/AIQ-852): the ``benefits_templates`` table read here is one of four
legacy template systems now unified by ``policy_template_service.PolicyTemplateService``.
Left in place until a follow-up cleanup task migrates this route to the unified
service and retires the table after validation — do not extend.

Policy Builder — 3-tier template library (P1-2).

Routes:
  GET /api/policy/templates  — return all 3 tiers × 14 categories
                               structured as { tiers: [...] }.
                               No auth required — templates are global
                               reference data with no company-scoped values.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.policy_template_service import PolicyTemplateService

router = APIRouter(prefix="/api/policy/templates", tags=["policy_templates"])


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class TemplateCategoryOut(BaseModel):
    category_id: str
    code: str
    display_name: str
    cap_value: float
    cap_unit: str
    cap_currency: str
    benchmark_source: str


class TemplateTierOut(BaseModel):
    tier: str
    tier_order: int
    categories: List[TemplateCategoryOut]


class TemplatesResponse(BaseModel):
    ok: bool = True
    tiers: List[TemplateTierOut]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("", response_model=TemplatesResponse)
def get_policy_templates() -> TemplatesResponse:
    """
    Return the 3-tier template library (Conservative / Standard / Premium),
    each tier containing all 14 benefit categories with benchmark cap values.

    Values are seeded from AIRINC 2025, Mercer 2024, and ECA International.
    Conservative caps are always <= Standard caps <= Premium caps.
    """
    # N12-followup-a (AIQ-889): read from the unified PolicyTemplateService benchmark
    # library (deterministic, no DB IO) instead of the retired benefits_templates table.
    library = PolicyTemplateService().get_benchmark_library()
    tiers = [
        TemplateTierOut(
            tier=tier["tier"],
            tier_order=tier["tier_order"],
            categories=[TemplateCategoryOut(**cat) for cat in tier["categories"]],
        )
        for tier in sorted(library, key=lambda t: t["tier_order"])
    ]
    return TemplatesResponse(tiers=tiers)
