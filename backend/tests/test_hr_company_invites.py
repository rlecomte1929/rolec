"""
[AIQ-2094 ST2] An HR user raises a colleague invite into their OWN company.

The property under test is the one AIQ-2090 (PR #1989) had to remove: the tenant an
invite grants must be derived from the CALLER, never from anything the caller asserts.
`test_a_body_supplied_company_id_is_ignored` is the load-bearing one — it is the direct
regression guard for that bug in this new surface, and it was written first and shown
failing against a body-trusting implementation before the router was written.

The table under test is `hr_company_invites`, created by 20261126000000 and applied to
production on 2026-08-30. _SCHEMA below mirrors it in SQLite: uuid -> TEXT, timestamptz
-> TEXT. The partial unique index is reproduced verbatim because SQLite supports both
partial and expression indexes, so the 409-not-500 duplicate path is genuinely exercised
here rather than mocked away.
"""
from __future__ import annotations

import os

# backend.main attaches the query-counter SQLAlchemy listener at import time, which blows
# up against conftest's mocked engine. Same opt-out the other app-mounted tests use.
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.routers import hr_company_invites
from backend.app.auth_deps import require_admin_or_hr

COMPANY_A = "11111111-1111-4111-8111-111111111111"
COMPANY_B = "22222222-2222-4222-8222-222222222222"
HR_A_PROFILE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
HR_B_PROFILE = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

# Mirrors supabase/migrations/20261126000000_hr_company_invites.sql in SQLite.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS hr_company_invites (
  id                    TEXT PRIMARY KEY,
  company_id            TEXT NOT NULL,
  invited_email         TEXT NOT NULL,
  invited_by_profile_id TEXT NOT NULL,
  status                TEXT NOT NULL DEFAULT 'pending_admin'
                          CHECK (status IN ('pending_admin','approved','rejected',
                                            'accepted','expired','revoked')),
  token_hash            TEXT,
  expires_at            TEXT,
  approved_by_admin_id  TEXT,
  approved_at           TEXT,
  rejected_reason       TEXT,
  accepted_at           TEXT,
  accepted_profile_id   TEXT,
  revoked_at            TEXT,
  created_at            TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

_LIVE_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_company_invites_live_per_email
  ON hr_company_invites (company_id, LOWER(invited_email))
  WHERE status IN ('pending_admin','approved')
"""


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
        conn.execute(text(_LIVE_UNIQUE))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _client(db_session, *, company: str = COMPANY_A, profile: str = HR_A_PROFILE) -> TestClient:
    """A client whose caller is an HR user of `company`.

    `_caller_company_id` is a FastAPI dependency precisely so it can be overridden here —
    the real resolution (hr_users -> profiles -> session claim) is exercised by ST5.
    """
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    app.dependency_overrides[require_admin_or_hr] = lambda: {"id": profile, "role": "HR"}
    app.dependency_overrides[hr_company_invites._caller_company_id] = lambda: company
    app.dependency_overrides[hr_company_invites._get_db] = lambda: db_session
    return TestClient(app)


def _rows(db_session, company: str | None = None):
    sql = "SELECT company_id, invited_email, status, invited_by_profile_id FROM hr_company_invites"
    params = {}
    if company:
        sql += " WHERE company_id = :c"
        params["c"] = company
    return [dict(r._mapping) for r in db_session.execute(text(sql), params).fetchall()]


# ── the deliverable ───────────────────────────────────────────────────────────

def test_hr_raises_an_invite_that_lands_pending_admin(db_session):
    c = _client(db_session)
    r = c.post("/api/hr/company/invites", json={"email": "colleague@acme.com"})
    assert r.status_code == 201, r.text

    rows = _rows(db_session)
    assert len(rows) == 1
    assert rows[0]["company_id"] == COMPANY_A
    assert rows[0]["status"] == "pending_admin"
    assert rows[0]["invited_by_profile_id"] == HR_A_PROFILE


def test_the_invite_grants_nothing_on_its_own(db_session):
    """ST2 raises; only ST3 approves and only ST4 grants. No token exists yet."""
    c = _client(db_session)
    c.post("/api/hr/company/invites", json={"email": "colleague@acme.com"})
    row = db_session.execute(
        text("SELECT status, token_hash, approved_at, accepted_at FROM hr_company_invites")
    ).fetchone()._mapping
    assert row["status"] == "pending_admin"
    assert row["token_hash"] is None
    assert row["approved_at"] is None
    assert row["accepted_at"] is None


# ── the tenant boundary — the load-bearing test ───────────────────────────────

def test_a_body_supplied_company_id_is_ignored(db_session):
    """The AIQ-2090 regression guard for this surface.

    A caller who is HR of company A names company B in the body. The invite must be
    raised against A. Ignored, not honoured — and not a 422 either, because rejecting
    the field would still mean the endpoint reads it.
    """
    c = _client(db_session, company=COMPANY_A, profile=HR_A_PROFILE)
    r = c.post(
        "/api/hr/company/invites",
        json={"email": "attacker@acme.com", "company_id": COMPANY_B},
    )
    assert r.status_code == 201, r.text

    assert _rows(db_session, COMPANY_B) == [], "invite leaked into the company named in the body"
    rows = _rows(db_session, COMPANY_A)
    assert len(rows) == 1 and rows[0]["invited_email"] == "attacker@acme.com"


def test_get_returns_only_the_callers_own_company(db_session):
    _client(db_session, company=COMPANY_A, profile=HR_A_PROFILE).post(
        "/api/hr/company/invites", json={"email": "a-side@acme.com"}
    )
    _client(db_session, company=COMPANY_B, profile=HR_B_PROFILE).post(
        "/api/hr/company/invites", json={"email": "b-side@other.com"}
    )

    body = _client(db_session, company=COMPANY_A, profile=HR_A_PROFILE).get(
        "/api/hr/company/invites"
    ).json()
    emails = {i["invited_email"] for i in body["items"]}
    assert emails == {"a-side@acme.com"}, f"cross-tenant leak: {emails}"


def test_unauthenticated_callers_are_refused():
    """No dependency_overrides at all — the real require_admin_or_hr must reject."""
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    r = TestClient(app).post("/api/hr/company/invites", json={"email": "x@acme.com"})
    assert r.status_code in (401, 403), f"public caller got {r.status_code}"


def test_a_caller_with_no_company_is_refused(db_session, monkeypatch):
    """An HR profile with no tenant cannot invite anyone anywhere.

    The REAL _caller_company_id runs here. conftest replaces backend.database.db with a
    MagicMock whose every attribute returns a truthy Mock, so the resolution chain has to
    be stubbed to actually return nothing — otherwise this test passes for the wrong
    reason and would never catch a missing guard.
    """
    monkeypatch.setattr(hr_company_invites.db, "get_hr_company_id", lambda _uid: None)
    monkeypatch.setattr(hr_company_invites.db, "get_profile_record", lambda _uid: None)

    app = FastAPI()
    app.include_router(hr_company_invites.router)
    app.dependency_overrides[require_admin_or_hr] = lambda: {"id": "orphan", "role": "HR"}
    app.dependency_overrides[hr_company_invites._get_db] = lambda: db_session
    r = TestClient(app).post("/api/hr/company/invites", json={"email": "x@acme.com"})
    assert r.status_code == 403
    assert _rows(db_session) == []


# ── duplicate handling: 409, never a 500 ──────────────────────────────────────

def test_a_duplicate_live_invite_is_a_409_not_a_500(db_session):
    c = _client(db_session)
    assert c.post("/api/hr/company/invites", json={"email": "dupe@acme.com"}).status_code == 201
    r = c.post("/api/hr/company/invites", json={"email": "dupe@acme.com"})
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"
    assert len(_rows(db_session)) == 1


def test_duplicate_detection_is_case_insensitive(db_session):
    c = _client(db_session)
    assert c.post("/api/hr/company/invites", json={"email": "Dupe@Acme.com"}).status_code == 201
    r = c.post("/api/hr/company/invites", json={"email": "dupe@ACME.com"})
    assert r.status_code == 409
    assert len(_rows(db_session)) == 1


def test_the_same_colleague_can_be_reinvited_after_a_rejection(db_session):
    """The partial index covers only live statuses, so a rejection must free the slot."""
    c = _client(db_session)
    assert c.post("/api/hr/company/invites", json={"email": "second@acme.com"}).status_code == 201
    db_session.execute(text("UPDATE hr_company_invites SET status='rejected'"))
    db_session.commit()
    assert c.post("/api/hr/company/invites", json={"email": "second@acme.com"}).status_code == 201
    assert len(_rows(db_session)) == 2


def test_two_companies_may_invite_the_same_email(db_session):
    """The uniqueness is per (company, email) — one person can be invited by two customers."""
    assert _client(db_session, company=COMPANY_A, profile=HR_A_PROFILE).post(
        "/api/hr/company/invites", json={"email": "consultant@freelance.com"}
    ).status_code == 201
    assert _client(db_session, company=COMPANY_B, profile=HR_B_PROFILE).post(
        "/api/hr/company/invites", json={"email": "consultant@freelance.com"}
    ).status_code == 201
    assert len(_rows(db_session)) == 2


# ── prod wiring: registered in the app Render actually boots ──────────────────

def test_the_routes_are_registered_on_the_production_app():
    """CLAUDE.md hard rule: a router registered only in backend/app/main.py 405s in prod.

    Render boots `uvicorn backend.main:app`, so that is the app this asserts against.
    """
    from backend.main import app as prod_app

    paths = {r.path for r in prod_app.routes if "company/invites" in getattr(r, "path", "")}
    assert "/api/hr/company/invites" in paths, f"not registered on backend.main: {paths}"
