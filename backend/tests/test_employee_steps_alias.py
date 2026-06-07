"""POST /api/employee/steps/4 alias (B11 / AIQ-421).

Verifies the employee wizard Step-4 endpoint is registered and delegates to the
canonical quote-request handler. The canonical handler is stubbed so the test
needs no database — we only assert wiring + argument pass-through.
"""
import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.app.routers import employee_steps  # noqa: E402


def _fake_user():
    return {"id": "emp-1", "company": "co-1"}


def test_step4_route_registered():
    assert "/api/employee/steps/4" in {r.path for r in app.routes}


def test_step4_delegates_to_quote_request(monkeypatch):
    captured = {}

    def _stub(case_id, body, user):
        captured["case_id"] = case_id
        captured["services"] = body.services
        captured["notes"] = body.notes
        captured["user"] = user
        return {"id": "qr-1", "status": "pending"}

    monkeypatch.setattr(employee_steps, "create_case_quote_request", _stub)
    app.dependency_overrides[get_current_user] = _fake_user
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/employee/steps/4",
            json={"case_id": "case-9", "services": ["Housing"], "notes": "hi"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending"
        assert captured["case_id"] == "case-9"
        assert captured["services"] == ["Housing"]
        assert captured["user"] == {"id": "emp-1", "company": "co-1"}
    finally:
        app.dependency_overrides.pop(get_current_user, None)
