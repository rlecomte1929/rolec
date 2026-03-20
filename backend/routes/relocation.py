import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from jose import jwt

from ..services.relocation_profile import compute_missing_fields
from ..services.relocation_classification import (
    compute_case_classification,
    persist_case_classification,
)
from ..services.supabase_client import get_supabase_client
from ..database import db as _rp_db

router = APIRouter(prefix="/relocation", tags=["relocation"])
api_router = APIRouter(prefix="/api/relocation", tags=["relocation"])
logger = logging.getLogger(__name__)


def looks_like_supabase_jwt(token: str) -> bool:
    """ReloPass session tokens are UUIDs; Supabase access tokens are JWTs (three dot-separated segments)."""
    parts = token.split(".")
    return len(parts) == 3 and min(len(p) for p in parts) >= 4


def _profile_from_wizard_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Map wizard Case draft into relocation_profile.compute_missing_fields shape."""
    basics = draft.get("relocationBasics") or {}
    ac = draft.get("assignmentContext") or {}
    out: Dict[str, Any] = {}
    oc = basics.get("originCountry") or basics.get("origin_country")
    dc = (
        basics.get("destCountry")
        or basics.get("destination_country")
        or basics.get("hostCountry")
        or basics.get("host_country")
    )
    if oc:
        out["origin_country"] = oc
    if dc:
        out["destination_country"] = dc
    md = basics.get("targetMoveDate") or basics.get("move_date")
    if md:
        out["move_date"] = md
    et = basics.get("employmentType") or basics.get("employment_type")
    if et:
        out["employment_type"] = et
    ec = ac.get("employerCountry") or ac.get("employer_country") or basics.get("employerCountry")
    if ec:
        out["employer_country"] = ec
    if basics.get("worksRemote") is not None:
        out["works_remote"] = basics.get("worksRemote")
    if basics.get("hasCorporateTaxSupport") is not None:
        out["has_corporate_tax_support"] = basics.get("hasCorporateTaxSupport")
    return out


def _relopass_can_access_assignment(user: Dict[str, Any], assignment: Dict[str, Any]) -> bool:
    role = (user.get("role") or "").upper()
    uid = str(user.get("id") or "").strip()
    if role == "ADMIN":
        return True
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    if role == "EMPLOYEE":
        if emp_id and str(emp_id).strip() == uid:
            return True
        if not emp_id:
            ident = (assignment.get("employee_identifier") or "").strip().lower()
            ids = [x.lower() for x in [user.get("email"), user.get("username")] if x]
            return bool(ident and ids and ident in ids)
        return False
    if role == "HR":
        return bool(hr_id and str(hr_id).strip() == uid)
    return False


def _resolve_assignment_for_relocation_route(route_id: str) -> Optional[Dict[str, Any]]:
    a = _rp_db.get_assignment_by_id(route_id)
    if a:
        return a
    return _rp_db.get_assignment_by_case_id(route_id)


def build_relocation_case_payload_relopass(route_case_id: str, relopass_token: str) -> Dict[str, Any]:
    """
    Build the same JSON shape as Supabase GET /case/{id} using main DB + wizard_cases draft.
    route_case_id may be assignment id or relocation/wizard case id.
    """
    from ..app.db import SessionLocal
    from ..app import crud as app_crud

    user = _rp_db.get_user_by_token(relopass_token.strip())
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    assignment = _resolve_assignment_for_relocation_route(route_case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Case not found")

    if not _relopass_can_access_assignment(user, assignment):
        raise HTTPException(status_code=403, detail="Forbidden")

    actual_case_id = (assignment.get("canonical_case_id") or assignment.get("case_id") or "").strip()
    if not actual_case_id:
        raise HTTPException(status_code=404, detail="Case not found")

    profile: Dict[str, Any] = {}
    rc = _rp_db.get_case_by_id(actual_case_id)
    status = None
    stage_db = None
    home_country = None
    host_country = None
    created_at = None
    updated_at = None
    if rc:
        status = rc.get("status")
        stage_db = rc.get("stage")
        home_country = rc.get("home_country")
        host_country = rc.get("host_country")
        created_at = rc.get("created_at")
        updated_at = rc.get("updated_at")
        pj = _safe_parse_profile(rc.get("profile_json"))
        for k, v in pj.items():
            if v is not None and v != "":
                profile[k] = v

    with SessionLocal() as session:
        wc = app_crud.get_case(session, actual_case_id)
        if not wc:
            wc = app_crud.create_case(
                session,
                actual_case_id,
                {
                    "relocationBasics": {},
                    "employeeProfile": {},
                    "familyMembers": {},
                    "assignmentContext": {},
                },
            )
        draft = json.loads(wc.draft_json or "{}")
        wprof = _profile_from_wizard_draft(draft)
        for k, v in wprof.items():
            if v is not None and v != "" and not profile.get(k):
                profile[k] = v
        if wc.updated_at is not None:
            ua = wc.updated_at.isoformat() if hasattr(wc.updated_at, "isoformat") else str(wc.updated_at)
            if not updated_at:
                updated_at = ua

    missing_fields = compute_missing_fields(profile)
    stage = stage_db or ("incomplete" if missing_fields else "complete")

    return {
        "id": actual_case_id,
        "status": status or "draft",
        "stage": stage,
        "home_country": home_country,
        "host_country": host_country,
        "profile": profile,
        "missing_fields": missing_fields,
        "created_at": created_at,
        "updated_at": updated_at,
    }


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


def _extract_relevant_fields(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "origin_country": profile.get("origin_country"),
        "destination_country": profile.get("destination_country"),
        "move_date": profile.get("move_date"),
        "employment_type": profile.get("employment_type"),
        "employer_country": profile.get("employer_country"),
        "works_remote": profile.get("works_remote"),
        "has_corporate_tax_support": profile.get("has_corporate_tax_support"),
    }


def _diff_relevant_fields(
    prev_profile: Dict[str, Any],
    next_profile: Dict[str, Any],
    prev_missing: List[str],
    next_missing: List[str],
) -> List[str]:
    changed: List[str] = []
    prev_fields = _extract_relevant_fields(prev_profile)
    next_fields = _extract_relevant_fields(next_profile)
    for key, prev_value in prev_fields.items():
        if prev_value != next_fields.get(key):
            changed.append(key)
    if set(prev_missing) != set(next_missing):
        changed.append("missing_fields")
    return changed


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
    prev_profile: Dict[str, Any] = {}
    prev_missing_fields: List[str] = []
    prev_status: Optional[str] = None
    prev_stage: Optional[str] = None

    if payload.case_id:
        lookup = (
            client.table("relocation_cases")
            .select("status,stage,profile_json,home_country,host_country")
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

        row = lookup.data[0] or {}
        existing_status = row.get("status")
        prev_status = existing_status
        prev_stage = row.get("stage")
        prev_profile = _safe_parse_profile(row.get("profile_json"))
        prev_missing_fields = compute_missing_fields(prev_profile)
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

    should_classify = payload.case_id is None
    changed_fields: List[str] = []
    if payload.case_id is not None:
        changed_fields = _diff_relevant_fields(
            prev_profile, profile, prev_missing_fields, missing_fields
        )
        if changed_fields:
            should_classify = True

    if should_classify:
        if changed_fields:
            logger.info("auto_classify triggered case_id=%s changed_fields=%s", case_id, changed_fields)
        else:
            logger.info("auto_classify triggered case_id=%s reason=created", case_id)
        input_payload = {"profile": profile, "missing_fields": missing_fields}
        output_payload = compute_case_classification(
            {**profile, "missing_fields": missing_fields}
        )
        try:
            persist_case_classification(client, case_id, input_payload, output_payload)
        except RuntimeError as exc:
            message = str(exc)
            if _is_permission_error(message):
                raise HTTPException(status_code=403, detail="Forbidden") from exc
            raise HTTPException(status_code=500, detail="Supabase error") from exc
    else:
        logger.info(
            "auto_classify skipped case_id=%s reason=no_relevant_changes",
            case_id,
        )

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
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "").strip()
    if not looks_like_supabase_jwt(token):
        return build_relocation_case_payload_relopass(case_id, token)

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
