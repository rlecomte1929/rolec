"""
[AIQ-2094 ST5] Adversarial tenant-boundary suite for the colleague-invite path.

ST2/ST3/ST4 each test their own route. This attacks the BOUNDARY across all three at
once, and differs from them in one deliberate way:

    only `get_current_user` is overridden. `require_admin`, `require_admin_or_hr` and
    `_caller_company_id` all run for real.

The per-subtask tests override the guard they are not exercising, which is right for unit
scope and wrong here — a suite that stubs the guards cannot discover that a guard is
missing. Everything below reaches the real ones.

Companion to test_tenant_boundary_aiq2090.py, which covers the SIGNUP side of the same
bug (a typed company name joining a stranger into a tenant). This covers the replacement
path built to give that need a safe route back.

Every test here was run against a permissive implementation before the guards existed and
observed to fail; see the PR body. A tenant guard that has never failed proves nothing.
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

ACME = "11111111-1111-4111-8111-111111111111"       # the victim tenant
RIVAL = "22222222-2222-4222-8222-222222222222"      # the attacker's tenant

HR_ACME = {"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "email": "hr@acme.com", "role": "HR"}
HR_RIVAL = {"id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "email": "hr@rival.com", "role": "HR"}
ADMIN = {"id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd", "email": "ops@relopass.com",
         "role": "ADMIN", "is_admin": True}
COLLEAGUE = {"id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc", "email": "new.hire@acme.com"}
OUTSIDER = {"id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", "email": "attacker@rival.com"}

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


@pytest.fixture()
def grants(monkeypatch):
    """Every actual grant of tenant access. Empty means nobody got in."""
    calls = []
    monkeypatch.setattr(
        hr_company_invites.db, "ensure_hr_user_for_profile",
        lambda profile_id, company_id: calls.append((profile_id, company_id)),
    )
    return calls


@pytest.fixture()
def tenancy(monkeypatch):
    """Map profile id -> company, the way hr_users/profiles would in production.

    The REAL _caller_company_id runs against this: conftest replaces backend.database.db
    with a MagicMock whose attributes are all truthy, so without stubbing the lookup
    every caller would resolve to a truthy Mock and the tenant tests would pass
    vacuously.
    """
    mapping = {HR_ACME["id"]: ACME, HR_RIVAL["id"]: RIVAL}
    monkeypatch.setattr(hr_company_invites.db, "get_hr_company_id", lambda uid: mapping.get(uid))
    monkeypatch.setattr(hr_company_invites.db, "get_profile_record", lambda uid: None)
    return mapping


def _as(db_session, principal: dict) -> TestClient:
    """A client authenticated as `principal`. ONLY identity is overridden — every
    authorisation guard on the routes runs for real."""
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    app.dependency_overrides[get_current_user] = lambda: dict(principal)
    app.dependency_overrides[hr_company_invites._get_db] = lambda: db_session
    return TestClient(app)


def _rows(db_session, company: str | None = None) -> list[dict]:
    sql = "SELECT id, company_id, invited_email, status FROM hr_company_invites"
    p = {}
    if company:
        sql += " WHERE company_id = :c"; p["c"] = company
    return [dict(r._mapping) for r in db_session.execute(text(sql), p).fetchall()]


def _seed(db_session, invite_id, *, company=ACME, email="new.hire@acme.com",
          status="pending_admin", token=None, expires_days=14):
    db_session.execute(
        text("INSERT INTO hr_company_invites "
             "(id, company_id, invited_email, invited_by_profile_id, status, token_hash, expires_at) "
             "VALUES (:i,:c,:e,:p,:s,:t,:x)"),
        {"i": invite_id, "c": company, "e": email, "p": HR_ACME["id"], "s": status,
         "t": hashlib.sha256(token.encode()).hexdigest() if token else None,
         "x": (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()},
    )
    db_session.commit()


# ── positive control: the suite is not vacuously green ────────────────────────

def test_the_full_lifecycle_actually_works(db_session, grants, tenancy):
    """HR raises -> admin approves -> colleague accepts. If this ever fails, every
    refusal below proves nothing, because everything would be refused."""
    r = _as(db_session, HR_ACME).post("/api/hr/company/invites",
                                      json={"email": COLLEAGUE["email"]})
    assert r.status_code == 201, r.text
    invite_id = r.json()["id"]

    r = _as(db_session, ADMIN).post(f"/api/admin/company-invites/{invite_id}/approve")
    assert r.status_code == 200, r.text
    token = r.json()["accept_token"]

    r = _as(db_session, COLLEAGUE).post(f"/api/company-invites/{token}/accept")
    assert r.status_code == 200, r.text

    assert grants == [(COLLEAGUE["id"], ACME)], f"grant was {grants}"


# ── role escalation: HR must not be able to act as the admin gate ─────────────

@pytest.mark.parametrize("method,path", [
    ("get", "/api/admin/company-invites"),
    ("post", "/api/admin/company-invites/inv-1/approve"),
    ("post", "/api/admin/company-invites/inv-1/reject"),
])
def test_an_hr_user_cannot_operate_the_admin_review_gate(db_session, grants, tenancy, method, path):
    """The whole design rests on an admin approving. An HR user who could approve their
    own invite would collapse the gate to nothing."""
    _seed(db_session, "inv-1")
    r = getattr(_as(db_session, HR_ACME), method)(path)
    assert r.status_code == 403, f"HR reached {path} with {r.status_code}"
    assert _rows(db_session)[0]["status"] == "pending_admin", "HR mutated the invite"


def test_an_hr_user_cannot_approve_by_impersonating_admin_in_the_payload(db_session, tenancy):
    _seed(db_session, "inv-2")
    r = _as(db_session, HR_ACME).post(
        "/api/admin/company-invites/inv-2/approve",
        json={"is_admin": True, "role": "ADMIN"},
    )
    assert r.status_code == 403
    assert _rows(db_session)[0]["status"] == "pending_admin"


# ── cross-tenant reads and writes ────────────────────────────────────────────

def test_an_hr_user_cannot_see_another_companys_invites(db_session, tenancy):
    _seed(db_session, "inv-acme", company=ACME, email="a@acme.com")
    _seed(db_session, "inv-rival", company=RIVAL, email="b@rival.com")

    body = _as(db_session, HR_RIVAL).get("/api/hr/company/invites").json()
    ids = {i["id"] for i in body["items"]}
    assert ids == {"inv-rival"}, f"cross-tenant read: {ids}"


def test_a_body_supplied_company_id_cannot_redirect_the_invite(db_session, tenancy):
    """The AIQ-2090 shape, on the new surface: the tenant must come from the caller."""
    r = _as(db_session, HR_RIVAL).post(
        "/api/hr/company/invites",
        json={"email": "mole@acme.com", "company_id": ACME},
    )
    assert r.status_code == 201, r.text
    assert _rows(db_session, ACME) == [], "invite landed in the company named in the body"
    assert len(_rows(db_session, RIVAL)) == 1


def test_an_hr_user_with_no_tenant_cannot_invite_anyone(db_session, tenancy):
    """tenancy maps only HR_ACME and HR_RIVAL; OUTSIDER resolves to nothing."""
    r = _as(db_session, OUTSIDER).post("/api/hr/company/invites", json={"email": "x@acme.com"})
    assert r.status_code == 403
    assert _rows(db_session) == []


# ── the admin gate cannot be skipped or replayed ─────────────────────────────

def test_a_raised_invite_cannot_be_accepted_before_an_admin_approves(db_session, grants, tenancy):
    """The single most important refusal in the feature."""
    r = _as(db_session, HR_ACME).post("/api/hr/company/invites",
                                      json={"email": COLLEAGUE["email"]})
    assert r.status_code == 201
    # No token exists yet, but try the obvious guesses anyway.
    for guess in (r.json()["id"], "", "pending_admin", COLLEAGUE["email"]):
        resp = _as(db_session, COLLEAGUE).post(f"/api/company-invites/{guess or 'x'}/accept")
        assert resp.status_code in (403, 404, 409), f"guess {guess!r} -> {resp.status_code}"
    assert grants == [], f"access granted without approval: {grants}"


def test_the_status_gate_itself_refuses_a_pending_invite_that_has_a_token(db_session, grants, tenancy):
    """Reaches the status gate, which the test above never does.

    A raised invite has token_hash NULL, so an accept attempt 404s at the LOOKUP and
    never exercises the status gate at all. This seeds the one shape that gets past
    the lookup: pending_admin WITH a token. ST3 never produces that today, but a
    change that minted the token before flipping status would.

    Sabotage-verified, and the result is worth recording: the admin gate has TWO
    independent guards — the explicit `status != 'approved'` check, and the claim
    UPDATE's own `WHERE ... AND status = 'approved'`. Removing EITHER alone still
    refuses, so neither single removal is a vulnerability. Only removing BOTH admits
    an unapproved invite, and that is what this test catches. It is the backstop for
    the whole admin-review design.
    """
    _seed(db_session, "inv-tokened", status="pending_admin", token="premature-token")
    r = _as(db_session, COLLEAGUE).post("/api/company-invites/premature-token/accept")
    assert r.status_code == 409, f"unapproved invite accepted with {r.status_code}"
    assert grants == [], f"admin gate bypassed: {grants}"
    assert _rows(db_session)[0]["status"] == "pending_admin"


@pytest.mark.parametrize("status", ["rejected", "revoked", "expired", "accepted"])
def test_a_dead_invite_cannot_be_resurrected_by_an_admin(db_session, grants, tenancy, status):
    _seed(db_session, "inv-dead", status=status)
    r = _as(db_session, ADMIN).post("/api/admin/company-invites/inv-dead/approve")
    assert r.status_code == 409, f"status={status} was re-approvable"
    assert _rows(db_session)[0]["status"] == status, "the 409 path mutated the row"
    assert grants == []


def test_a_leaked_token_does_not_admit_its_holder(db_session, grants, tenancy):
    """The token points at an invite; the caller's own email is what authorises."""
    _seed(db_session, "inv-leak", status="approved", token="leaked-token-value")
    r = _as(db_session, OUTSIDER).post("/api/company-invites/leaked-token-value/accept")
    assert r.status_code in (403, 404), f"leaked token admitted holder: {r.status_code}"
    assert grants == [], f"granted: {grants}"
    assert _rows(db_session)[0]["status"] == "approved", "the invite was consumed"


def test_a_token_for_one_company_cannot_land_the_caller_in_another(db_session, grants, tenancy):
    """Even for the RIGHT person, the tenant comes from the invite row alone."""
    _seed(db_session, "inv-x", company=RIVAL, email=COLLEAGUE["email"],
          status="approved", token="tok-rival")
    r = _as(db_session, COLLEAGUE).post("/api/company-invites/tok-rival/accept")
    assert r.status_code == 200, r.text
    assert grants == [(COLLEAGUE["id"], RIVAL)], \
        f"landed in a company other than the invite's: {grants}"


# ── the original AIQ-2090 guard still holds ──────────────────────────────────

def test_signup_still_never_joins_a_company_by_typed_name():
    """The regression this whole feature exists to make unnecessary.

    Duplicated deliberately from test_tenant_boundary_aiq2090.py: if the invite path
    ever tempts someone to re-wire signup to find_or_create_company_by_name, this suite
    fails too, not only that one.
    """
    import inspect
    import re
    from backend.app.routers import auth as auth_router

    src = inspect.getsource(auth_router)
    # Match the CALL SITE, not the name. AIQ-2090 deliberately left an explanatory
    # comment naming the old helper, and a bare substring check flags that comment —
    # the same trap that made a warning comment trip test_jsonb_bind_cast.
    calls = re.findall(r"db\.find_or_create_company_by_name\s*\(", src)
    assert calls == [], (
        "signup is wired back to the name-matching join — AIQ-2090 regression"
    )
    assert "db.create_company_for_self_serve_signup(" in src
