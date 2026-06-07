"""Bare-path HR vendor-widget endpoints (B16 / AIQ-422).

The vendor-curation widget + E2E (T11_WIDGET) call the endpoints at
/api/hr/vendor-assignments/pending and /api/hr/employees/waiting (no /catalog).
These assert the routes are registered on the prod app and return the
{count: ...} contract with HR auth. (No demand data is seeded; the handlers
return count=0, which still proves wiring + auth + shape.)
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.app.auth_deps import require_admin_or_hr  # noqa: E402


def _fake_hr():
    return {"id": "hr-1", "role": "HR"}


def test_bare_paths_registered():
    paths = {r.path for r in app.routes}
    assert "/api/hr/vendor-assignments/pending" in paths
    assert "/api/hr/employees/waiting" in paths


def test_endpoints_return_200_with_count_contract():
    app.dependency_overrides[require_admin_or_hr] = _fake_hr
    try:
        client = TestClient(app)
        r1 = client.get("/api/hr/vendor-assignments/pending")
        assert r1.status_code == 200, r1.text
        assert "count" in r1.json()

        r2 = client.get("/api/hr/employees/waiting")
        assert r2.status_code == 200, r2.text
        assert "count" in r2.json()
    finally:
        app.dependency_overrides.pop(require_admin_or_hr, None)
