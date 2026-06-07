"""Shared auth dependencies for routers (avoids circular imports with main)."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request

from ..database import db
from ..schemas import UserRole


def _resolve_auth_uuid(user: Dict[str, Any]) -> Optional[str]:
    """Resolve the caller to a canonical Supabase auth UUID (AUTH-ID-1).

    ReloPass runs a hybrid auth model: a legacy session token yields a non-UUID
    text ``id`` (e.g. ``seed-emp-testingapril``), while immigration/case tables
    key on uuid columns. Binding the text id to such a column makes Postgres
    raise ``invalid input syntax for type uuid`` and the endpoint 500s. We map
    the caller to their UUID here so downstream handlers bind a real UUID — or
    ``None`` (→ no match, which degrades safely) instead of crashing.

    - UUID-native id (Supabase-native account) → that id, unchanged.
    - Legacy text id with a matching profile    → ``profiles.id`` (the auth
      UUID), bridged by email (``profiles`` is keyed by the auth uuid).
    - Otherwise                                 → ``None``.
    """
    raw = user.get("id")
    try:
        return str(uuid.UUID(str(raw)))
    except (ValueError, AttributeError, TypeError):
        pass
    email = (user.get("email") or "").strip().lower()
    if email:
        profile = db.get_profile_by_email(email)
        prof_id = (profile or {}).get("id")
        if prof_id:
            try:
                return str(uuid.UUID(str(prof_id)))
            except (ValueError, AttributeError, TypeError):
                return None
    return None


def _is_admin_user(user: Dict[str, Any]) -> bool:
    role = (user.get("role") or "").upper()
    if role == UserRole.ADMIN.value:
        return True
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() == UserRole.ADMIN.value:
        return True
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return True
    return False


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Extract user from authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    db.ensure_profile_record(
        user_id=user["id"],
        email=user.get("email"),
        role=user.get("role", UserRole.EMPLOYEE.value),
        full_name=user.get("name"),
        company_id=user.get("company"),
    )
    if _is_admin_user(user):
        user["role"] = UserRole.ADMIN.value
        user["is_admin"] = True
    else:
        user["is_admin"] = False
    # Canonical Supabase auth UUID for uuid-keyed immigration/case queries
    # (AUTH-ID-1). None when a legacy id can't be mapped — callers degrade
    # gracefully rather than 500 on a uuid cast.
    user["auth_uuid"] = _resolve_auth_uuid(user)
    if request is not None:
        try:
            request.state.user_id = user.get("id")
        except Exception:
            pass
    session = db.get_admin_session(token)
    if session and session.get("target_user_id"):
        user["impersonation"] = {
            "target_user_id": session.get("target_user_id"),
            "mode": session.get("mode"),
        }
    return user


def require_role(role: UserRole):
    """Return a FastAPI dependency that requires *role*. ADMIN users pass all role checks."""
    def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = user.get("role")
        if user_role == UserRole.ADMIN.value:
            return user
        if user_role != role.value:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency


def require_hr_or_employee(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Allow HR or Employee. Admin passes as HR."""
    r = user.get("role")
    if r == UserRole.ADMIN.value:
        return user
    if r in (UserRole.HR.value, UserRole.EMPLOYEE.value):
        return user
    raise HTTPException(status_code=403, detail="HR or Employee only")


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Admin only."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_admin_or_hr(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Admin or HR. Used for read-only access to suppliers (HR picks from approved list)."""
    r = user.get("role")
    if r == UserRole.ADMIN.value or user.get("is_admin"):
        return user
    if r == UserRole.HR.value:
        return user
    raise HTTPException(status_code=403, detail="Admin or HR only")


def _effective_user(user: Dict[str, Any], expected_role: Optional[UserRole] = None) -> Dict[str, Any]:
    imp = user.get("impersonation")
    if not imp:
        return user
    target = db.get_user_by_id(imp.get("target_user_id"))
    if not target:
        return user
    if expected_role and target.get("role") != expected_role.value:
        return user
    return target


def get_org_id_for_hr_user(user: Dict[str, Any] = Depends(require_admin_or_hr)) -> str:
    """Return the company_id for the current HR / Admin user.

    Resolution order (AIQ-862): ``db.get_hr_company_id`` first — it is the only
    path that works for LEGACY text HR ids (e.g. ``seed-hr-testingapril``),
    resolving via the ``hr_users`` table (and ``profiles`` internally). A
    profiles-only lookup returns ``None`` for non-UUID legacy ids, which used to
    leave ``org_id=""`` and silently mis-scope every HR endpoint that depends on
    this. ``user.get("company")`` (the session claim) is the final fallback.
    """
    uid = user.get("id")
    company_id = (db.get_hr_company_id(uid) if uid else None) or user.get("company") or ""
    return company_id


def require_vendor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require user to be a vendor. Returns user dict with vendor_id added. 403 if not a vendor."""
    vendor_id = db.get_vendor_for_user(user.get("id"))
    if not vendor_id:
        raise HTTPException(status_code=403, detail="Vendor access only")
    user = dict(user)
    user["vendor_id"] = vendor_id
    return user


def require_assignment_visibility(assignment_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user can access assignment; return assignment.
    HR: allowed if admin, or owns assignment (hr_user_id), or assignment belongs to their company.
    """
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    if is_employee:
        visible = emp_id == effective["id"]
    else:
        visible = effective.get("is_admin") or hr_id == effective["id"]
        if not visible and effective.get("role") == UserRole.HR.value:
            hr_company = db.get_hr_company_id(effective["id"])
            if hr_company and db.assignment_belongs_to_company(assignment_id, hr_company):
                visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    return assignment


def require_case_access(case_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user can access a case by its case_id; return the assignment row.

    Employees: must own the case (assignment.employee_user_id == caller.id).
    HR / Admin: sufficient to belong to the same company as the case.

    Raises 404 if the case has no assignment, 403 if the caller lacks access.
    Used by case-scoped routers (services_state, exception_requests) that
    previously only checked organization_id — insufficient for employees.
    """
    assignment = db.get_assignment_by_case_id(case_id)
    if not assignment:
        # Case might exist without an assignment for HR-wizard flows; in that
        # case employee access is implicitly denied (no assignment to verify).
        # HR can still proceed if the case belongs to their company.
        role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
        effective = _effective_user(user, role)
        is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
        if not is_hr:
            raise HTTPException(status_code=404, detail="Case not found")
        return {}  # No assignment row — HR path with no assignment yet
    return require_assignment_visibility(assignment["id"], user)
