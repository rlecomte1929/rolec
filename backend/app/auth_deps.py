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
