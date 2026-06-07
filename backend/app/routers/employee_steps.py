"""Employee wizard step endpoints (B11 / AIQ-421).

Thin, discoverable aliases for employee relocation-wizard steps. Each step
delegates to its canonical handler so there is no logic duplication.

Step 4 (WZ4) = submit a service quote request, implemented canonically at
POST /api/cases/{case_id}/quote-request (cases_write.create_case_quote_request).
The wizard step is exposed here as POST /api/employee/steps/4 so the step is
discoverable at a stable, step-numbered URL.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth_deps import get_current_user
from .cases_write import _QuoteRequestBody, create_case_quote_request

router = APIRouter(prefix="/api/employee/steps", tags=["employee-steps"])


class _Step4Body(_QuoteRequestBody):
    """Step-4 body = the quote-request body plus the target case_id."""

    case_id: str


@router.post("/4", status_code=201)
def employee_step4_quote_request(
    body: _Step4Body,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """WZ4: submit a service quote request for the employee's case.

    Delegates to the canonical quote-request handler (cases_write) so the
    behaviour, auth, and persistence stay identical to
    POST /api/cases/{case_id}/quote-request.
    """
    return create_case_quote_request(case_id=body.case_id, body=body, user=user)
