import json
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Header, HTTPException
from jose import jwt

from ..services.relocation_profile import compute_missing_fields
from ..services.supabase_client import get_supabase_client
from .relocation import _extract_bearer_token, _is_permission_error

router = APIRouter(prefix="/api", tags=["compat"])


def _get_supabase_client_from_header(authorization: Optional[str]):
    user_jwt = _extract_bearer_token(authorization)
    try:
        client = get_supabase_client(user_jwt)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return client, user_jwt


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
    profile = _safe_parse_profile(row.get("profile_json"))
    missing_fields = compute_missing_fields(profile)

    return {
        "id": row.get("id", case_id),
        "status": row.get("status") or "draft",
        "stage": row.get("stage") or "incomplete",
        "home_country": row.get("home_country"),
        "host_country": row.get("host_country"),
        "profile_json": row.get("profile_json") or "",
        "profile": profile,
        "missing_fields": missing_fields,
    }


@router.get("/cases/{case_id}/requirements")
def compat_get_requirements(case_id: str, authorization: Optional[str] = Header(None)):
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
        claims = jwt.get_unverified_claims(user_jwt)
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
