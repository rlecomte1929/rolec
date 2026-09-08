"""
W2-3 — HR escalation endpoints, mounted on the prod app (backend.main:app) so the
test also proves dual-registration. Service is monkeypatched; auth overridden.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.services import case_escalation_service

_HR = {"id": "hr-1", "role": "HR", "company": "co-1", "is_admin": False, "auth_uuid": None}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(case_escalation_service, "create_escalation",
                        lambda **kw: {"id": "esc-1", "status": "open", **kw})
    monkeypatch.setattr(case_escalation_service, "list_escalations",
                        lambda case_id, company_id: [{"id": "esc-1", "case_id": case_id, "status": "open"}])
    monkeypatch.setattr(case_escalation_service, "resolve_escalation",
                        lambda eid, co, **kw: {"id": eid, "status": "resolved", **kw})
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _HR
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: "co-1"
    yield TestClient(app)
    app.dependency_overrides.pop(auth_deps.get_current_user, None)
    app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_routes_registered_in_prod_app():
    paths = {r.path for r in app.routes}
    assert "/api/hr/cases/{case_id}/escalate" in paths
    assert "/api/hr/cases/{case_id}/escalations" in paths
    assert "/api/hr/escalations/{escalation_id}/resolve" in paths


def test_escalate_create(client):
    r = client.post("/api/hr/cases/case-9/escalate", json={"reason": "Need legal review", "kind": "legal"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "open" and body["company_id"] == "co-1" and body["case_id"] == "case-9"


def test_list(client):
    r = client.get("/api/hr/cases/case-9/escalations")
    assert r.status_code == 200
    assert r.json()["escalations"][0]["id"] == "esc-1"


def test_resolve(client):
    r = client.post("/api/hr/escalations/esc-1/resolve", json={"resolution_note": "handled"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


def test_resolve_not_found(client, monkeypatch):
    monkeypatch.setattr(case_escalation_service, "resolve_escalation", lambda eid, co, **kw: None)
    r = client.post("/api/hr/escalations/ghost/resolve", json={"resolution_note": "x"})
    assert r.status_code == 404


# ── AIQ-1136: HR case reassignment ─────────────────────────────────────────
from backend.app.routers import hr_case_escalation  # noqa: E402


@pytest.fixture()
def reassign_client(monkeypatch):
    """HR (co-1) with a 2-person team: prof-a, prof-b."""
    monkeypatch.setattr(
        hr_case_escalation.db, "list_hr_users_with_profiles",
        lambda cid: [
            {"profile_id": "prof-a", "name": "Alice", "email": "a@co-1.com"},
            {"profile_id": "prof-b", "name": "Bob", "email": "b@co-1.com"},
        ] if cid == "co-1" else [],
    )
    calls = []
    monkeypatch.setattr(
        hr_case_escalation.db, "admin_reassign_hr_owner",
        lambda aid, hr: calls.append((aid, hr)),
    )
    app.dependency_overrides[auth_deps.get_current_user] = lambda: _HR
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: "co-1"
    client = TestClient(app)
    client._reassign_calls = calls  # type: ignore[attr-defined]
    yield client
    app.dependency_overrides.pop(auth_deps.get_current_user, None)
    app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_reassign_routes_registered():
    paths = {r.path for r in app.routes}
    assert "/api/hr/team" in paths
    assert "/api/hr/cases/{case_id}/reassign-hr-owner" in paths


def test_team_list(reassign_client):
    r = reassign_client.get("/api/hr/team")
    assert r.status_code == 200
    members = r.json()["members"]
    assert {m["profile_id"] for m in members} == {"prof-a", "prof-b"}


def test_reassign_success(reassign_client, monkeypatch):
    monkeypatch.setattr(hr_case_escalation, "_assignment_company_id", lambda aid: "co-1")
    r = reassign_client.patch(
        "/api/hr/cases/case-9/reassign-hr-owner",
        json={"hr_user_id": "prof-b", "reason": "Going on leave"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert reassign_client._reassign_calls == [("case-9", "prof-b")]


def test_reassign_rejects_case_in_other_company(reassign_client, monkeypatch):
    # The case belongs to a different company → 404, and no reassign happens.
    monkeypatch.setattr(hr_case_escalation, "_assignment_company_id", lambda aid: "co-2")
    r = reassign_client.patch(
        "/api/hr/cases/case-9/reassign-hr-owner",
        json={"hr_user_id": "prof-b", "reason": "x"},
    )
    assert r.status_code == 404
    assert reassign_client._reassign_calls == []


def test_reassign_rejects_target_outside_company(reassign_client, monkeypatch):
    # Target HR is not in the caller's team → 400, and no reassign happens.
    monkeypatch.setattr(hr_case_escalation, "_assignment_company_id", lambda aid: "co-1")
    r = reassign_client.patch(
        "/api/hr/cases/case-9/reassign-hr-owner",
        json={"hr_user_id": "prof-zzz", "reason": "x"},
    )
    assert r.status_code == 400
    assert reassign_client._reassign_calls == []
