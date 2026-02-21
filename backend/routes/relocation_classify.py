import json
from typing import Optional, Dict, Any

from fastapi import APIRouter, Header, HTTPException

from ..services.relocation_profile import compute_missing_fields
from ..services.relocation_classifier import classify_case
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


def _get_next_version(client, case_id: str) -> int:
    result = (
        client.table("relocation_artifacts")
        .select("version")
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
    if result.data:
        return int(result.data[0]["version"]) + 1
    return 1


@router.post("/case/{case_id}/classify")
def classify_relocation_case(case_id: str, authorization: Optional[str] = Header(None)):
    client = _get_client(authorization)
    case_row = _get_case(client, case_id)
    profile = _safe_parse_profile(case_row.get("profile_json"))
    missing_fields = compute_missing_fields(profile)
    classification = classify_case(profile, missing_fields)

    version = _get_next_version(client, case_id)
    artifact_payload = {
        "case_id": case_id,
        "artifact_type": "case_classification",
        "version": version,
        "content": classification.model_dump(),
        "content_text": None,
    }
    artifact_res = client.table("relocation_artifacts").insert(artifact_payload).execute()
    if artifact_res.error:
        message = getattr(artifact_res.error, "message", str(artifact_res.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=403, detail="Forbidden")
        raise HTTPException(status_code=500, detail="Supabase error")

    run_payload = {
        "case_id": case_id,
        "run_type": "case_classification",
        "input_payload": {"profile": profile, "missing_fields": missing_fields},
        "output_payload": classification.model_dump(),
        "model_provider": None,
        "model_name": None,
        "error": None,
    }
    run_res = client.table("relocation_runs").insert(run_payload).execute()
    if run_res.error:
        message = getattr(run_res.error, "message", str(run_res.error))
        if _is_permission_error(message):
            raise HTTPException(status_code=403, detail="Forbidden")
        raise HTTPException(status_code=500, detail="Supabase error")

    return {
        "case_id": case_id,
        "classification": classification.model_dump(),
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
