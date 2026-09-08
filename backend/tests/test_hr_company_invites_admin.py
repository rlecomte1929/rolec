"""
[AIQ-2094 ST3] The admin review gate — the control point of the whole feature.

Romain's decision, 2026-08-30: the admin keeps control of who in a company can use the
system. An HR user may raise an invite (ST2), but nothing reaches the colleague until an
admin approves it here. There is no domain matching anywhere in the design.

Two properties carry the security of this stage and are tested first:

  * only `pending_admin` may transition. Anything else is a 409 with NO mutation — if a
    second approve could re-run, it would mint a SECOND valid token for an invite that may
    since have been accepted or revoked.
  * the raw accept token is returned to the admin exactly once and NEVER persisted. Only
    its sha256 is stored, so a database leak yields no working invite links.

Both were shown failing against a permissive stub before the router was written.

Table shape mirrors 20261126000000, applied to prod 2026-08-30. token_hash and expires_at
are NULL until approval — an unapproved invite has no token at all.
"""
from __future__ import annotations

import hashlib
import logging
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
from backend.app.auth_deps import require_admin

COMPANY_A = "11111111-1111-4111-8111-111111111111"
COMPANY_B = "22222222-2222-4222-8222-222222222222"
HR_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ADMIN = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

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


def _admin_client(db_session) -> TestClient:
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    app.dependency_overrides[require_admin] = lambda: {"id": ADMIN, "is_admin": True}
    app.dependency_overrides[hr_company_invites._get_db] = lambda: db_session
    return TestClient(app)


def _seed(db_session, invite_id: str, *, company: str = COMPANY_A,
          email: str = "colleague@acme.com", status: str = "pending_admin") -> str:
    db_session.execute(
        text("INSERT INTO hr_company_invites "
             "(id, company_id, invited_email, invited_by_profile_id, status) "
             "VALUES (:i, :c, :e, :p, :s)"),
        {"i": invite_id, "c": company, "e": email, "p": HR_A, "s": status},
    )
    db_session.commit()
    return invite_id


def _row(db_session, invite_id: str) -> dict:
    r = db_session.execute(
        text("SELECT * FROM hr_company_invites WHERE id = :i"), {"i": invite_id}
    ).fetchone()
    return dict(r._mapping) if r else {}


# ── the gate ──────────────────────────────────────────────────────────────────

def test_a_non_admin_cannot_reach_the_review_queue(db_session):
    """No overrides at all — the real require_admin must refuse."""
    app = FastAPI()
    app.include_router(hr_company_invites.router)
    c = TestClient(app)
    assert c.get("/api/admin/company-invites").status_code in (401, 403)
    assert c.post("/api/admin/company-invites/whatever/approve").status_code in (401, 403)


def test_the_queue_lists_pending_invites_across_all_companies(db_session):
    _seed(db_session, "inv-a", company=COMPANY_A, email="a@acme.com")
    _seed(db_session, "inv-b", company=COMPANY_B, email="b@other.com")
    _seed(db_session, "inv-done", company=COMPANY_A, email="c@acme.com", status="accepted")

    body = _admin_client(db_session).get("/api/admin/company-invites").json()
    ids = {i["id"] for i in body["items"]}
    assert ids == {"inv-a", "inv-b"}, f"default queue should be pending only, got {ids}"


def test_approving_a_pending_invite_stamps_the_approver(db_session):
    _seed(db_session, "inv-1")
    r = _admin_client(db_session).post("/api/admin/company-invites/inv-1/approve")
    assert r.status_code == 200, r.text

    row = _row(db_session, "inv-1")
    assert row["status"] == "approved"
    assert row["approved_by_admin_id"] == ADMIN
    assert row["approved_at"] is not None
    assert row["expires_at"] is not None


def test_rejecting_stores_the_reason(db_session):
    _seed(db_session, "inv-2")
    r = _admin_client(db_session).post(
        "/api/admin/company-invites/inv-2/reject", json={"reason": "left the company"}
    )
    assert r.status_code == 200, r.text
    row = _row(db_session, "inv-2")
    assert row["status"] == "rejected"
    assert row["rejected_reason"] == "left the company"
    assert row["token_hash"] is None, "a rejected invite must never carry a token"


# ── the two load-bearing security properties ──────────────────────────────────

def test_only_pending_may_transition_and_a_replay_mutates_nothing(db_session):
    """A second approve must NOT re-run.

    If it did it would mint a second valid token for an invite that may since have been
    accepted or revoked — a live credential for a decision already made.
    """
    _seed(db_session, "inv-3")
    c = _admin_client(db_session)
    assert c.post("/api/admin/company-invites/inv-3/approve").status_code == 200
    before = _row(db_session, "inv-3")

    r = c.post("/api/admin/company-invites/inv-3/approve")
    assert r.status_code == 409, f"replayed approve returned {r.status_code}"
    assert _row(db_session, "inv-3") == before, "409 path mutated the row"


@pytest.mark.parametrize("status", ["approved", "rejected", "accepted", "expired", "revoked"])
def test_no_non_pending_status_can_be_approved(db_session, status):
    _seed(db_session, f"inv-{status}", status=status)
    r = _admin_client(db_session).post(f"/api/admin/company-invites/inv-{status}/approve")
    assert r.status_code == 409, f"status={status} was approvable"


def test_the_raw_token_is_returned_once_and_never_stored(db_session):
    """Only sha256 is persisted, so a database leak yields no working invite links."""
    _seed(db_session, "inv-4")
    r = _admin_client(db_session).post("/api/admin/company-invites/inv-4/approve")
    assert r.status_code == 200

    raw = r.json().get("accept_token")
    assert raw, "the admin must receive the token exactly once"

    row = _row(db_session, "inv-4")
    assert row["token_hash"] == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in (row["token_hash"] or ""), "raw token leaked into token_hash"

    stored = " ".join(str(v) for v in row.values() if v is not None)
    assert raw not in stored, "the raw token was persisted somewhere on the row"


def test_a_missing_invite_is_404_not_500(db_session):
    r = _admin_client(db_session).post("/api/admin/company-invites/does-not-exist/approve")
    assert r.status_code == 404


def test_rejection_frees_the_slot_for_a_fresh_invite(db_session):
    """The partial unique index covers only live statuses (ST1)."""
    _seed(db_session, "inv-5", email="again@acme.com")
    assert _admin_client(db_session).post(
        "/api/admin/company-invites/inv-5/reject", json={"reason": "wrong person"}
    ).status_code == 200
    _seed(db_session, "inv-6", email="again@acme.com")  # must not raise
    assert _row(db_session, "inv-6")["status"] == "pending_admin"


def test_approve_writes_an_admin_audit_event(db_session, monkeypatch):
    """Reuses record_admin_event, which already handles the audit_logs
    action_type CHECK and the entity_id NOT NULL uuid constraint."""
    seen = {}
    monkeypatch.setattr(
        hr_company_invites, "record_admin_event",
        lambda db, **kw: seen.update(kw),
    )
    _seed(db_session, "inv-7")
    assert _admin_client(db_session).post(
        "/api/admin/company-invites/inv-7/approve"
    ).status_code == 200
    assert seen.get("actor_id") == ADMIN
    assert "approve" in seen.get("event", "")
    assert seen.get("entity_id") == "inv-7"


# ── prod wiring ───────────────────────────────────────────────────────────────

def test_the_admin_routes_are_registered_on_the_production_app():
    from backend.main import app as prod_app

    paths = {r.path for r in prod_app.routes if "admin/company-invites" in getattr(r, "path", "")}
    assert "/api/admin/company-invites" in paths, f"not on backend.main: {paths}"
    assert any(p.endswith("/approve") for p in paths), f"approve missing: {paths}"
    assert any(p.endswith("/reject") for p in paths), f"reject missing: {paths}"


# ── [AIQ-2188] the approve handler delivers the accept link by email ───────────
#
# AIQ-2094 shipped the lifecycle but left delivery to a human relay. These pin the
# gap-closing send: exactly one email on a real approve, none on a replay, the emailed
# token is the working one, a send failure never rolls back the approval, and the raw
# token never reaches a log line.

def _capture_sender(monkeypatch) -> list:
    """Replace the router's email sender with a stub that records its kwargs."""
    calls: list = []
    monkeypatch.setattr(
        hr_company_invites, "send_company_invite_email",
        lambda **kw: calls.append(kw) or {"status": "logged"},
    )
    return calls


def test_approving_sends_exactly_one_invite_email_to_the_invited_address(db_session, monkeypatch):
    calls = _capture_sender(monkeypatch)
    _seed(db_session, "inv-e1", email="colleague@acme.com")
    r = _admin_client(db_session).post("/api/admin/company-invites/inv-e1/approve")
    assert r.status_code == 200, r.text
    assert len(calls) == 1, f"expected one email, got {len(calls)}"
    assert calls[0]["to_email"] == "colleague@acme.com"
    assert calls[0]["raw_token"], "the emailed link needs the raw token"


def test_no_second_email_is_sent_on_a_replayed_approve(db_session, monkeypatch):
    calls = _capture_sender(monkeypatch)
    _seed(db_session, "inv-e2")
    c = _admin_client(db_session)
    assert c.post("/api/admin/company-invites/inv-e2/approve").status_code == 200
    assert c.post("/api/admin/company-invites/inv-e2/approve").status_code == 409
    assert len(calls) == 1, "a replayed (409) approve must not send a second email"


def test_the_emailed_token_hashes_to_the_stored_hash(db_session, monkeypatch):
    calls = _capture_sender(monkeypatch)
    _seed(db_session, "inv-e3")
    r = _admin_client(db_session).post("/api/admin/company-invites/inv-e3/approve")
    assert r.status_code == 200
    emailed = calls[0]["raw_token"]
    # the token in the email is exactly the one minted, and only its sha256 is stored
    assert emailed == r.json()["accept_token"]
    assert _row(db_session, "inv-e3")["token_hash"] == hashlib.sha256(emailed.encode()).hexdigest()


def test_the_emailed_token_actually_accepts(db_session, monkeypatch):
    """The real proof: feed the emailed token to the accept route and it redeems."""
    from backend.app.auth_deps import get_current_user

    calls = _capture_sender(monkeypatch)
    monkeypatch.setattr(hr_company_invites.db, "ensure_hr_user_for_profile", lambda *a, **k: None)
    _seed(db_session, "inv-e4", email="rt@acme.com")
    approve = _admin_client(db_session).post("/api/admin/company-invites/inv-e4/approve")
    assert approve.status_code == 200
    emailed = calls[0]["raw_token"]

    app = FastAPI()
    app.include_router(hr_company_invites.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-rt", "email": "rt@acme.com"}
    app.dependency_overrides[hr_company_invites._get_db] = lambda: db_session
    accepted = TestClient(app).post(f"/api/company-invites/{emailed}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"


def test_a_send_failure_leaves_the_invite_approved(db_session, monkeypatch):
    """A delivery crash must not roll back a valid approval, and must not 500."""
    def boom(**kw):
        raise RuntimeError("mail transport down")
    monkeypatch.setattr(hr_company_invites, "send_company_invite_email", boom)
    _seed(db_session, "inv-e5")
    r = _admin_client(db_session).post("/api/admin/company-invites/inv-e5/approve")
    assert r.status_code == 200, r.text
    row = _row(db_session, "inv-e5")
    assert row["status"] == "approved"
    assert row["token_hash"] is not None, "the approval (and its token) must survive a send failure"


def test_the_invite_email_never_logs_the_raw_token(caplog, monkeypatch):
    """ST3's property extends to logs: the no-key dev path withholds the token-bearing body."""
    from backend.app.services.company_invite_email import send_company_invite_email

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with caplog.at_level(logging.INFO):
        res = send_company_invite_email(
            to_email="c@acme.com", company_name="Acme", raw_token="SUPERSECRETTOKEN123",
        )
    assert res["status"] == "logged"
    assert "SUPERSECRETTOKEN123" not in caplog.text, "the raw token leaked into a log line"
