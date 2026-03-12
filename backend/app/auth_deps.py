"""Shared auth dependencies for routers (avoids circular imports with main)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request

from ..database import db
from ..schemas import UserRole


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


def require_hr_or_employee(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Allow HR or Employee. Admin passes as HR."""
    r = user.get("role")
    if r == UserRole.ADMIN.value:
        return user
    if r in (UserRole.HR.value, UserRole.EMPLOYEE.value):
        return user
    raise HTTPException(status_code=403, detail="HR or Employee only")


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


def require_assignment_visibility(assignment_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user can access assignment; return assignment."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    visible = (is_employee and emp_id == effective["id"]) or (
        is_hr and (effective.get("is_admin") or hr_id == effective["id"])
    )
    if not visible:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    return assignment
