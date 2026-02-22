import json
from typing import Optional, Dict, Any

from fastapi import APIRouter, Header, HTTPException

from ..services.relocation_classification import (
    compute_case_classification,
    persist_case_classification,
)
from ..services.relocation_profile import compute_missing_fields
from ..services.supabase_client import get_supabase_client
from .relocation import _extract_bearer_token, _is_permission_error

router = APIRouter(prefix="/api/relocation", tags=["relocation"])


def _safe_parse_profile(profile_json: Optional[str]) -> Dict[str, Any]:
    if not profile_json:
        return {}
    try:
        parsed = json.loads(profile_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _get_client(authorization: Optional[str]):
    user_jwt = _extract_bearer_token(authorization)
    try:
        client = get_supabase_client(user_jwt)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return client


def _get_case(client, case_id: str) -> Dict[str, Any]:
    result = (
        client.table("relocation_cases")
        .select("id,profile_json")
        .eq("id", case_id)
        .execute()
    )
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=500, detail="Supabase error")
    if not result.data:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.data[0]


@router.post("/case/{case_id}/classify")
def classify_relocation_case(case_id: str, authorization: Optional[str] = Header(None)):
    client = _get_client(authorization)
    case_row = _get_case(client, case_id)
    profile = _safe_parse_profile(case_row.get("profile_json"))
    missing_fields = compute_missing_fields(profile)
    input_payload = {"profile": profile, "missing_fields": missing_fields}
    output_payload = compute_case_classification({**profile, "missing_fields": input_payload["missing_fields"]})
    try:
        persist_case_classification(client, case_id, input_payload, output_payload)
    except RuntimeError as exc:
        message = str(exc)
        if _is_permission_error(message):
            raise HTTPException(status_code=403, detail="Forbidden")
        raise HTTPException(status_code=500, detail="Supabase error") from exc

    return {
        "case_id": case_id,
        "classification": output_payload,
    }


@router.get("/case/{case_id}/classification")
def get_relocation_classification(case_id: str, authorization: Optional[str] = Header(None)):
    client = _get_client(authorization)
    result = (
        client.table("relocation_artifacts")
        .select("content,version,created_at")
        .eq("case_id", case_id)
        .eq("artifact_type", "case_classification")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=500, detail="Supabase error")
    if not result.data:
        raise HTTPException(status_code=404, detail="Classification not found")
    row = result.data[0]
    return {
        "case_id": case_id,
        "classification": row.get("content") or {},
        "version": row.get("version"),
        "created_at": row.get("created_at"),
    }
