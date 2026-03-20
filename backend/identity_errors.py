"""
Structured API error codes for identity, signup, and assignment claim flows.

Use dict-shaped FastAPI/Starlette `detail` so clients can branch without parsing prose.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class IdentityErrorCode(str, Enum):
    AUTH_USERNAME_TAKEN = "AUTH_USERNAME_TAKEN"
    AUTH_EMAIL_TAKEN = "AUTH_EMAIL_TAKEN"
    AUTH_USER_CREATE_FAILED = "AUTH_USER_CREATE_FAILED"
    AUTH_IDENTIFIER_REQUIRED = "AUTH_IDENTIFIER_REQUIRED"
    AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"
    AUTH_NO_PASSWORD = "AUTH_NO_PASSWORD"
    AUTH_WRONG_PASSWORD = "AUTH_WRONG_PASSWORD"

    CLAIM_MISSING_ACCOUNT_IDENTIFIER = "CLAIM_MISSING_ACCOUNT_IDENTIFIER"
    CLAIM_MISSING_REQUEST_IDENTIFIER = "CLAIM_MISSING_REQUEST_IDENTIFIER"
    CLAIM_ACCOUNT_IDENTIFIER_MISMATCH = "CLAIM_ACCOUNT_IDENTIFIER_MISMATCH"
    CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH = "CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH"
    CLAIM_INVITE_REVOKED = "CLAIM_INVITE_REVOKED"
    CLAIM_ASSIGNMENT_ALREADY_CLAIMED = "CLAIM_ASSIGNMENT_ALREADY_CLAIMED"


def err_detail(code: IdentityErrorCode, message: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"code": code.value, "message": message}
    out.update(extra)
    return out
