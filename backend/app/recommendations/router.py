"""FastAPI router for recommendations API."""
from __future__ import annotations

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ..auth_deps import require_assignment_visibility, require_hr_or_employee
from .criteria_builder import _flatten_saved_answers, build_criteria_for_assignment
from .engine import recommend

log = logging.getLogger(__name__)
from .registry import get_plugin, list_categories
from .types import RecommendationResponse

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class _BatchRequest:
    def __init__(self, assignment_id: str, selected_services: Optional[List[str]] = None):
        self.assignment_id = assignment_id
        self.selected_services = selected_services or []


@router.post("/batch")
def post_recommendations_batch(
    request: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
    body: Dict[str, Any] = Body(...),
):
    """
    Get recommendations for all selected services in one round-trip.
    Uses canonical criteria builder (assignment, case, saved answers, policy).
    """
    assignment_id = body.get("assignment_id")
    if not assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id is required")
    req = _BatchRequest(
        assignment_id=str(assignment_id),
        selected_services=body.get("selected_services"),
    )
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    start = time.perf_counter()

    # Avoid circular imports
    from ...database import db
    from ...policy_engine import PolicyEngine
    from ...services.policy_adapter import normalize_policy_caps

    from ..db import SessionLocal
    from .. import crud as app_crud

    assignment = require_assignment_visibility(req.assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")

    selected_keys = req.selected_services
    if not selected_keys:
        services = db.list_case_services(assignment["id"])
        selected_keys = [r["service_key"] for r in services if r.get("selected") in (True, 1)]
    valid_svc = {"housing", "schools", "movers", "banks", "insurances", "electricity"}
    selected_keys = [k for k in selected_keys if k in valid_svc]

    if not selected_keys:
        return {"results": {}, "message": "No selected services with recommendation support"}

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
        assignment_id=req.assignment_id,
        case_id=case_id,
        selected_services=selected_keys,
        saved_answers=saved_answers,
        case_context=case_context,
        policy_context=policy_context,
        company_id=company_id,
    )

    def _run_one(backend_key: str, criteria: Dict[str, Any]) -> tuple[str, Any | None]:
        dest_city_val = (criteria.get("destination_city") or "").strip()
        if backend_key in ("living_areas", "schools", "movers") and not dest_city_val:
            log.warning(
                "request_id=%s category=%s recommendations_batch skipped_missing_destination",
                request_id, backend_key,
            )
            return (backend_key, None)
        try:
            return (backend_key, recommend(backend_key, criteria, top_n=10))
        except Exception as e:
            log.warning(
                "request_id=%s category=%s recommendations_batch failed error=%s",
                request_id, backend_key, str(e),
            )
            return (backend_key, None)

    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(criteria_map) or 1)) as ex:
        futures = {
            ex.submit(_run_one, backend_key, criteria): backend_key
            for backend_key, criteria in criteria_map.items()
        }
        for future in as_completed(futures):
            key, rec_result = future.result()
            if rec_result is not None:
                results[key] = rec_result

    dur_ms = (time.perf_counter() - start) * 1000
    log.info(
        "request_id=%s assignment_id=%s services=%s recommendations_batch succeeded dur_ms=%.2f",
        request_id, req.assignment_id, list(results.keys()), dur_ms,
    )
    try:
        from ...services.analytics_service import emit_event, EVENT_RECOMMENDATIONS_GENERATED
        total_count = sum(len(r.get("items", [])) for r in results.values())
        emit_event(
            EVENT_RECOMMENDATIONS_GENERATED,
            request_id=request_id,
            assignment_id=req.assignment_id,
            case_id=case_id,
            user_id=user.get("id"),
            user_role=user.get("role"),
            duration_ms=dur_ms,
            service_categories=list(results.keys()),
            counts={"categories": len(results), "items": total_count},
        )
    except Exception:
        pass
    return {"results": results}


@router.get("/categories")
def get_categories():
    """List all recommendation categories with schema info."""
    return {"categories": list_categories()}


@router.get("/{category}/schema")
def get_schema(category: str):
    """Get JSON schema for category criteria."""
    plugin = get_plugin(category)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")
    return plugin.CriteriaModel.model_json_schema()


class RecommendRequest:
    def __init__(self, criteria: Dict[str, Any], top_n: Optional[int] = None):
        self.criteria = criteria
        self.top_n = top_n or 10


DESTINATION_REQUIRING = ("living_areas", "schools", "movers")


@router.post("/{category}", response_model=RecommendationResponse)
def post_recommend(category: str, body: Dict[str, Any], request: Request):
    """Get recommendations for a category."""
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    start = time.perf_counter()
    plugin = get_plugin(category)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Category not found: {category}")
    criteria = body.get("criteria", {})
    top_n = body.get("top_n", 10)
    if not isinstance(criteria, dict):
        raise HTTPException(status_code=400, detail="criteria must be an object")
    dest_city = (criteria.get("destination_city") or "").strip()
    if category in DESTINATION_REQUIRING and not dest_city:
        log.warning(
            "request_id=%s category=%s recommendations_load rejected_missing_destination",
            request_id, category,
        )
        raise HTTPException(
            status_code=400,
            detail="destination_city is required for this category. Please complete your preferences with a destination city.",
        )
    try:
        result = recommend(category, criteria, top_n=int(top_n))
        dur_ms = (time.perf_counter() - start) * 1000
        dest = (criteria.get("destination_city") or "").strip()
        log.info(
            "request_id=%s category=%s dest_city=%s recommendations_load succeeded dur_ms=%.2f",
            request_id, category, dest or "(none)", dur_ms,
        )
        try:
            from ...services.analytics_service import emit_event, EVENT_RECOMMENDATIONS_GENERATED
            items = result.get("items", []) if isinstance(result, dict) else []
            emit_event(
                EVENT_RECOMMENDATIONS_GENERATED,
                request_id=request_id,
                duration_ms=dur_ms,
                service_categories=[category],
                counts={"items": len(items)},
                extra={"destination_city": dest or None},
            )
        except Exception:
            pass
        return result
    except Exception as e:
        dur_ms = (time.perf_counter() - start) * 1000
        log.warning(
            "request_id=%s category=%s recommendations_load failed dur_ms=%.2f error=%s",
            request_id, category, dur_ms, str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
