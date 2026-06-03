"""Benefit-mix optimizer route (Parker-B).

POST /api/hr/{company_id}/optimize-benefit-mix — given a budget and a set of
candidate benefits, return the utility-maximizing mix plus shadow prices ("each
extra €1000 of budget yields +X satisfaction").

Auth: HR admin of the company in the path, or a platform admin. An HR admin of a
different company gets 403.

The PuLP solver is imported lazily inside the optimizer service, so importing this
router never requires the solver to be installed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..db import SessionLocal
from ...schemas import UserRole
from ..services.benefit_optimizer import (
    DEFAULT_LAMBDA,
    LAMBDA_MAX,
    LAMBDA_MIN,
    BenefitCandidate,
    OptimizationError,
    optimize,
)

router = APIRouter(prefix="/api/hr", tags=["benefit-optimizer"])


class CandidateBody(BaseModel):
    id: str
    category: str
    cost_per_employee: float = Field(ge=0)
    expected_satisfaction: Optional[float] = None
    variance: Optional[float] = Field(default=None, ge=0)
    mandatory: bool = False


class OptimizeRequest(BaseModel):
    budget: float = Field(ge=0)
    candidates: List[CandidateBody]
    mandatory_ids: List[str] = Field(default_factory=list)
    category_caps: Dict[str, float] = Field(default_factory=dict)
    lambda_risk: float = Field(default=DEFAULT_LAMBDA, ge=LAMBDA_MIN, le=LAMBDA_MAX)
    min_coverage: int = Field(default=0, ge=0)


def _resolve_candidates(
    company_id: str, body: OptimizeRequest
) -> List[BenefitCandidate]:
    """Build optimizer candidates, filling missing priors from benefit_priors."""
    needs_priors = any(c.expected_satisfaction is None for c in body.candidates)
    priors = {}
    if needs_priors:
        from ..services.benefit_priors_repo import load_company_priors

        with SessionLocal() as session:
            priors = load_company_priors(session, company_id)

    resolved: List[BenefitCandidate] = []
    for c in body.candidates:
        expected = c.expected_satisfaction
        variance = c.variance
        if expected is None:
            prior = priors.get((c.category, c.id))
            if prior is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"no expected_satisfaction for candidate {c.id!r} and no prior found",
                )
            expected = prior["expected_satisfaction"]
            if variance is None:
                variance = prior["variance"]
        resolved.append(
            BenefitCandidate(
                id=c.id,
                category=c.category,
                cost_per_employee=c.cost_per_employee,
                expected_satisfaction=expected,
                variance=variance,
                mandatory=c.mandatory,
            )
        )
    return resolved


@router.post("/{company_id}/optimize-benefit-mix")
def optimize_benefit_mix(
    body: OptimizeRequest,
    company_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_admin_or_hr),
    caller_company: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """Return the optimal benefit portfolio + shadow prices for ``company_id``."""
    is_admin = user.get("role") == UserRole.ADMIN.value or user.get("is_admin")
    if not is_admin and str(caller_company) != str(company_id):
        raise HTTPException(status_code=403, detail="Not authorized for this company")

    candidates = _resolve_candidates(company_id, body)
    try:
        result = optimize(
            budget=body.budget,
            candidates=candidates,
            mandatory_ids=body.mandatory_ids,
            category_caps=body.category_caps,
            lambda_risk=body.lambda_risk,
            min_coverage=body.min_coverage,
        )
    except OptimizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "feasible": result.feasible,
        "infeasibility_reason": result.infeasibility_reason,
        "selected": result.selected,
        "achieved_utility": result.achieved_utility,
        "total_cost": result.total_cost,
        "shadow_prices": result.shadow_prices,
        "lambda_risk": result.lambda_risk,
    }
