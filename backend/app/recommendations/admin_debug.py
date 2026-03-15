"""Admin-only recommendation debug endpoint."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth_deps import require_admin
from .criteria_builder import (
    SERVICE_KEY_TO_BACKEND,
    _flatten_saved_answers,
    build_criteria_for_assignment,
)
from .engine import recommend_debug

log = logging.getLogger(__name__)

router = APIRouter(tags=["admin-recommendations-debug"])


@router.get("/recommendations/debug")
def get_recommendations_debug(
    assignment_id: str = Query(..., description="Assignment id to build criteria from"),
    service_category: str = Query(..., description="Service key: housing, schools, movers, banks, insurances, electricity"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """
    Admin: debug recommendation inputs and ranking for an assignment + service.
    Returns criteria used, dataset size, and full ranked list with scores and preferred flag.
    """
    from ...database import db
    from ...policy_engine import PolicyEngine
    from ...services.policy_adapter import normalize_policy_caps
    from ..db import SessionLocal
    from .. import crud as app_crud

    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")

    backend_key = SERVICE_KEY_TO_BACKEND.get(service_category)
    if not backend_key:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown service_category. Use one of: {list(SERVICE_KEY_TO_BACKEND.keys())}",
        )

    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
    draft = {}
    dest_city = dest_country = origin_city = origin_country = None
    if case:
        try:
            draft = json.loads(case.draft_json or "{}")
        except Exception:
            draft = {}
        dest_city = getattr(case, "dest_city", None)
        dest_country = getattr(case, "dest_country", None)
        origin_city = getattr(case, "origin_city", None)
        origin_country = getattr(case, "origin_country", None)
    basics = draft.get("relocationBasics") or {}
    case_context = {
        "destCity": basics.get("destCity") or dest_city,
        "destCountry": basics.get("destCountry") or dest_country,
        "originCity": basics.get("originCity") or origin_city,
        "originCountry": origin_country or basics.get("originCountry"),
    }

    answer_rows = db.list_case_service_answers(case_id)
    saved_answers = _flatten_saved_answers(answer_rows)

    policy_context = None
    try:
        policy_engine = PolicyEngine()
        policy = policy_engine.load_policy()
        if policy:
            policy_context = normalize_policy_caps(policy)
    except Exception:
        pass

    company_id = assignment.get("company_id")
    if not company_id and assignment.get("hr_user_id"):
        profile = db.get_profile_record(assignment["hr_user_id"])
        company_id = profile.get("company_id") if profile else None

    criteria_map = build_criteria_for_assignment(
        assignment_id=assignment_id,
        case_id=case_id,
        selected_services=[service_category],
        saved_answers=saved_answers,
        case_context=case_context,
        policy_context=policy_context,
        company_id=company_id,
    )
    criteria = criteria_map.get(backend_key)
    if not criteria:
        raise HTTPException(status_code=400, detail="No criteria built for this service")

    try:
        return recommend_debug(backend_key, criteria, top_n=100)
    except Exception as e:
        log.warning("recommendations/debug failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
