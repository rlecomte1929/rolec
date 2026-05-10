"""
Public Resources API - Read-only endpoints for HR/Employee/Admin.
Uses published views only. Never exposes internal governance fields.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query

from ..database import db
from ..app.db import SessionLocal
from ..app import crud as app_crud
from ..services.resources.public_service import (
    get_resource_context as build_context,
    get_published_resources,
    get_published_events,
    get_recommended_resources,
    get_resources_page_data,
)

router = APIRouter(prefix="/api/resources", tags=["resources"])


def _require_hr_or_employee(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Allow HR, Employee, or Admin. Avoids circular import from main."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    role = (user.get("role") or "").upper()
    if role in ("ADMIN", "HR", "EMPLOYEE"):
        return user
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() in ("ADMIN", "HR", "EMPLOYEE"):
        return user
    raise HTTPException(status_code=403, detail="Access denied")


def _require_case_access_via_assignment(assignment_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve assignment, validate access, return assignment with case_id."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    role = (user.get("role") or "").upper()
    is_hr = role in ("HR", "ADMIN")
    is_employee = role == "EMPLOYEE"
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    user_id = user.get("id")
    visible = False
    if is_employee and emp_id == user_id:
        visible = True
    if is_hr and (hr_id == user_id or role == "ADMIN"):
        visible = True
    if not visible:
        email = (user.get("email") or "").strip().lower()
        if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
            visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Access denied")
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no case")
    return {"assignment": assignment, "case_id": case_id}


def _get_draft_for_case(case_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if not case:
            return {}
        return json.loads(case.draft_json or "{}")


@router.get("/context")
def get_resource_context(
    assignment_id: str = Query(..., description="Assignment id (gate for case access)"),
    user: Dict[str, Any] = Depends(_require_hr_or_employee),
):
    """Get resource context for personalization. Requires assignment access."""
    result = _require_case_access_via_assignment(assignment_id, user)
    case_id = result["case_id"]
    draft = _get_draft_for_case(case_id)
    return build_context(case_id, draft)


@router.get("")
def list_published_resources(
    assignment_id: str = Query(..., description="Assignment id (gate for case access)"),
    filters: Optional[str] = Query(None, description="JSON: city, category, audienceType, etc."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user: Dict[str, Any] = Depends(_require_hr_or_employee),
):
    """List published resources. Uses safe published view."""
    result = _require_case_access_via_assignment(assignment_id, user)
    case_id = result["case_id"]
    draft = _get_draft_for_case(case_id)
    context = build_context(case_id, draft)
    cc = context.get("countryCode") or "NO"
    filter_dict = {}
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError:
            pass
    return {"resources": get_published_resources(cc, filter_dict, page, limit)}


@router.get("/events")
def list_published_events(
    assignment_id: str = Query(..., description="Assignment id (gate for case access)"),
    filters: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user: Dict[str, Any] = Depends(_require_hr_or_employee),
):
    """List published events. Uses safe published view."""
    result = _require_case_access_via_assignment(assignment_id, user)
    case_id = result["case_id"]
    draft = _get_draft_for_case(case_id)
    context = build_context(case_id, draft)
    cc = context.get("countryCode") or "NO"
    filter_dict = {}
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError:
            pass
    return {"events": get_published_events(cc, filter_dict, page, limit)}


@router.get("/recommended")
def get_recommended(
    assignment_id: str = Query(..., description="Assignment id (gate for case access)"),
    limit: int = Query(10, ge=1, le=20),
    user: Dict[str, Any] = Depends(_require_hr_or_employee),
):
    """Get recommended resources for the case."""
    result = _require_case_access_via_assignment(assignment_id, user)
    case_id = result["case_id"]
    draft = _get_draft_for_case(case_id)
    context = build_context(case_id, draft)
    return get_recommended_resources(context, limit)


@router.get("/page")
def get_resources_page(
    assignment_id: str = Query(..., description="Assignment id (gate for case access)"),
    filters: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(_require_hr_or_employee),
):
    """Composite: context, categories, resources, events, recommended. All from safe published sources."""
    result = _require_case_access_via_assignment(assignment_id, user)
    case_id = result["case_id"]
    draft = _get_draft_for_case(case_id)
    filter_dict = {}
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError:
            pass
    return get_resources_page_data(case_id, draft, filter_dict)
