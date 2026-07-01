"""Setup & Help Assistant — read-only HR workspace setup-status + query endpoints.

``GET  /api/hr/setup-status``         — workspace setup progress (T2 state reader).
``POST /api/hr/setup-assistant/query`` — LLM-grounded HR setup question answering.

Both endpoints are READ-ONLY: no writes, no new tables. The POST endpoint
computes live workspace state (same as the GET), calls the engine, and returns
a structured answer grounded in the KB. Company scope comes ONLY from auth.

Field sources:
  - company_profile_complete → ``db.get_company`` (company-profile source table)
  - policy_published         → ``db.get_latest_published_policy_config_version``
                               (LIVE config-matrix publish path)
  - cases_count/first_case_id→ ``public.relocation_cases`` filtered by company_id
  - employees_invited        → ``case_assignments`` JOIN ``relocation_cases`` by company_id

Per CLAUDE.md the router is registered in BOTH ``backend/app/main.py`` and
``backend/main.py`` (prod entry).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from ...database import db
from ..auth_deps import get_org_id_for_hr_user, require_admin_or_hr
from ..services.policy_config_matrix_service import CONFIG_KEY
from ..services.setup_help.setup_help_engine import answer_setup_question

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hr", tags=["hr-setup"])


# --------------------------------------------------------------------------- #
# Response schema
# --------------------------------------------------------------------------- #
class NextStep(BaseModel):
    label: str
    route: str


class SetupStatusResponse(BaseModel):
    company_profile_complete: bool
    policy_published: bool
    cases_count: int
    employees_invited: int
    first_case_id: Optional[str] = None
    next_step: NextStep


# --------------------------------------------------------------------------- #
# Field derivation — each degrades to a "not set up" value rather than 500, so
# the assistant always receives a usable workspace state.
# --------------------------------------------------------------------------- #
def _company_profile_complete(company_id: str) -> bool:
    """Complete when the company row has its core profile fields (name, country,
    address) filled. A fresh self-serve signup company has only name + size_band,
    so it reads as incomplete → the first setup step."""
    company = db.get_company(company_id) or {}
    return (
        bool((company.get("name") or "").strip())
        and bool((company.get("country") or "").strip())
        and bool((company.get("address") or "").strip())
    )


def _policy_published(company_id: str) -> bool:
    """True when a published policy_config version exists for the company (the
    LIVE config-matrix system, same source as the onboarding-inference engine)."""
    try:
        pub = db.get_latest_published_policy_config_version(company_id, CONFIG_KEY)
        return bool(pub and pub.get("id"))
    except Exception:  # pragma: no cover - defensive, degrade to False
        log.warning("setup-status: policy lookup failed for company=%s", company_id, exc_info=True)
        return False


def _cases(company_id: str) -> Tuple[int, Optional[str]]:
    """Count ``public.relocation_cases`` for the company and return the first
    (earliest) case id. Live HR-created cases live in ``relocation_cases``;
    ``public.cases`` is seed-data only. Pure read; degrades to (0, None)."""
    try:
        with db.engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM relocation_cases WHERE company_id = :cid"),
                {"cid": company_id},
            ).scalar()
            first = conn.execute(
                text(
                    "SELECT id FROM relocation_cases WHERE company_id = :cid "
                    "ORDER BY created_at ASC LIMIT 1"
                ),
                {"cid": company_id},
            ).fetchone()
        first_id = str(first[0]) if first and first[0] is not None else None
        return int(count or 0), first_id
    except Exception:  # pragma: no cover - defensive, degrade to 0
        log.warning("setup-status: cases lookup failed for company=%s", company_id, exc_info=True)
        return 0, None


def _employees_invited(company_id: str) -> int:
    """Count distinct employees assigned to the company's relocation cases.

    Joins ``case_assignments`` to ``relocation_cases`` via
    ``ca.case_id = CAST(rc.id AS TEXT)`` (the FK is stored as text in
    case_assignments while relocation_cases.id is a UUID column; CAST works on
    both Postgres and SQLite).  Counting from ``public.employees`` under-counts
    because invited employees frequently have NULL ``company_id`` on that table.
    Pure read; degrades to 0.
    """
    try:
        with db.engine.connect() as conn:
            count = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT COALESCE(ca.employee_user_id, ca.employee_identifier))"
                    " FROM case_assignments ca"
                    " JOIN relocation_cases rc ON ca.case_id = CAST(rc.id AS TEXT)"
                    " WHERE rc.company_id = :cid"
                ),
                {"cid": company_id},
            ).scalar()
        return int(count or 0)
    except Exception:  # pragma: no cover - defensive, degrade to 0
        log.warning("setup-status: employees lookup failed for company=%s", company_id, exc_info=True)
        return 0


def _next_step(
    profile_complete: bool,
    policy_published: bool,
    cases_count: int,
    employees_invited: int,
) -> NextStep:
    """First incomplete stage in order: company profile → publish policy →
    create first case → invite employee → (all done) you're set up."""
    if not profile_complete:
        return NextStep(label="Complete your company profile", route="/hr/company-profile")
    if not policy_published:
        return NextStep(label="Publish your relocation policy", route="/hr/settings/policy")
    if cases_count == 0:
        return NextStep(label="Create your first case", route="/hr/command-center")
    if employees_invited == 0:
        return NextStep(label="Invite your first employee", route="/hr/command-center")
    return NextStep(label="You're all set up", route="/hr/command-center")


# --------------------------------------------------------------------------- #
# Route
# --------------------------------------------------------------------------- #
@router.get("/setup-status", response_model=SetupStatusResponse)
def get_setup_status(
    _user=Depends(require_admin_or_hr),
    company_id: str = Depends(get_org_id_for_hr_user),
) -> SetupStatusResponse:
    """Return the caller's real setup progress, scoped to their own company.

    ``company_id`` is resolved from auth by ``get_org_id_for_hr_user`` — never
    from a request body or query param — so a caller can only ever see their own
    company's status.
    """
    if not company_id:
        # No company linked yet — the first step is always the company profile.
        return SetupStatusResponse(
            company_profile_complete=False,
            policy_published=False,
            cases_count=0,
            employees_invited=0,
            first_case_id=None,
            next_step=NextStep(
                label="Complete your company profile", route="/hr/company-profile"
            ),
        )

    profile_complete = _company_profile_complete(company_id)
    policy_published = _policy_published(company_id)
    cases_count, first_case_id = _cases(company_id)
    employees_invited = _employees_invited(company_id)

    return SetupStatusResponse(
        company_profile_complete=profile_complete,
        policy_published=policy_published,
        cases_count=cases_count,
        employees_invited=employees_invited,
        first_case_id=first_case_id,
        next_step=_next_step(
            profile_complete, policy_published, cases_count, employees_invited
        ),
    )


# --------------------------------------------------------------------------- #
# POST /api/hr/setup-assistant/query — LLM-grounded HR setup question
# --------------------------------------------------------------------------- #

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class QueryNextStep(BaseModel):
    label: str
    route: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    next_step: Optional[QueryNextStep] = None
    cited_topics: List[str] = Field(default_factory=list)
    model: str
    usage: Dict[str, Any] = Field(default_factory=dict)


@router.post("/setup-assistant/query", response_model=QueryResponse)
def post_setup_assistant_query(
    body: QueryRequest,
    _user=Depends(require_admin_or_hr),
    company_id: str = Depends(get_org_id_for_hr_user),
) -> QueryResponse:
    """Answer an HR setup question grounded in the Setup & Help KB.

    Company scope comes from auth (``get_org_id_for_hr_user``), never from
    the request body. PII in the question is masked before LLM egress. The
    engine is READ-ONLY — it guides and reads state; it does not write anything.
    """
    # Compute live setup state (same logic as GET /setup-status).
    if not company_id:
        status: Dict[str, Any] = {
            "company_profile_complete": False,
            "policy_published": False,
            "cases_count": 0,
            "employees_invited": 0,
            "first_case_id": None,
            "next_step": {"label": "Complete your company profile", "route": "/hr/company-profile"},
        }
    else:
        profile_complete = _company_profile_complete(company_id)
        policy_published = _policy_published(company_id)
        cases_count, first_case_id = _cases(company_id)
        employees_invited = _employees_invited(company_id)
        ns = _next_step(profile_complete, policy_published, cases_count, employees_invited)
        status = {
            "company_profile_complete": profile_complete,
            "policy_published": policy_published,
            "cases_count": cases_count,
            "employees_invited": employees_invited,
            "first_case_id": first_case_id,
            "next_step": {"label": ns.label, "route": ns.route},
        }

    result = answer_setup_question(question=body.question, setup_status=status)

    raw_ns = result.get("next_step")
    next_step_out: Optional[QueryNextStep] = None
    if isinstance(raw_ns, dict):
        next_step_out = QueryNextStep(
            label=raw_ns.get("label", ""),
            route=raw_ns.get("route"),
        )

    return QueryResponse(
        answer=result["answer"],
        next_step=next_step_out,
        cited_topics=result.get("cited_topics", []),
        model=result.get("model", "unknown"),
        usage=result.get("usage", {}),
    )
