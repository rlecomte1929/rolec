"""GET /api/hr/setup-status — read-only HR workspace setup progress.

Mounted on the prod app (``backend.main:app``) so the suite also proves the
dual-registration hard gate. Auth deps are overridden; the four field-derivation
helpers are monkeypatched with a per-company data map so the tests exercise the
route wiring, the next_step ordering, and — critically — that the company scope
comes ONLY from auth (``get_org_id_for_hr_user``), never from a param/body, so
one HR user can never see another company's status.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.routers import setup_assistant

# Per-company synthetic workspace state, keyed by company_id.
_DATA = {
    # Fresh self-serve signup: no profile, no policy, no cases, no employees.
    "co-fresh": {"profile": False, "policy": False, "cases": (0, None), "employees": 0},
    # Advanced: profile + policy done, one case, no employee invited yet.
    "co-advanced": {"profile": True, "policy": True, "cases": (1, "case-abc"), "employees": 0},
    # A DIFFERENT company whose data must never leak to another caller.
    "co-other": {"profile": True, "policy": True, "cases": (7, "case-other"), "employees": 4},
}

_HR = {"id": "hr-1", "role": "HR", "company": None, "is_admin": False, "auth_uuid": None}


@pytest.fixture(autouse=True)
def _patch_helpers(monkeypatch):
    """Route the four helpers through the per-company map so each derived field
    is a pure function of the company_id the endpoint resolved from auth."""
    monkeypatch.setattr(setup_assistant, "_company_profile_complete",
                        lambda cid: _DATA.get(cid, {}).get("profile", False))
    monkeypatch.setattr(setup_assistant, "_policy_published",
                        lambda cid: _DATA.get(cid, {}).get("policy", False))
    monkeypatch.setattr(setup_assistant, "_cases",
                        lambda cid: _DATA.get(cid, {}).get("cases", (0, None)))
    monkeypatch.setattr(setup_assistant, "_employees_invited",
                        lambda cid: _DATA.get(cid, {}).get("employees", 0))
    yield


def _client_for(company_id: str) -> TestClient:
    """A TestClient whose auth resolves to ``company_id`` (scope from auth only)."""
    app.dependency_overrides[auth_deps.require_admin_or_hr] = lambda: _HR
    app.dependency_overrides[auth_deps.get_org_id_for_hr_user] = lambda: company_id
    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.pop(auth_deps.require_admin_or_hr, None)
    app.dependency_overrides.pop(auth_deps.get_org_id_for_hr_user, None)


def test_route_registered_in_prod_app():
    assert "/api/hr/setup-status" in {r.path for r in app.routes}


def test_fresh_company_next_step_is_company_profile():
    try:
        r = _client_for("co-fresh").get("/api/hr/setup-status")
        assert r.status_code == 200
        body = r.json()
        assert body["company_profile_complete"] is False
        assert body["policy_published"] is False
        assert body["cases_count"] == 0
        assert body["employees_invited"] == 0
        assert body["first_case_id"] is None
        assert body["next_step"] == {
            "label": "Complete your company profile",
            "route": "/hr/company-profile",
        }
    finally:
        _clear_overrides()


def test_advanced_company_counts_and_next_step():
    try:
        r = _client_for("co-advanced").get("/api/hr/setup-status")
        assert r.status_code == 200
        body = r.json()
        assert body["company_profile_complete"] is True
        assert body["policy_published"] is True
        assert body["cases_count"] == 1
        assert body["first_case_id"] == "case-abc"
        assert body["employees_invited"] == 0
        # Profile + policy + a case done → the first incomplete stage is invite.
        assert body["next_step"]["label"] == "Invite your first employee"
        assert body["next_step"]["route"] == "/hr/command-center"
    finally:
        _clear_overrides()


def test_company_scoping_no_cross_company_leak():
    """Each caller sees ONLY their own company's status; co-other's data
    (7 cases, 4 employees) never appears for the co-advanced caller, and a
    ``?company_id=`` query param cannot override the auth-derived scope."""
    try:
        advanced = _client_for("co-advanced").get(
            "/api/hr/setup-status?company_id=co-other"
        )
        assert advanced.status_code == 200
        b1 = advanced.json()
        # Param-injection ignored: still co-advanced's numbers, not co-other's.
        assert b1["cases_count"] == 1 and b1["first_case_id"] == "case-abc"
        assert b1["employees_invited"] == 0
    finally:
        _clear_overrides()

    try:
        other = _client_for("co-other").get("/api/hr/setup-status")
        assert other.status_code == 200
        b2 = other.json()
        assert b2["cases_count"] == 7 and b2["first_case_id"] == "case-other"
        assert b2["employees_invited"] == 4
        # All done → the "set up" terminal step.
        assert b2["next_step"]["label"] == "You're all set up"
    finally:
        _clear_overrides()


def test_unauthenticated_is_rejected():
    _clear_overrides()  # no auth override → real require_admin_or_hr runs
    r = TestClient(app).get("/api/hr/setup-status")
    assert r.status_code in (401, 403)
