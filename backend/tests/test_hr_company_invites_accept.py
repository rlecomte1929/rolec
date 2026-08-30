"""
[AIQ-2094 ST4] The colleague accepts an admin-approved invite.

This is the only code path in the product that attaches an HR profile to an EXISTING
company. AIQ-2090 (PR #1989) had to remove the previous one because a typed company name
on a public form joined a stranger into a customer's tenant. Everything here exists so the
replacement rests on something an attacker cannot assert.

DESIGN DEVIATION FROM THE CARD, decided with Romain 2026-08-30: the card specified an
unauthenticated public route. This requires an authenticated caller instead. The colleague
registers normally (AIQ-2090 gives them their own throwaway company), then accepts while
logged in, and their profile is re-pointed to the invite's company. That removes a public
write path into the identity system and the whole account-creation surface, and it needs no
route_auth_allowlist entry. The orphan company it leaves behind is exactly what ST6 merges.

Order of trust: HR raises (ST2) -> admin approves (ST3) -> colleague accepts (here).

FIVE REFUSALS, each its own test:
  wrong status  · expired · already accepted · forged token · email mismatch
The email check is what stops a holder of a leaked token from joining a tenant they were
never invited to — the token alone is not authorisation.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.routers import hr_company_invites
from backend.app.auth_deps import get_current_user

COMPANY_A = "11111111-1111-4111-8111-111111111111"
COMPANY_B = "22222222-2222-4222-8222-222222222222"
HR_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
COLLEAGUE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
COLLEAGUE_EMAIL = "colleague@acme.com"

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

RAW_TOKEN = "a-perfectly-good-token-value"
TOKEN_HASH = hashlib.sha256(RAW_TOKEN.encode()).hexdigest()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA))
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def linked(monkeypatch):
    """Capture ensure_hr_user_for_profile calls — the actual grant of access."""
    calls = []
    monkeypatch.setattr(
        hr_company_invites.db, "ensure_hr_user_for_profile",
        lambda profile_id, company_id: calls.append((profile_id, company_id)),
    )
    return calls


def _client(db_session, *, profile: str = COLLEAGUE, email: str = COLLEAGUE_EMAIL) -> TestClient:
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": profile, "email": email}
    app.dependency_overrides[hr_company_invites._get_db] = lambda: db_session
    return TestClient(app)


def _seed(db_session, *, status: str = "approved", company: str = COMPANY_A,
          email: str = COLLEAGUE_EMAIL, token_hash: str | None = TOKEN_HASH,
          expires_in_days: int = 14) -> str:
    exp = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
    db_session.execute(
        text("INSERT INTO hr_company_invites "
             "(id, company_id, invited_email, invited_by_profile_id, status, token_hash, expires_at) "
             "VALUES ('inv-1', :c, :e, :p, :s, :t, :x)"),
        {"c": company, "e": email, "p": HR_A, "s": status, "t": token_hash, "x": exp},
    )
    db_session.commit()
    return "inv-1"


def _row(db_session) -> dict:
    r = db_session.execute(text("SELECT * FROM hr_company_invites WHERE id='inv-1'")).fetchone()
    return dict(r._mapping) if r else {}


# ── the happy path ────────────────────────────────────────────────────────────

def test_accepting_an_approved_invite_links_the_colleague_to_the_invites_company(db_session, linked):
    _seed(db_session)
    r = _client(db_session).post(f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code == 200, r.text

    assert linked == [(COLLEAGUE, COMPANY_A)], f"link call was {linked}"
    row = _row(db_session)
    assert row["status"] == "accepted"
    assert row["accepted_profile_id"] == COLLEAGUE
    assert row["accepted_at"] is not None


def test_the_company_comes_from_the_invite_row_not_the_caller(db_session, linked):
    """The AIQ-2090 property. The caller cannot influence which tenant they land in."""
    _seed(db_session, company=COMPANY_B)
    r = _client(db_session).post(
        f"/api/company-invites/{RAW_TOKEN}/accept",
        json={"company_id": COMPANY_A},          # ignored — there is no such field
        params={"company_id": COMPANY_A},        # ignored — nor such a query param
    )
    assert r.status_code == 200, r.text
    assert linked == [(COLLEAGUE, COMPANY_B)], \
        f"caller steered the tenant: {linked}"


# ── the five refusals ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["pending_admin", "rejected", "accepted", "expired", "revoked"])
def test_only_an_approved_invite_can_be_accepted(db_session, linked, status):
    """`pending_admin` is the important one: it proves the admin gate cannot be skipped."""
    _seed(db_session, status=status)
    r = _client(db_session).post(f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code in (403, 409, 410), f"status={status} accepted with {r.status_code}"
    assert linked == [], f"status={status} granted access: {linked}"


def test_an_expired_invite_is_refused_and_marked_expired(db_session, linked):
    _seed(db_session, expires_in_days=-1)
    r = _client(db_session).post(f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code == 410, r.text
    assert linked == []
    assert _row(db_session)["status"] == "expired"


def test_a_forged_token_is_404_and_leaks_nothing(db_session, linked):
    _seed(db_session)
    r = _client(db_session).post("/api/company-invites/not-the-real-token/accept")
    assert r.status_code == 404
    assert linked == []
    body = r.text.lower()
    for leak in (COMPANY_A.lower(), COLLEAGUE_EMAIL.lower(), "inv-1"):
        assert leak not in body, f"404 body leaked {leak!r}"


def test_a_second_accept_is_refused_and_does_not_double_link(db_session, linked):
    _seed(db_session)
    c = _client(db_session)
    assert c.post(f"/api/company-invites/{RAW_TOKEN}/accept").status_code == 200
    r = c.post(f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code in (403, 409), f"replay returned {r.status_code}"
    assert len(linked) == 1, f"replay re-linked: {linked}"


def test_a_different_person_cannot_use_someone_elses_token(db_session, linked):
    """A leaked token must not let its holder join a tenant they were never invited to.

    The token is a pointer to an invite; it is not authorisation on its own.
    """
    _seed(db_session, email="the.invited.person@acme.com")
    r = _client(db_session, profile="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                email="someone.else@elsewhere.com").post(
        f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code in (403, 404), f"token holder joined anyway: {r.status_code}"
    assert linked == [], f"granted access to the wrong person: {linked}"
    assert _row(db_session)["status"] == "approved", "the invite was consumed by the wrong person"


def test_an_unauthenticated_caller_is_refused(db_session):
    """No overrides — the real get_current_user must reject. This route is NOT public."""
    _seed(db_session)
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    r = TestClient(app).post(f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code in (401, 403)


def test_the_raw_token_is_never_used_as_a_lookup_key(db_session, linked):
    """An invite whose token_hash holds the RAW token must not be findable by it."""
    _seed(db_session, token_hash=RAW_TOKEN)
    r = _client(db_session).post(f"/api/company-invites/{RAW_TOKEN}/accept")
    assert r.status_code == 404, "lookup matched a raw token instead of its sha256"
    assert linked == []


# ── prod wiring ───────────────────────────────────────────────────────────────

def test_the_accept_route_is_registered_on_the_production_app():
    from backend.main import app as prod_app

    paths = {r.path for r in prod_app.routes if "company-invites" in getattr(r, "path", "")}
    assert any(p.endswith("/accept") for p in paths), f"accept not on backend.main: {paths}"
