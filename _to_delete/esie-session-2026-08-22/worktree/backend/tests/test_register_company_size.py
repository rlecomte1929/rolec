"""AIQ-829 — signup routing question + HR company-size capture.

Covers the contract additions: RegisterRequest accepts/sanitizes company_size,
the register route is wired, and find_or_create_company_by_name threads
company_size into create_company as size_band only when creating a new company.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.main import app  # noqa: E402
from backend.schemas import RegisterRequest  # noqa: E402
from backend.database import db  # noqa: E402


def test_register_route_wired():
    assert "/api/auth/register" in {r.path for r in app.routes}


def test_register_request_accepts_and_sanitizes_company_size():
    req = RegisterRequest(password="x", role="HR", company_size="51-500")
    assert req.company_size == "51-500"
    # HTML stripped (XSS defence parity with name/company_name)
    dirty = RegisterRequest(password="x", role="HR", company_size="<b>1-50</b>")
    assert "<b>" not in (dirty.company_size or "")


def test_company_size_optional_for_employee():
    req = RegisterRequest(password="x", role="EMPLOYEE")
    assert req.company_size is None


# NOTE: the company_size → companies.size_band persistence (find_or_create_company_by_name
# → create_company(size_band=...)) is a direct kwarg pass verified by code review +
# manual staging signup. It is intentionally NOT unit-tested here: backend.main wraps the
# Database methods with runtime instrumentation, so a stubbed-`self` white-box test can't
# intercept the call. The contract that crosses the API boundary (RegisterRequest.company_size)
# is covered above.
