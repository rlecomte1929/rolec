"""Compensation & Allowance — structured policy matrix routers.

Extracted from backend/main.py (AUDIT-C2 Month-0 P3).

Four routers are exported for registration in main.py:
  hr_policy_config_router       — /api/hr/policy-config/*
  admin_policy_config_router    — /api/admin/policy-config/*
  employee_policy_config_router — /api/employee/policy-config
  public_policy_config_router   — /api/policy-config/caps

Company scope:
  HR routes: companyId query is ignored unless the user is admin (is_admin);
    HR always uses their own company from profile / hr_users.
  Admin routes: companyId is required and selects the tenant.
  Employee route: company comes from the employee profile;
    assignmentId/caseId only tighten context.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ...database import db
from ...schemas import UserRole
from ...schemas_policy_caps import CapsCompareRequest
from ..auth_deps import _effective_user, get_current_user, require_admin, require_role
from ..services.policy_config_matrix_service import PolicyConfigMatrixService
from ..services.policy_config_targeting import (
    normalize_assignment_type,
    normalize_family_status,
    validate_optional_query_assignment_type,
    validate_optional_query_employee_level,
    validate_optional_query_family_status,
)

# ---------------------------------------------------------------------------
# Shared service instance
# ---------------------------------------------------------------------------
policy_config_matrix_svc = PolicyConfigMatrixService(db)


# ---------------------------------------------------------------------------
# Private helpers (scoped to this module)
# ---------------------------------------------------------------------------

def _get_hr_company_id(user: Dict[str, Any]) -> Optional[str]:
    """Resolve company_id for HR user. Uses hr_users first, then profile."""
    uid = user.get("id")
    if not uid:
        return None
    cid = db.get_hr_company_id(uid)
    if cid:
        return cid
    profile = db.get_profile_record(uid)
    return profile.get("company_id") if profile else None


def _resolve_employee_company_id(user: Dict[str, Any]) -> Optional[str]:
    """Resolve company_id for an employee. Profile first (uuid-native employees),
    then via their case assignment — a legacy/seed employee's non-UUID id can't
    look up the uuid-keyed profiles row, but case_assignments.employee_user_id
    carries that id, so the company is recoverable from the assignment."""
    uid = user.get("id")
    if not uid:
        return None
    profile = db.get_profile_record(uid)
    if profile and profile.get("company_id"):
        return profile.get("company_id")
    assignment = db.get_assignment_for_employee(uid, request_id=None)
    if assignment:
        return db.get_company_id_for_assignment_id(str(assignment.get("id")))
    return None


def _require_company_for_user(user: Dict[str, Any]) -> Dict[str, Any]:
    profile = db.get_profile_record(user.get("id")) or {}
    company_id = _get_hr_company_id(user) if user.get("role") == UserRole.HR.value else profile.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User missing company association")
    profile["company_id"] = company_id
    return profile


def _resolve_company_for_policy(
    user: Dict[str, Any], company_id_override: Optional[str] = None
) -> str:
    """Resolve company_id for policy matrix APIs.

    Admins may pass company_id_override to act on another tenant. Non-admin HR
    users always receive their own company; passing companyId on /api/hr/...
    does not switch tenants.
    """
    if user.get("is_admin") and company_id_override:
        return company_id_override
    profile = _require_company_for_user(user)
    return profile.get("company_id") or ""


def _policy_matrix_validation_http(exc: ValueError) -> HTTPException:
    try:
        payload = json.loads(str(exc))
        return HTTPException(status_code=422, detail=payload)
    except Exception:
        return HTTPException(
            status_code=422,
            detail={"code": "validation_error", "errors": [{"message": str(exc)}]},
        )


def _policy_matrix_company_hr(user: Dict[str, Any], company_id: Optional[str]) -> str:
    return _resolve_company_for_policy(user, company_id)


def _policy_matrix_resolve_company_caps(
    user: Dict[str, Any],
    company_id: Optional[str],
    assignment_id: Optional[str],
    case_id: Optional[str],
) -> str:
    if user.get("is_admin"):
        if company_id and str(company_id).strip():
            return str(company_id).strip()
        if assignment_id:
            c = db.get_company_id_for_assignment_id(str(assignment_id))
            if c:
                return c
        if case_id:
            a = db.get_assignment_by_case_id(str(case_id))
            if a:
                c = db.get_company_id_for_assignment_id(str(a.get("id")))
                if c:
                    return c
        raise HTTPException(
            status_code=400,
            detail={"code": "missing_scope", "message": "Provide company_id, assignment_id, or case_id"},
        )
    role = (user.get("role") or "").upper()
    if role == UserRole.HR.value:
        cid = _get_hr_company_id(user)
        if not cid:
            raise HTTPException(status_code=400, detail="HR user missing company")
        if assignment_id and not db.assignment_belongs_to_company(str(assignment_id), cid):
            raise HTTPException(status_code=403, detail="Assignment not in your company")
        if case_id:
            a = db.get_assignment_by_case_id(str(case_id))
            if not a or not db.assignment_belongs_to_company(str(a.get("id")), cid):
                raise HTTPException(status_code=403, detail="Case not in your company")
        return cid
    if role == UserRole.EMPLOYEE.value:
        cid = _resolve_employee_company_id(user)
        if not cid:
            raise HTTPException(status_code=400, detail="Employee missing company")
        if assignment_id:
            a = db.get_assignment_by_id(str(assignment_id))
            if not a:
                raise HTTPException(status_code=404, detail="Assignment not found")
            if a.get("employee_user_id") != user.get("id"):
                raise HTTPException(status_code=403, detail="Assignment not assigned to user")
            c = db.get_company_id_for_assignment_id(str(assignment_id))
            if c and c != cid:
                raise HTTPException(status_code=403, detail="Assignment company mismatch")
        if case_id:
            a = db.get_assignment_by_case_id(str(case_id))
            if not a:
                raise HTTPException(status_code=404, detail="Case not found")
            if a.get("employee_user_id") != user.get("id"):
                raise HTTPException(status_code=403, detail="Not authorized for this case")
            c = db.get_company_id_for_assignment_id(str(a.get("id")))
            if c and c != cid:
                raise HTTPException(status_code=403, detail="Case company mismatch")
        return str(cid)
    raise HTTPException(status_code=403, detail="Not authorized for policy-config caps")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
hr_policy_config_router = APIRouter(prefix="/api/hr", tags=["compensation-policy-config"])
admin_policy_config_router = APIRouter(prefix="/api/admin", tags=["admin-compensation-policy-config"])
employee_policy_config_router = APIRouter(prefix="/api/employee", tags=["employee-compensation-policy-config"])
public_policy_config_router = APIRouter(prefix="/api", tags=["policy-config-caps"])


# ---------------------------------------------------------------------------
# HR routes
# ---------------------------------------------------------------------------

@hr_policy_config_router.get("/policy-config")
def hr_get_policy_config(
    companyId: Optional[str] = Query(None, alias="companyId"),
    assignmentType: Optional[str] = Query(None, alias="assignmentType"),
    familyStatus: Optional[str] = Query(None, alias="familyStatus"),
    employeeLevel: Optional[str] = Query(None, alias="employeeLevel"),
    effectiveRowsOnly: bool = Query(False, alias="effectiveRowsOnly"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    try:
        at = validate_optional_query_assignment_type(assignmentType)
        fs = validate_optional_query_family_status(familyStatus)
        el = validate_optional_query_employee_level(employeeLevel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Graceful onboarding: an HR not yet linked to a company gets a read-only
    # empty scaffold (company_setup_required) instead of a 400 — a missing
    # precondition must degrade gracefully (see SKILL.md Phase 0.5).
    if not user.get("is_admin") and not _get_hr_company_id(user):
        return policy_config_matrix_svc.empty_onboarding_payload(
            assignment_type=at,
            family_status=fs,
            employee_level=el,
            effective_rows_only=effectiveRowsOnly,
        )
    cid = _policy_matrix_company_hr(user, companyId)
    return policy_config_matrix_svc.get_working_payload(
        cid,
        assignment_type=at,
        family_status=fs,
        employee_level=el,
        effective_rows_only=effectiveRowsOnly,
    )


@hr_policy_config_router.post("/policy-config/draft")
def hr_post_policy_config_draft(
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _policy_matrix_company_hr(user, companyId)
    return policy_config_matrix_svc.ensure_draft(cid, created_by=user.get("id"))


@hr_policy_config_router.put("/policy-config/draft")
def hr_put_policy_config_draft(
    body: Dict[str, Any] = Body(...),
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _policy_matrix_company_hr(user, companyId)
    try:
        return policy_config_matrix_svc.put_draft(cid, body, changed_by=user.get("id"))
    except ValueError as e:
        raise _policy_matrix_validation_http(e)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "draft_not_found", "message": "Draft not found"})
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail={"code": "not_draft", "message": "Only draft versions can be overwritten"},
        )


@hr_policy_config_router.post("/policy-config/publish")
def hr_post_policy_config_publish(
    body: Optional[Dict[str, Any]] = Body(default=None),
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _policy_matrix_company_hr(user, companyId)
    payload = body or {}
    try:
        return policy_config_matrix_svc.publish_draft(
            cid,
            policy_version_id=payload.get("policy_version"),
            created_by=user.get("id"),
        )
    except ValueError as e:
        raise _policy_matrix_validation_http(e)
    except KeyError as e:
        code = e.args[0] if e.args else ""
        if code == "no_draft":
            raise HTTPException(
                status_code=409,
                detail={"code": "no_draft", "message": "No draft exists to publish"},
            )
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Draft not found"})
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail={"code": "draft_mismatch", "message": "policy_version does not match current draft"},
        )


@hr_policy_config_router.get("/policy-config/templates")
def hr_get_policy_config_templates(
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    List the admin-curated starter templates available to HR for the
    "Start from a template" card. Returns lightweight metadata only;
    the full row expansion happens server-side when HR applies one.
    """
    from ..services.policy_config_templates import list_templates

    _ = user  # auth already enforced by require_role
    return {"templates": list_templates()}


@hr_policy_config_router.post("/policy-config/draft/apply-template")
def hr_post_policy_config_apply_template(
    body: Dict[str, Any] = Body(...),
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Apply a starter template to the company's draft. Body:
      { template_key: "conservative"|"standard"|"premium",
        replace_existing_draft?: bool }

    Returns the fresh working payload on success. Live published
    version is NOT touched — employees continue seeing the current
    policy until HR publishes the replacement.
    """
    cid = _policy_matrix_company_hr(user, companyId)
    template_key = str(body.get("template_key") or "").strip().lower()
    replace = bool(body.get("replace_existing_draft", False))
    if not template_key:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "template_key is required"},
        )
    try:
        return policy_config_matrix_svc.apply_template_to_draft(
            cid,
            template_key=template_key,
            replace_existing_draft=replace,
            created_by=user.get("id"),
        )
    except KeyError as exc:
        code = exc.args[0] if exc.args else ""
        if isinstance(code, str) and code.startswith("unknown_template:"):
            raise HTTPException(
                status_code=404,
                detail={"code": "unknown_template", "message": "Unknown template"},
            )
        if code == "draft_has_rows":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "draft_has_rows",
                    "message": (
                        "A draft with existing rows is already in progress. "
                        "Confirm to replace it with the template, or edit the "
                        "current draft in the row drawer."
                    ),
                },
            )
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Not found"})


@hr_policy_config_router.post("/policy-config/draft/import-extraction")
def hr_post_policy_config_import_extraction(
    body: Dict[str, Any] = Body(...),
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    AIQ-873: import an extracted policy's benefits (policy_benefits, the document
    pipeline) into the company's config-matrix draft as `extracted_llm` rows.
    Body: { policy_id }.

    Each extracted benefit whose key maps to a canonical matrix key is inserted
    into the draft ONLY if that key is not already present — existing
    manual_hr/template/seeded rows are never clobbered. Extracted free-text terms
    land in `notes`, per-field confidence in `field_confidence`; structured amounts
    stay at defaults for HR to fill. Unmapped extraction keys are returned for HR
    manual entry. The live published version is untouched.

    Returns { imported, skipped_existing, unmapped, version_id }.
    """
    cid = _policy_matrix_company_hr(user, companyId)
    policy_id = str(body.get("policy_id") or "").strip()
    if not policy_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "policy_id is required"},
        )
    # Tenant scope: the extracted policy must belong to the HR user's own company.
    pol = db.get_company_policy(policy_id)
    if not pol or str(pol.get("company_id") or "") != str(cid):
        raise HTTPException(
            status_code=404,
            detail={"code": "policy_not_found", "message": "Policy not found for this company"},
        )
    try:
        return policy_config_matrix_svc.import_extraction_to_draft(
            policy_id, changed_by=user.get("id")
        )
    except KeyError as exc:
        code = exc.args[0] if exc.args else "not_found"
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Not found"})


@hr_policy_config_router.get("/policy-config/diff")
def hr_get_policy_config_diff(
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Draft vs Live snapshot for the HR Policy "Draft vs Live" section.
    See PolicyConfigMatrixService.compute_diff for the response shape.
    """
    # Graceful onboarding: HR not yet linked to a company gets an empty diff.
    if not user.get("is_admin") and not _get_hr_company_id(user):
        return policy_config_matrix_svc.empty_diff()
    cid = _policy_matrix_company_hr(user, companyId)
    return policy_config_matrix_svc.compute_diff(cid)


@hr_policy_config_router.post("/policy-config/draft/revert-row")
def hr_post_policy_config_revert_row(
    body: Dict[str, Any] = Body(...),
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Revert one benefit row of the current draft back to the live
    version. Body: {benefit_key, targeting_signature}. Returns the
    refreshed diff so the UI can re-render without a second request.
    """
    cid = _policy_matrix_company_hr(user, companyId)
    try:
        return policy_config_matrix_svc.revert_row_to_live(
            cid,
            benefit_key=str(body.get("benefit_key") or "").strip(),
            targeting_signature=str(body.get("targeting_signature") or "global").strip(),
        )
    except ValueError as e:
        raise _policy_matrix_validation_http(e)
    except KeyError as e:
        code = e.args[0] if e.args else ""
        if code == "no_draft":
            raise HTTPException(
                status_code=409,
                detail={"code": "no_draft", "message": "No draft exists to revert"},
            )
        if code == "row_not_found":
            raise HTTPException(
                status_code=404,
                detail={"code": "row_not_found", "message": "Benefit row not found in live or draft"},
            )
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Not found"})


@hr_policy_config_router.get("/policy-config/history")
def hr_get_policy_config_history(
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _policy_matrix_company_hr(user, companyId)
    return {"versions": policy_config_matrix_svc.history(cid)}


@hr_policy_config_router.get("/policy-config/versions/{version_id}")
def hr_get_policy_config_version(
    version_id: str,
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _policy_matrix_company_hr(user, companyId)
    try:
        return policy_config_matrix_svc.get_version_readonly_payload(cid, version_id)
    except KeyError as e:
        code = e.args[0] if e.args else ""
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Version not found"})
    except PermissionError:
        raise HTTPException(
            status_code=400,
            detail={"code": "version_not_readable", "message": "Only published or archived versions can be opened from history"},
        )


@hr_policy_config_router.get("/policy-config/published")
def hr_get_policy_config_published(
    companyId: Optional[str] = Query(None, alias="companyId"),
    assignmentType: Optional[str] = Query(None, alias="assignmentType"),
    familyStatus: Optional[str] = Query(None, alias="familyStatus"),
    employeeLevel: Optional[str] = Query(None, alias="employeeLevel"),
    effectiveRowsOnly: bool = Query(False, alias="effectiveRowsOnly"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    try:
        at = validate_optional_query_assignment_type(assignmentType)
        fs = validate_optional_query_family_status(familyStatus)
        el = validate_optional_query_employee_level(employeeLevel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Graceful onboarding: an HR not yet linked to a company gets a read-only
    # empty scaffold (company_setup_required) instead of a 400 — mirrors
    # GET /policy-config. A missing precondition must degrade gracefully
    # (SKILL.md Phase 0.5); /published was the lone policy endpoint still 400ing.
    if not user.get("is_admin") and not _get_hr_company_id(user):
        return policy_config_matrix_svc.empty_onboarding_payload(
            assignment_type=at,
            family_status=fs,
            employee_level=el,
            effective_rows_only=effectiveRowsOnly,
        )
    cid = _policy_matrix_company_hr(user, companyId)
    return policy_config_matrix_svc.get_published_payload(
        cid,
        assignment_type=at,
        family_status=fs,
        employee_level=el,
        effective_rows_only=effectiveRowsOnly,
    )


@hr_policy_config_router.post("/policy-config/caps/compare")
def hr_post_policy_caps_compare(
    body: CapsCompareRequest,
    companyId: Optional[str] = Query(None, alias="companyId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _policy_matrix_company_hr(user, companyId)
    at = normalize_assignment_type(body.assignment_type)
    fs = normalize_family_status(body.family_status)
    estimates = [e.model_dump() for e in body.estimates]
    return policy_config_matrix_svc.compare_provider_estimates_to_published_caps(
        cid,
        assignment_type=at,
        family_status=fs,
        estimates=estimates,
    )


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@admin_policy_config_router.get("/policy-config")
def admin_get_policy_config(
    company_id: str = Query(..., alias="companyId"),
    assignmentType: Optional[str] = Query(None, alias="assignmentType"),
    familyStatus: Optional[str] = Query(None, alias="familyStatus"),
    employeeLevel: Optional[str] = Query(None, alias="employeeLevel"),
    effectiveRowsOnly: bool = Query(False, alias="effectiveRowsOnly"),
    user: Dict[str, Any] = Depends(require_admin),
):
    try:
        at = validate_optional_query_assignment_type(assignmentType)
        fs = validate_optional_query_family_status(familyStatus)
        el = validate_optional_query_employee_level(employeeLevel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return policy_config_matrix_svc.get_working_payload(
        company_id,
        assignment_type=at,
        family_status=fs,
        employee_level=el,
        effective_rows_only=effectiveRowsOnly,
    )


@admin_policy_config_router.post("/policy-config/draft")
def admin_post_policy_config_draft(
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    return policy_config_matrix_svc.ensure_draft(company_id, created_by=user.get("id"))


@admin_policy_config_router.put("/policy-config/draft")
def admin_put_policy_config_draft(
    body: Dict[str, Any] = Body(...),
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    try:
        return policy_config_matrix_svc.put_draft(company_id, body, changed_by=user.get("id"))
    except ValueError as e:
        raise _policy_matrix_validation_http(e)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "draft_not_found", "message": "Draft not found"})
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail={"code": "not_draft", "message": "Only draft versions can be overwritten"},
        )


@admin_policy_config_router.post("/policy-config/publish")
def admin_post_policy_config_publish(
    company_id: str = Query(..., alias="companyId"),
    body: Optional[Dict[str, Any]] = Body(default=None),
    user: Dict[str, Any] = Depends(require_admin),
):
    payload = body or {}
    try:
        return policy_config_matrix_svc.publish_draft(
            company_id,
            policy_version_id=payload.get("policy_version"),
            created_by=user.get("id"),
        )
    except ValueError as e:
        raise _policy_matrix_validation_http(e)
    except KeyError as e:
        code = e.args[0] if e.args else ""
        if code == "no_draft":
            raise HTTPException(
                status_code=409,
                detail={"code": "no_draft", "message": "No draft exists to publish"},
            )
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Draft not found"})
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail={"code": "draft_mismatch", "message": "policy_version does not match current draft"},
        )


@admin_policy_config_router.get("/policy-config/published")
def admin_get_policy_config_published(
    company_id: str = Query(..., alias="companyId"),
    assignmentType: Optional[str] = Query(None, alias="assignmentType"),
    familyStatus: Optional[str] = Query(None, alias="familyStatus"),
    employeeLevel: Optional[str] = Query(None, alias="employeeLevel"),
    effectiveRowsOnly: bool = Query(False, alias="effectiveRowsOnly"),
    user: Dict[str, Any] = Depends(require_admin),
):
    try:
        at = validate_optional_query_assignment_type(assignmentType)
        fs = validate_optional_query_family_status(familyStatus)
        el = validate_optional_query_employee_level(employeeLevel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return policy_config_matrix_svc.get_published_payload(
        company_id,
        assignment_type=at,
        family_status=fs,
        employee_level=el,
        effective_rows_only=effectiveRowsOnly,
    )


@admin_policy_config_router.get("/policy-config/versions/{version_id}")
def admin_get_policy_config_version(
    version_id: str,
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    try:
        return policy_config_matrix_svc.get_version_readonly_payload(company_id, version_id)
    except KeyError as e:
        code = e.args[0] if e.args else ""
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Version not found"})
    except PermissionError:
        raise HTTPException(
            status_code=400,
            detail={"code": "version_not_readable", "message": "Only published or archived versions can be opened from history"},
        )


@admin_policy_config_router.get("/policy-config/history")
def admin_get_policy_config_history(
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    return {"versions": policy_config_matrix_svc.history(company_id)}


@admin_policy_config_router.get("/policy-config/templates")
def admin_get_policy_config_templates(
    user: Dict[str, Any] = Depends(require_admin),
):
    from ..services.policy_config_templates import list_templates

    _ = user
    return {"templates": list_templates()}


@admin_policy_config_router.post("/policy-config/draft/apply-template")
def admin_post_policy_config_apply_template(
    body: Dict[str, Any] = Body(...),
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    template_key = str(body.get("template_key") or "").strip().lower()
    replace = bool(body.get("replace_existing_draft", False))
    if not template_key:
        raise HTTPException(
            status_code=400,
            detail={"code": "validation_error", "message": "template_key is required"},
        )
    try:
        return policy_config_matrix_svc.apply_template_to_draft(
            company_id,
            template_key=template_key,
            replace_existing_draft=replace,
            created_by=user.get("id"),
        )
    except KeyError as exc:
        code = exc.args[0] if exc.args else ""
        if isinstance(code, str) and code.startswith("unknown_template:"):
            raise HTTPException(
                status_code=404,
                detail={"code": "unknown_template", "message": "Unknown template"},
            )
        if code == "draft_has_rows":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "draft_has_rows",
                    "message": (
                        "A draft with existing rows is already in progress. "
                        "Confirm to replace it with the template, or edit the "
                        "current draft in the row drawer."
                    ),
                },
            )
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Not found"})


@admin_policy_config_router.get("/policy-config/diff")
def admin_get_policy_config_diff(
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin-scoped draft vs live snapshot. Mirrors the HR endpoint."""
    return policy_config_matrix_svc.compute_diff(company_id)


@admin_policy_config_router.post("/policy-config/draft/revert-row")
def admin_post_policy_config_revert_row(
    body: Dict[str, Any] = Body(...),
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    try:
        return policy_config_matrix_svc.revert_row_to_live(
            company_id,
            benefit_key=str(body.get("benefit_key") or "").strip(),
            targeting_signature=str(body.get("targeting_signature") or "global").strip(),
        )
    except ValueError as e:
        raise _policy_matrix_validation_http(e)
    except KeyError as e:
        code = e.args[0] if e.args else ""
        if code == "no_draft":
            raise HTTPException(
                status_code=409,
                detail={"code": "no_draft", "message": "No draft exists to revert"},
            )
        if code == "row_not_found":
            raise HTTPException(
                status_code=404,
                detail={"code": "row_not_found", "message": "Benefit row not found in live or draft"},
            )
        raise HTTPException(status_code=404, detail={"code": str(code), "message": "Not found"})


@admin_policy_config_router.post("/policy-config/caps/compare")
def admin_post_policy_caps_compare(
    body: CapsCompareRequest,
    company_id: str = Query(..., alias="companyId"),
    user: Dict[str, Any] = Depends(require_admin),
):
    at = normalize_assignment_type(body.assignment_type)
    fs = normalize_family_status(body.family_status)
    estimates = [e.model_dump() for e in body.estimates]
    return policy_config_matrix_svc.compare_provider_estimates_to_published_caps(
        company_id,
        assignment_type=at,
        family_status=fs,
        estimates=estimates,
    )


# ---------------------------------------------------------------------------
# Employee route
# ---------------------------------------------------------------------------

@employee_policy_config_router.get("/policy-config")
def employee_get_policy_config(
    assignment_id: Optional[str] = Query(None, alias="assignmentId"),
    case_id: Optional[str] = Query(None, alias="caseId"),
    assignment_type: Optional[str] = Query(None, alias="assignmentType"),
    family_status: Optional[str] = Query(None, alias="familyStatus"),
    # Section C: explicit overrides for the destination country and the
    # employee's level. Both default to None; when None, the resolver
    # treats them as missing context and Section C overrides do not
    # collapse onto the base row (overrides still surface alongside it).
    country: Optional[str] = Query(None, alias="country"),
    employee_level: Optional[str] = Query(None, alias="employeeLevel"),
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    effective = _effective_user(user, UserRole.EMPLOYEE)
    cid = _resolve_employee_company_id(effective)
    if not cid:
        raise HTTPException(status_code=400, detail="Employee missing company")
    atype, fstat = assignment_type, family_status
    assign_for_ctx: Optional[Dict[str, Any]] = None
    if assignment_id:
        a = db.get_assignment_by_id(str(assignment_id))
        if not a:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if a.get("employee_user_id") != effective.get("id"):
            raise HTTPException(status_code=403, detail="Assignment not assigned to user")
        emp = db.get_employee_by_profile_for_company(effective.get("id"), cid)
        if emp and emp.get("assignment_type") and not atype:
            atype = emp.get("assignment_type")
        coid = db.get_company_id_for_assignment_id(str(assignment_id))
        if coid and coid != cid:
            raise HTTPException(status_code=403, detail="Assignment company mismatch")
        assign_for_ctx = a
    elif case_id:
        a = db.get_assignment_by_case_id(str(case_id))
        if not a:
            raise HTTPException(status_code=404, detail="Case not found")
        if a.get("employee_user_id") != effective.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized for this case")
        emp = db.get_employee_by_profile_for_company(effective.get("id"), cid)
        if emp and emp.get("assignment_type") and not atype:
            atype = emp.get("assignment_type")
        coid = db.get_company_id_for_assignment_id(str(a.get("id")))
        if coid and coid != cid:
            raise HTTPException(status_code=403, detail="Case company mismatch")
        assign_for_ctx = a
    else:
        fa = db.get_assignment_for_employee(effective.get("id"), request_id=None)
        if fa:
            coid = db.get_company_id_for_assignment_id(str(fa.get("id")))
            if not coid or coid == cid:
                assign_for_ctx = fa

    # Resolve country + employee_level from case context when not passed
    # in. Country lives on the relocation case (host_country); employee
    # level is on the employee profile.
    resolved_country = country
    resolved_level = employee_level
    if assign_for_ctx and (not atype or not fstat or not resolved_country or not resolved_level):
        from ..services.policy_resolution import extract_resolution_context

        aid = str(assign_for_ctx.get("id") or "").strip()
        case_id_inner = assign_for_ctx.get("case_id")
        case_row = db.get_relocation_case(case_id_inner) if case_id_inner else None
        prof_j = None
        if case_row and case_row.get("profile_json"):
            try:
                raw_pj = case_row["profile_json"]
                prof_j = json.loads(raw_pj) if isinstance(raw_pj, str) else raw_pj
            except Exception:
                prof_j = None
        emp_pf = None
        if aid:
            try:
                emp_pf = db.get_employee_profile(aid)
            except Exception:
                emp_pf = None
        ctx = extract_resolution_context(assign_for_ctx, case_row, prof_j, emp_pf)
        if not atype:
            atype = ctx.get("assignment_type")
        if not fstat:
            fstat = ctx.get("family_status")
        # Section C: pull country from host_country on the case, level
        # from the employee profile band when not passed explicitly.
        # readiness_service already has the country-name → ISO2 mapper
        # (Germany → DE, Singapore → SG, etc.) — reuse it instead of
        # duplicating the alias table.
        if not resolved_country and case_row:
            from ...readiness_service import normalize_destination_key
            host = case_row.get("host_country") or case_row.get("destination_country")
            if host:
                resolved_country = normalize_destination_key(str(host))
        if not resolved_level and emp_pf:
            band = emp_pf.get("employee_level") or emp_pf.get("band")
            if band:
                resolved_level = str(band).strip().lower()

    return policy_config_matrix_svc.employee_grouped_payload(
        cid,
        assignment_type=atype,
        family_status=fstat,
        country=resolved_country,
        employee_level=resolved_level,
    )


# ---------------------------------------------------------------------------
# Public / cross-role caps route
# ---------------------------------------------------------------------------

@public_policy_config_router.get("/policy-config/caps")
def get_policy_config_caps(
    company_id: Optional[str] = Query(None, alias="companyId"),
    assignment_id: Optional[str] = Query(None, alias="assignmentId"),
    case_id: Optional[str] = Query(None, alias="caseId"),
    assignment_type: Optional[str] = Query(None, alias="assignmentType"),
    family_status: Optional[str] = Query(None, alias="familyStatus"),
    benefit_keys: Optional[List[str]] = Query(None, alias="benefitKeys"),
    service_module: Optional[str] = Query(None, alias="serviceModule"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    cid = _policy_matrix_resolve_company_caps(user, company_id, assignment_id, case_id)
    keys = benefit_keys if benefit_keys else None
    at = normalize_assignment_type(assignment_type)
    fs = normalize_family_status(family_status)
    return policy_config_matrix_svc.caps_payload(
        cid,
        assignment_type=at,
        family_status=fs,
        benefit_keys=keys,
        service_module=service_module,
    )
