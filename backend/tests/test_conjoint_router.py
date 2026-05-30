"""
Tests for the conjoint study API — Parker Step H.

Drives the router over an in-memory SQLite schema (the modular SessionLocal is
monkeypatched), exercising the real auth dependencies: HR/admin gating + company-scope
check on create/fit/results, respondent submission + idempotency, the fit endpoint
persisting a results row, and the guarantee that respondent ids never appear in results.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import conjoint  # noqa: E402
from backend.app.auth_deps import get_current_user, get_org_id_for_hr_user  # noqa: E402


_SCHEMA = [
    """
    CREATE TABLE conjoint_studies (
      id TEXT PRIMARY KEY, company_id TEXT, name TEXT, status TEXT,
      attributes_json TEXT, n_responses_target INTEGER,
      opened_at TEXT, closed_at TEXT, created_at TEXT
    )
    """,
    """
    CREATE TABLE conjoint_responses (
      id TEXT PRIMARY KEY, study_id TEXT, respondent_user_id TEXT,
      choice_set_json TEXT, choice_set_hash TEXT, chosen_index INTEGER, responded_at TEXT
    )
    """,
    """
    CREATE TABLE conjoint_results (
      id TEXT PRIMARY KEY, study_id TEXT, part_worths_json TEXT,
      fit_quality_json TEXT, computed_at TEXT
    )
    """,
]

ATTRS = {
    "housing": ["none", "basic", "premium"],
    "tax": ["none", "full"],
}


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(conjoint, "SessionLocal", Session)
    return Session


def _app(*, user, caller_company="acme") -> FastAPI:
    app = FastAPI()
    app.include_router(conjoint.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_org_id_for_hr_user] = lambda: caller_company
    return app


_HR = {"id": "hr-1", "role": "HR", "is_admin": False}
_EMP = {"id": "emp-1", "role": "EMPLOYEE", "is_admin": False}


def test_non_hr_cannot_create_study(session_factory):
    client = TestClient(_app(user=_EMP))
    r = client.post("/api/hr/acme/conjoint/studies", json={"attributes": ATTRS})
    assert r.status_code == 403


def test_wrong_company_is_rejected(session_factory):
    client = TestClient(_app(user=_HR, caller_company="acme"))
    r = client.post("/api/hr/other-co/conjoint/studies", json={"attributes": ATTRS})
    assert r.status_code == 403


def test_create_requires_multi_level_attributes(session_factory):
    client = TestClient(_app(user=_HR))
    r = client.post(
        "/api/hr/acme/conjoint/studies",
        json={"attributes": {"housing": ["only-one"]}},
    )
    assert r.status_code == 422


def _create_study(session_factory) -> str:
    client = TestClient(_app(user=_HR))
    r = client.post(
        "/api/hr/acme/conjoint/studies",
        json={"name": "Q3 benefits", "attributes": ATTRS, "n_responses_target": 50},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_cross_company_study_access_404(session_factory):
    study_id = _create_study(session_factory)
    # Admin bypasses the company-scope check but the study still isn't in 'other-co'.
    admin_app = _app(user={"id": "a", "role": "admin", "is_admin": True}, caller_company="")
    client = TestClient(admin_app)
    r = client.get(f"/api/hr/other-co/conjoint/studies/{study_id}/results")
    assert r.status_code == 404


def test_results_404_before_fit(session_factory):
    study_id = _create_study(session_factory)
    client = TestClient(_app(user=_HR))
    r = client.get(f"/api/hr/acme/conjoint/studies/{study_id}/results")
    assert r.status_code == 404


def test_response_submission_is_idempotent(session_factory):
    study_id = _create_study(session_factory)
    emp = TestClient(_app(user=_EMP))

    nxt = emp.get(f"/api/hr/acme/conjoint/studies/{study_id}/next-choice-set").json()
    assert nxt["done"] is False
    alts = nxt["choice_set"]["alternatives"]

    body = {"alternatives": alts, "chosen_index": 0}
    r1 = emp.post(f"/api/hr/acme/conjoint/studies/{study_id}/responses", json=body)
    r2 = emp.post(f"/api/hr/acme/conjoint/studies/{study_id}/responses", json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["deduplicated"] is False
    assert r2.json()["deduplicated"] is True

    # Exactly one persisted row for that respondent + choice set.
    Session = session_factory
    s = Session()
    try:
        n = s.execute(text("SELECT COUNT(*) FROM conjoint_responses")).scalar()
    finally:
        s.close()
    assert n == 1


def test_fit_persists_results_without_leaking_respondents(session_factory):
    study_id = _create_study(session_factory)
    emp = TestClient(_app(user=_EMP))

    # Answer every choice set this respondent is served.
    for _ in range(conjoint.conjoint_repo.CHOICE_SETS_PER_STUDY + 2):
        nxt = emp.get(f"/api/hr/acme/conjoint/studies/{study_id}/next-choice-set").json()
        if nxt["done"]:
            break
        alts = nxt["choice_set"]["alternatives"]
        emp.post(
            f"/api/hr/acme/conjoint/studies/{study_id}/responses",
            json={"alternatives": alts, "chosen_index": 0},
        )

    hr = TestClient(_app(user=_HR))
    fit = hr.post(f"/api/hr/acme/conjoint/studies/{study_id}/fit")
    assert fit.status_code == 200, fit.text

    res = hr.get(f"/api/hr/acme/conjoint/studies/{study_id}/results")
    assert res.status_code == 200
    body = res.json()
    assert "part_worths" in body and "fit_quality" in body
    assert set(body["part_worths"].keys()) == set(ATTRS.keys())
    # Respondent identifiers must never surface in HR-facing results.
    assert "respondent_user_id" not in res.text
