import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from jose import jwt

from ..services.relocation_profile import compute_missing_fields
from ..services.supabase_client import get_supabase_client

router = APIRouter(prefix="/relocation", tags=["relocation"])
api_router = APIRouter(prefix="/api/relocation", tags=["relocation"])


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def _is_permission_error(message: str) -> bool:
    lowered = message.lower()
    return "permission denied" in lowered or "row-level security" in lowered or "rls" in lowered


def _get_user_id(client, user_jwt: str) -> str:
    try:
        response = client.auth.get_user(user_jwt)
        user = getattr(response, "user", None)
        if user and getattr(user, "id", None):
            return str(user.id)
    except Exception:
        pass

    try:
        claims = jwt.get_unverified_claims(user_jwt)
        sub = claims.get("sub")
        if sub:
            return str(sub)
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Invalid token")


class RelocationCaseRequest(BaseModel):
    case_id: Optional[str] = None
    profile: Dict[str, Any]


class RelocationCaseResponse(BaseModel):
    case_id: str
    missing_fields: List[str]
    stage: str


def upsert_relocation_case(
    payload: RelocationCaseRequest,
    authorization: Optional[str] = Header(None),
) -> RelocationCaseResponse:
    user_jwt = _extract_bearer_token(authorization)
    try:
        client = get_supabase_client(user_jwt)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    user_id = _get_user_id(client, user_jwt)
    profile: Dict[str, Any] = payload.profile or {}
    missing_fields = compute_missing_fields(profile)
    stage = "incomplete" if missing_fields else "complete"
    now = datetime.utcnow().isoformat()

    case_id = payload.case_id or uuid.uuid4().hex
    profile_json = json.dumps(profile)
    home_country = profile.get("origin_country")
    host_country = profile.get("destination_country")

    if payload.case_id:
        lookup = (
            client.table("relocation_cases")
            .select("status")
            .eq("id", case_id)
            .execute()
        )
        if lookup.error:
            message = getattr(lookup.error, "message", str(lookup.error))
            if _is_permission_error(message):
                raise HTTPException(status_code=403, detail="Forbidden")
            raise HTTPException(status_code=500, detail="Supabase error")
        if not lookup.data:
            raise HTTPException(status_code=404, detail="Case not found")

        existing_status = lookup.data[0].get("status")
        update_payload: Dict[str, Any] = {
            "profile_json": profile_json,
            "stage": stage,
            "updated_at": now,
        }
        if existing_status is None:
            update_payload["status"] = "draft"
        if home_country:
            update_payload["home_country"] = home_country
        if host_country:
            update_payload["host_country"] = host_country

        update_res = (
            client.table("relocation_cases")
            .update(update_payload)
            .eq("id", case_id)
            .select("id")
            .execute()
        )
        if update_res.error:
            message = getattr(update_res.error, "message", str(update_res.error))
            if _is_permission_error(message):
                raise HTTPException(status_code=403, detail="Forbidden")
            raise HTTPException(status_code=500, detail="Supabase error")
        if not update_res.data:
            raise HTTPException(status_code=404, detail="Case not found")
    else:
        insert_payload: Dict[str, Any] = {
            "id": case_id,
            "employee_id": user_id,
            "profile_json": profile_json,
            "status": "draft",
            "stage": stage,
            "created_at": now,
            "updated_at": now,
        }
        if home_country:
            insert_payload["home_country"] = home_country
        if host_country:
            insert_payload["host_country"] = host_country

        insert_res = (
            client.table("relocation_cases")
            .insert(insert_payload)
            .select("id")
            .execute()
        )
        if insert_res.error:
            message = getattr(insert_res.error, "message", str(insert_res.error))
            if _is_permission_error(message):
                raise HTTPException(status_code=403, detail="Forbidden")
            raise HTTPException(status_code=500, detail="Supabase error")

    run_res = (
        client.table("relocation_runs")
        .insert(
            {
                "case_id": case_id,
                "run_type": "profile_update",
                "input_payload": profile,
                "output_payload": {"missing_fields": missing_fields, "stage": stage},
                "model_provider": None,
                "model_name": None,
            }
        )
        .execute()
    )
    if run_res.error:
        message = getattr(run_res.error, "message", str(run_res.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=403, detail="Forbidden")
        raise HTTPException(status_code=500, detail="Supabase error")

    return RelocationCaseResponse(
        case_id=case_id,
        missing_fields=missing_fields,
        stage=stage,
    )


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


@api_router.get("/cases")
def list_relocation_cases(authorization: Optional[str] = Header(None)):
    client, _ = _get_supabase_client_from_header(authorization)
    result = (
        client.table("relocation_cases")
        .select(
            "id,status,stage,home_country,host_country,created_at,updated_at,employee_id,hr_user_id,company_id"
        )
        .order("updated_at", desc=True)
        .execute()
    )
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=404, detail="Not found")
        raise HTTPException(status_code=500, detail="Supabase error")
    return result.data or []


@api_router.get("/case/{case_id}")
def get_relocation_case(case_id: str, authorization: Optional[str] = Header(None)):
    client, _ = _get_supabase_client_from_header(authorization)
    result = (
        client.table("relocation_cases")
        .select(
            "id,status,stage,home_country,host_country,profile_json,created_at,updated_at"
        )
        .eq("id", case_id)
        .execute()
    )
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=404, detail="Not found")
        raise HTTPException(status_code=500, detail="Supabase error")
    if not result.data:
        raise HTTPException(status_code=404, detail="Case not found")

    row = result.data[0] or {}
    profile = _safe_parse_profile(row.get("profile_json"))
    missing_fields = compute_missing_fields(profile)
    stage = row.get("stage") or ("incomplete" if missing_fields else "complete")

    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "stage": stage,
        "home_country": row.get("home_country"),
        "host_country": row.get("host_country"),
        "profile": profile,
        "missing_fields": missing_fields,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@api_router.get("/case/{case_id}/runs")
def list_relocation_runs(case_id: str, authorization: Optional[str] = Header(None)):
    client, _ = _get_supabase_client_from_header(authorization)
    result = (
        client.table("relocation_runs")
        .select("id,created_at,run_type,input_payload,output_payload,error,model_provider,model_name")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .execute()
    )
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=404, detail="Not found")
        raise HTTPException(status_code=500, detail="Supabase error")
    return result.data or []


router.add_api_route(
    "/case",
    upsert_relocation_case,
    methods=["POST"],
    response_model=RelocationCaseResponse,
)
api_router.add_api_route(
    "/case",
    upsert_relocation_case,
    methods=["POST"],
    response_model=RelocationCaseResponse,
)
