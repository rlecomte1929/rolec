"""AIQ-1414 Phase 3 — app-mounted tests for the coordinator endpoint.

Mounts the PROD app (``backend.main:app``) so this also proves dual-registration. The
LLM/agent, case-access check, and auth are overridden/monkeypatched so no DB or network
is touched.
"""

import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import require_hr_or_employee
from backend.app.routers import coordinator as coord

_URL = "/api/cases/c-1/coordinator/respond"
_FAKE_USER = {"id": "emp-1", "role": "employee", "roles": ["employee"], "is_admin": False}


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


def _setup(monkeypatch, *, enabled=True, assignment=None, respond_result=None):
    if assignment is None:
        assignment = {"employee_user_id": "emp-1", "id": "asg-1"}
    if respond_result is None:
        respond_result = {"answer": "Here's your next step.", "model": "claude-sonnet-4-6", "case_id": "c-1"}
    app.dependency_overrides[require_hr_or_employee] = lambda: _FAKE_USER
    monkeypatch.setattr(coord, "coordinator_enabled", lambda: enabled)
    monkeypatch.setattr(coord, "require_case_access", lambda case_id, user: assignment)
    calls = {}

    def _fake_respond(case_id, message, *, employee_id=None):
        calls.update(case_id=case_id, message=message, employee_id=employee_id)
        return respond_result

    monkeypatch.setattr(coord.coordinator_agent, "respond", _fake_respond)
    return calls


def test_route_is_dual_registered_on_prod_app():
    paths = {r.path for r in app.routes}
    assert "/api/cases/{case_id}/coordinator/respond" in paths


def test_flag_off_returns_404_and_never_calls_agent(monkeypatch):
    calls = _setup(monkeypatch, enabled=False)
    r = TestClient(app).post(_URL, json={"message": "hello"})
    assert r.status_code == 404
    assert calls == {}  # agent never invoked when the feature is disabled


def test_flag_on_returns_answer_and_passes_employee_id(monkeypatch):
    calls = _setup(monkeypatch, enabled=True,
                   assignment={"employee_user_id": "emp-1", "id": "asg-1"})
    r = TestClient(app).post(_URL, json={"message": "what's next on my visa?"})
    assert r.status_code == 200
    assert r.json()["answer"] == "Here's your next step."
    assert r.json()["model"] == "claude-sonnet-4-6"
    # the endpoint threaded the assignment's employee id into the agent
    assert calls["employee_id"] == "emp-1"
    assert calls["message"] == "what's next on my visa?"


def test_empty_message_is_rejected(monkeypatch):
    _setup(monkeypatch, enabled=True)
    r = TestClient(app).post(_URL, json={"message": ""})
    assert r.status_code == 422  # min_length=1


# ── GET session (Phase 4) ──────────────────────────────────────────────────────

_SESSION_URL = "/api/cases/c-1/coordinator/session"


def _setup_get(monkeypatch, *, enabled=True, session=None):
    app.dependency_overrides[require_hr_or_employee] = lambda: _FAKE_USER
    monkeypatch.setattr(coord, "coordinator_enabled", lambda: enabled)
    monkeypatch.setattr(coord, "require_case_access", lambda case_id, user: {"employee_user_id": "emp-1"})
    monkeypatch.setattr(coord.store, "get", lambda case_id: session)


def test_get_session_is_dual_registered_on_prod_app():
    assert "/api/cases/{case_id}/coordinator/session" in {r.path for r in app.routes}


def test_get_session_flag_off_404(monkeypatch):
    _setup_get(monkeypatch, enabled=False)
    assert TestClient(app).get(_SESSION_URL).status_code == 404


def test_get_session_returns_persisted_turns(monkeypatch):
    _setup_get(monkeypatch, session={
        "rolling_summary": "moving FR→DE",
        "recent_turns": [{"user": "hi", "assistant": "hello"}],
        "model": "claude-sonnet-4-6", "status": "active",
    })
    r = TestClient(app).get(_SESSION_URL)
    assert r.status_code == 200
    body = r.json()
    assert body["case_id"] == "c-1"
    assert body["rolling_summary"] == "moving FR→DE"
    assert body["recent_turns"] == [{"user": "hi", "assistant": "hello"}]


def test_get_session_empty_when_none(monkeypatch):
    _setup_get(monkeypatch, session=None)
    r = TestClient(app).get(_SESSION_URL)
    assert r.status_code == 200
    assert r.json()["recent_turns"] == []
    assert r.json()["status"] == "none"
