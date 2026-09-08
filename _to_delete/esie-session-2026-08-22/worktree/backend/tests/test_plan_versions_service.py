"""
W1-2 + W1-3 — tests for plan_versions_service.persist_generated_plan.

Backed by an in-memory SQLite mirror of the migration's tables. Verifies:
  - idempotency: identical regenerations (same structural hash) → 1 version;
  - a changed roadmap → a new immutable version (append-only, version_no++);
  - case_plans tracks current_version_id + version_count;
  - retrieval telemetry: a run + per-chunk rows are persisted and linked;
  - best-effort: a broken session returns None, never raises.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.services import plan_versions_service as svc

_SCHEMA = """
CREATE TABLE case_plans (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE, current_version_id TEXT,
  version_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE retrieval_runs (
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL, corridor TEXT, query_text TEXT,
  top_k INTEGER, params TEXT, chunk_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE plan_versions (
  id TEXT PRIMARY KEY, case_plan_id TEXT NOT NULL, case_id TEXT NOT NULL,
  version_no INTEGER NOT NULL, plan_json TEXT NOT NULL, plan_hash TEXT NOT NULL,
  model TEXT, prompt_version_id TEXT, retrieval_run_id TEXT, corridor TEXT,
  created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (case_id, version_no)
);
CREATE TABLE retrieval_run_chunks (
  id TEXT PRIMARY KEY, retrieval_run_id TEXT NOT NULL, case_id TEXT NOT NULL,
  chunk_id TEXT, rank INTEGER, raw_score REAL, adjusted_score REAL,
  trust_tier INTEGER, freshness REAL, source_url TEXT
);
"""

_CASE = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in _SCHEMA.split(";"))):
            conn.execute(text(stmt))
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(svc, "SessionLocal", TestSession)
    return TestSession


def _plan(*titles, result="OK", corridor="FR-NO"):
    return {
        "result": result, "corridor": corridor, "pathway_type": "eea",
        "model": "claude-sonnet-4-6",
        "steps": [{"title": t, "instructions": f"do {t} now"} for t in titles],
        # volatile presentation fields that must NOT affect the structural hash:
        "as_of": "2026-06-10T00:00:00Z", "ai_roadmap_eligible": True,
    }


def test_identical_regeneration_is_idempotent(session_factory):
    p = _plan("Apply permit", "Register address")
    first = svc.persist_generated_plan(_CASE, p, created_by=_USER)
    assert first["created"] is True and first["version_no"] == 1

    # Same structure, different volatile field → must NOT create a new version.
    p2 = dict(p, as_of="2026-06-11T09:00:00Z")
    second = svc.persist_generated_plan(_CASE, p2, created_by=_USER)
    assert second["created"] is False and second["version_no"] == 1

    with session_factory() as db:
        n = db.execute(text("SELECT COUNT(*) FROM plan_versions WHERE case_id = :c"),
                       {"c": _CASE}).scalar()
        vc = db.execute(text("SELECT version_count FROM case_plans WHERE case_id = :c"),
                        {"c": _CASE}).scalar()
    assert n == 1 and vc == 1


def test_changed_roadmap_creates_new_version(session_factory):
    svc.persist_generated_plan(_CASE, _plan("Apply permit"), created_by=_USER)
    res = svc.persist_generated_plan(_CASE, _plan("Apply permit", "Open bank account"), created_by=_USER)
    assert res["created"] is True and res["version_no"] == 2

    with session_factory() as db:
        rows = db.execute(
            text("SELECT version_no FROM plan_versions WHERE case_id = :c ORDER BY version_no"),
            {"c": _CASE},
        ).fetchall()
        cur = db.execute(text("SELECT current_version_id FROM case_plans WHERE case_id = :c"),
                         {"c": _CASE}).scalar()
    assert [r[0] for r in rows] == [1, 2]
    assert cur == res["plan_version_id"]


def test_retrieval_telemetry_persisted_and_linked(session_factory):
    retrieval = {
        "query_text": "FR-NO permit", "top_k": 5,
        "params": {"min_similarity": 0.25},
        "chunks": [
            {"id": "chunk-a", "rank": 0, "raw_score": 0.9, "adjusted_score": 0.81,
             "trust_tier": 1, "freshness": 1.0, "source_url": "https://udi.no/a"},
            {"id": "chunk-b", "raw_score": 0.7, "adjusted_score": 0.6, "trust_tier": 2},
        ],
    }
    res = svc.persist_generated_plan(_CASE, _plan("Apply permit"), retrieval=retrieval, created_by=_USER)
    with session_factory() as db:
        run_id = db.execute(text("SELECT retrieval_run_id FROM plan_versions WHERE id = :i"),
                            {"i": res["plan_version_id"]}).scalar()
        assert run_id is not None
        cc = db.execute(text("SELECT chunk_count FROM retrieval_runs WHERE id = :r"),
                        {"r": run_id}).scalar()
        nchunks = db.execute(text("SELECT COUNT(*) FROM retrieval_run_chunks WHERE retrieval_run_id = :r"),
                             {"r": run_id}).scalar()
    assert cc == 2 and nchunks == 2


def test_legacy_text_created_by_is_dropped(session_factory):
    # A non-uuid id must not be written to the uuid created_by column.
    res = svc.persist_generated_plan(_CASE, _plan("Apply permit"), created_by="seed-emp-testingapril")
    with session_factory() as db:
        by = db.execute(text("SELECT created_by FROM plan_versions WHERE id = :i"),
                        {"i": res["plan_version_id"]}).scalar()
    assert by is None


def test_persistence_failure_returns_none(monkeypatch):
    # Broken SessionLocal → best-effort: returns None, never raises.
    class _Boom:
        def __call__(self):
            raise RuntimeError("db down")
    monkeypatch.setattr(svc, "SessionLocal", _Boom())
    assert svc.persist_generated_plan(_CASE, _plan("x")) is None
