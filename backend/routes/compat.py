import json
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text

from .._jwt_claims import get_unverified_claims as _jwt_unverified_claims
from ..app.services.relocation_profile import compute_missing_fields
from ..app.services.supabase_client import get_supabase_client
from .relocation import _extract_bearer_token, _is_permission_error
from ..database import db
from ..app.db import SessionLocal
from ..app import crud as app_crud
from ..app.routers import cases as wizard_cases_router
from ..app.services.requirements_builder import compute_case_requirements
from ..app.services.case_service import _assert_case_access

router = APIRouter(prefix="/api", tags=["compat"])


def _get_supabase_client_from_header(authorization: Optional[str]):
    user_jwt = _extract_bearer_token(authorization)
    try:
        client = get_supabase_client(user_jwt)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return client, user_jwt


def _is_jwt(token: str) -> bool:
    return token.count(".") == 2


def _get_user_from_session_token(token: str) -> Dict[str, Any]:
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _get_case_row_for_user(case_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with db.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM relocation_cases "
                "WHERE id = :id AND (employee_id = :uid OR hr_user_id = :uid)"
            ),
            {"id": case_id, "uid": user_id},
        ).fetchone()
    return db._row_to_dict(row)


def _get_wizard_case_dto(
    case_id: str, requesting_user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if not case:
            return None
        draft = json.loads(case.draft_json)
        # Single source of truth: derive status via the shared resolver, scoped to
        # the REQUESTING user so the detail agrees with that user's
        # GET /api/employee/cases (both pick the same assignment row). When the
        # requester has no assignment for the case (HR/admin), fall back to the
        # most-recent assignment overall. Scoping by id (not role) keeps this immune
        # to role-string casing — the bug that made the detail never scope.
        assignment_status = (
            db.resolve_case_status(case_id, requesting_user_id)
            or db.resolve_case_status(case_id, None)
        )
        return wizard_cases_router._case_dto(
            case, draft, assignment_status=assignment_status
        ).model_dump()


def _default_wizard_draft() -> Dict[str, Any]:
    return {
        "relocationBasics": {},
        "employeeProfile": {},
        "familyMembers": {},
        "assignmentContext": {},
    }


def _ensure_wizard_case(case_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if not case:
            case = app_crud.create_case(session, case_id, _default_wizard_draft())
        draft = json.loads(case.draft_json)
        return wizard_cases_router._case_dto(case, draft).model_dump()


def _safe_parse_profile(profile_json: Optional[str]) -> Dict[str, Any]:
    if not profile_json:
        return {}
    try:
        parsed = json.loads(profile_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _title_case_fallback(value: str) -> str:
    return " ".join(word.capitalize() for word in value.replace("_", " ").split())


@router.get("/cases/{case_id}")
def compat_get_case(case_id: str, authorization: Optional[str] = Header(None)):
    token = _extract_bearer_token(authorization)
    # Authoritative case status = the linked assignment's lifecycle status, the
    # SAME source GET /api/employee/cases uses. resolve_case_status matches by
    # canonical_case_id/case_id/id, so it works even when the caseId is a
    # relocation_cases id with no wizard_cases row — the path where this detail
    # used to fall through to _ensure_wizard_case and return 'created'. None when
    # the case has no assignment (then the case-row status is used).
    assignment_status: Optional[str] = None
    if _is_jwt(token):
        client, _ = _get_supabase_client_from_header(authorization)
        result = client.table("relocation_cases").select("*").eq("id", case_id).execute()
        if result.error:
            message = getattr(result.error, "message", str(result.error))
            if _is_permission_error(message):
                raise HTTPException(status_code=403, detail="Forbidden")
            raise HTTPException(status_code=500, detail="Supabase error")
        if not result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        row = result.data[0] or {}
    else:
        user = _get_user_from_session_token(token)
        # [AIQ-1535] Tenant guard. This branch reads through the service-role `db` connection,
        # which BYPASSES RLS — so without an explicit check `_get_wizard_case_dto` /
        # `_ensure_wizard_case` / `_get_case_row_for_user` below return ANY company's case to any
        # authenticated session (cross-tenant IDOR leaking relocation PII). Mirror the safe
        # cases_read.get_case handler this route shadows: reuse the shared guard, which raises
        # 403 (case belongs to another tenant) or 404 (unknown/malformed id) BEFORE any case
        # body is built. (The JWT branch above runs under the caller's JWT, so RLS scopes it.)
        _assert_case_access(user, case_id)
        # Scope to the requesting user (by id, not role); fall back to the
        # most-recent assignment when the requester has none (HR/admin).
        assignment_status = (
            db.resolve_case_status(case_id, user.get("id"))
            or db.resolve_case_status(case_id, None)
        )
        wizard_case = _get_wizard_case_dto(case_id, user.get("id"))
        if wizard_case:
            return wizard_case
        row = _get_case_row_for_user(case_id, user["id"])
        if not row:
            dto = _ensure_wizard_case(case_id)
            if assignment_status:
                dto["status"] = assignment_status
            return dto
    profile = _safe_parse_profile(row.get("profile_json"))
    missing_fields = compute_missing_fields(profile)
    # Convenience shortcut: expose employer at top level so clients don't need
    # to traverse primaryApplicant.employer — also returned inside profile_json.
    employer_obj = (profile.get("primaryApplicant") or {}).get("employer") or {}

    return {
        "id": row.get("id", case_id),
        "status": assignment_status or row.get("status") or "draft",
        "stage": row.get("stage") or "incomplete",
        "home_country": row.get("home_country"),
        "host_country": row.get("host_country"),
        # Return profile_json as parsed dict (not raw string) so callers can
        # traverse .employer.name etc. without double-parsing.
        "profile_json": profile,
        "employer": employer_obj,
        "profile": profile,
        "missing_fields": missing_fields,
    }


@router.get("/cases/{case_id}/requirements")
def compat_get_requirements(case_id: str, authorization: Optional[str] = Header(None)):
    token = _extract_bearer_token(authorization)
    if _is_jwt(token):
        client, _ = _get_supabase_client_from_header(authorization)
        result = client.table("relocation_cases").select("profile_json").eq("id", case_id).execute()
        if result.error:
            message = getattr(result.error, "message", str(result.error))
            if _is_permission_error(message):
                raise HTTPException(status_code=403, detail="Forbidden")
            raise HTTPException(status_code=500, detail="Supabase error")
        if not result.data:
            raise HTTPException(status_code=404, detail="Case not found")
        profile = _safe_parse_profile(result.data[0].get("profile_json"))
    else:
        user = _get_user_from_session_token(token)
        try:
            return compute_case_requirements(case_id).model_dump()
        except ValueError:
            pass
        row = _get_case_row_for_user(case_id, user["id"])
        if not row:
            _ensure_wizard_case(case_id)
            return compute_case_requirements(case_id).model_dump()
        profile = _safe_parse_profile(row.get("profile_json"))
    missing_fields = compute_missing_fields(profile)
    label_map = {
        "origin_country": "Origin country",
        "destination_country": "Destination country",
        "employment_type": "Employment type",
        "move_date": "Move date",
        "employer_country": "Employer country",
    }

    requirements = [
        {
            "key": field,
            "label": label_map.get(field, _title_case_fallback(field)),
            "status": "missing",
        }
        for field in missing_fields
    ]

    return {
        "case_id": case_id,
        "requirements": requirements,
        "missing_fields": missing_fields,
    }


@router.get("/admin/context")
def compat_admin_context(authorization: Optional[str] = Header(None)):
    user_jwt = _extract_bearer_token(authorization)
    email = None
    role = None
    user_id = None
    claims: Dict[str, Any] = {}

    try:
        claims = _jwt_unverified_claims(user_jwt)
        email = email or claims.get("email")
        role = role or claims.get("role")
        user_id = user_id or claims.get("sub")
    except Exception:
        pass

    is_privileged = False
    if email and email.lower().endswith("@relopass.com"):
        is_privileged = True
    if role and str(role).lower() in {"admin", "hr"}:
        is_privileged = True

    return {
        "role": "admin_or_hr" if is_privileged else "employee",
        "user_id": str(user_id) if user_id else "",
        "company_id": None,
    }
