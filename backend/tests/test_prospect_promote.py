"""Track A — prospect → outreach "promote" endpoint (admin_prospects.py).

Locks the bridge that turns an approved ``prospect_candidate`` into a
``linkedin_prospects`` contact seeded with the enrichment hook (as an initial
``outreach_messages`` draft), flips the candidate to ``promoted``, and rejects
double-promote / non-approved.

Runs on a shared in-memory SQLite DB (StaticPool). ``prospect_candidates`` has
an ORM model so it's created from metadata; ``linkedin_prospects`` and
``outreach_messages`` are raw Supabase tables (no model), so they're created
here under an attached ``public`` schema with SQLite-compatible defaults — the
endpoint writes them via ``public.`` raw SQL exactly as in admin_outreach.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth_deps import require_admin
from backend.app.models import ProspectCandidate
from backend.app.routers import admin_prospects
from backend.main import app as prod_app

# The endpoint's INSERT ... RETURNING id needs SQLite >= 3.35.
_HAS_RETURNING = sqlite3.sqlite_version_info >= (3, 35, 0)

_LINKEDIN_DDL = """
CREATE TABLE public.linkedin_prospects (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    full_name TEXT NOT NULL,
    linkedin_url TEXT UNIQUE NOT NULL,
    profile_headline TEXT,
    company_name TEXT NOT NULL,
    company_size TEXT,
    job_title TEXT NOT NULL,
    corridor_relevance TEXT,
    notes TEXT,
    source TEXT DEFAULT 'linkedin',
    status TEXT NOT NULL DEFAULT 'flagged',
    message_sent_at TEXT,
    last_reply_at TEXT,
    follow_up_sent_at TEXT,
    converted_at TEXT
)
"""

_OUTREACH_DDL = """
CREATE TABLE public.outreach_messages (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    prospect_id TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'initial',
    subject_line TEXT,
    body TEXT NOT NULL,
    personalisation_notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    approved_at TEXT,
    sent_at TEXT,
    copied_to_clipboard_at TEXT
)
"""


@pytest.fixture
def Session(monkeypatch):
    """In-memory SQLite wired to admin_prospects.SessionLocal, with the two
    raw outreach tables created under an attached ``public`` schema."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
        conn.exec_driver_sql(_LINKEDIN_DDL)
        conn.exec_driver_sql(_OUTREACH_DDL)
    # prospect_candidates comes from the ORM model (default/main schema).
    ProspectCandidate.__table__.create(bind=engine)

    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(admin_prospects, "SessionLocal", TestSession)
    return TestSession


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_prospects.router, prefix="/api/admin")
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "email": "admin@relopass.com", "role": "ADMIN"}
    return TestClient(app)


def _seed(Session, *, status: str, hook: str | None = "Great hook", title: str | None = "Head of People") -> str:
    row = ProspectCandidate(
        id="cand-1",
        company_name="Acme AS",
        company_domain="acme.no",
        raw_input_json="{}",
        enriched_json="{}",
        icp_score=85,
        qualification_band="hot",
        suggested_contact_title=title,
        suggested_hook=hook,
        status=status,
        web_search_used=False,
    )
    with Session() as s:
        s.add(row)
        s.commit()
    return row.id


def test_promote_route_registered_on_prod_app():
    """The promote route is wired onto the production app (no DB needed)."""
    hits = {
        (r.path, "POST")
        for r in prod_app.routes
        if getattr(r, "path", "") == "/api/admin/prospects/{prospect_id}/promote"
        and "POST" in (getattr(r, "methods", None) or set())
    }
    assert hits, "promote route must be registered on the prod app"


def test_promote_unknown_prospect_is_404(Session):
    resp = _client().post("/api/admin/prospects/does-not-exist/promote")
    assert resp.status_code == 404


def test_promote_non_approved_is_409(Session):
    _seed(Session, status="enriched")
    resp = _client().post("/api/admin/prospects/cand-1/promote")
    assert resp.status_code == 409
    assert "approve" in resp.json()["detail"].lower()


def test_promote_already_promoted_is_409(Session):
    _seed(Session, status="promoted")
    resp = _client().post("/api/admin/prospects/cand-1/promote")
    assert resp.status_code == 409
    assert "already promoted" in resp.json()["detail"].lower()


@pytest.mark.skipif(not _HAS_RETURNING, reason="endpoint uses INSERT ... RETURNING (needs SQLite >= 3.35)")
def test_promote_happy_path_creates_contact_and_draft(Session):
    _seed(Session, status="approved", hook="You expand across the Nordics — we handle relocations.", title="Head of Global Mobility")

    resp = _client().post("/api/admin/prospects/cand-1/promote")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_initial_draft"] is True
    assert body["outreach_status"] == "message_drafted"
    new_id = body["promoted_prospect_id"]
    assert new_id

    with Session() as s:
        contact = s.execute(
            text("SELECT company_name, job_title, source, status, linkedin_url FROM public.linkedin_prospects WHERE id = :i"),
            {"i": new_id},
        ).mappings().one()
        assert contact["company_name"] == "Acme AS"
        assert contact["job_title"] == "Head of Global Mobility"
        assert contact["source"] == "prospect_pipeline"
        assert contact["status"] == "message_drafted"
        assert contact["linkedin_url"]  # non-null, unique people-search seed

        draft = s.execute(
            text("SELECT body, message_type, status FROM public.outreach_messages WHERE prospect_id = :i"),
            {"i": new_id},
        ).mappings().one()
        assert draft["body"].startswith("You expand across the Nordics")
        assert draft["message_type"] == "initial"
        assert draft["status"] == "draft"

        cand = s.get(ProspectCandidate, "cand-1")
        assert cand.status == "promoted"
        assert cand.reviewed_by == "admin@relopass.com"


@pytest.mark.skipif(not _HAS_RETURNING, reason="endpoint uses INSERT ... RETURNING (needs SQLite >= 3.35)")
def test_promote_without_hook_flags_no_draft(Session):
    _seed(Session, status="approved", hook=None)
    resp = _client().post("/api/admin/prospects/cand-1/promote")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_initial_draft"] is False
    assert body["outreach_status"] == "flagged"
    with Session() as s:
        n = s.execute(text("SELECT COUNT(*) AS c FROM public.outreach_messages")).mappings().one()["c"]
        assert n == 0


@pytest.mark.skipif(not _HAS_RETURNING, reason="endpoint uses INSERT ... RETURNING (needs SQLite >= 3.35)")
def test_promote_twice_second_call_is_409(Session):
    _seed(Session, status="approved")
    c = _client()
    assert c.post("/api/admin/prospects/cand-1/promote").status_code == 200
    # candidate is now 'promoted' → a second promote is rejected
    assert c.post("/api/admin/prospects/cand-1/promote").status_code == 409
