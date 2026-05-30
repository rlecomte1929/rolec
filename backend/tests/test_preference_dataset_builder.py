"""
Tests for backend/app/services/preference_dataset_builder.py — Parker Step E.

An in-memory SQLite DB stands in for the prompt registry + trace + feedback
tables. We exercise pair construction (edited + cross-arm), win-rate math (Wilson
CI), FK enforcement on prompt_versions, and the JSONL writer.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import preference_dataset_builder as pdb  # noqa: E402
from backend.app.services.preference_dataset_builder import (  # noqa: E402
    DPOPair,
    build_dpo_pairs,
    compute_win_rates,
    wilson_interval,
)
from backend.scripts.export_preference_dataset import write_jsonl  # noqa: E402


_SCHEMA = [
    """
    CREATE TABLE prompt_versions (
      id TEXT PRIMARY KEY,
      task_key TEXT NOT NULL,
      version INTEGER NOT NULL,
      system_prompt TEXT NOT NULL,
      model_name TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'prod'
    )
    """,
    """
    CREATE TABLE policy_assistant_traces (
      id TEXT PRIMARY KEY,
      session_id TEXT,
      query_hash TEXT NOT NULL,
      company_id TEXT NOT NULL,
      prompt_version_id TEXT,
      canary_arm TEXT,
      created_at TEXT
    )
    """,
    """
    CREATE TABLE ai_human_feedback (
      id TEXT PRIMARY KEY,
      trace_session_id TEXT NOT NULL,
      reviewer_user_id TEXT NOT NULL,
      verdict TEXT NOT NULL,
      edited_output_json TEXT,
      comment TEXT,
      prompt_version_id TEXT REFERENCES prompt_versions(id),
      canary_arm TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      UNIQUE (trace_session_id, reviewer_user_id)
    )
    """,
]


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):  # enforce FKs in SQLite
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    with engine.begin() as conn:
        for stmt in _SCHEMA:
            conn.execute(text(stmt))
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _seed_version(s, vid, task_key="policy_assistant_answer", version=1, status="prod"):
    s.execute(
        text(
            "INSERT INTO prompt_versions (id, task_key, version, system_prompt, model_name, status) "
            "VALUES (:id, :tk, :v, 'SYS', 'm', :st)"
        ),
        {"id": vid, "tk": task_key, "v": version, "st": status},
    )


def _seed_trace(s, tid, query_hash, prompt_version_id, canary_arm):
    s.execute(
        text(
            "INSERT INTO policy_assistant_traces (id, query_hash, company_id, prompt_version_id, canary_arm) "
            "VALUES (:id, :qh, 'co-1', :pvid, :arm)"
        ),
        {"id": tid, "qh": query_hash, "pvid": prompt_version_id, "arm": canary_arm},
    )


def _seed_feedback(s, fid, tid, reviewer, verdict, pvid, arm, edited=None):
    s.execute(
        text(
            "INSERT INTO ai_human_feedback "
            "(id, trace_session_id, reviewer_user_id, verdict, edited_output_json, prompt_version_id, canary_arm) "
            "VALUES (:id, :tid, :r, :v, :e, :pvid, :arm)"
        ),
        {"id": fid, "tid": tid, "r": reviewer, "v": verdict, "e": edited, "pvid": pvid, "arm": arm},
    )


# ── Pair construction ─────────────────────────────────────────────────────────


def test_edited_verdict_yields_pair_with_edited_text(db):
    _seed_version(db, "v-prod")
    _seed_trace(db, "t1", "hashA", "v-prod", "prod")
    _seed_feedback(
        db, "f1", "t1", "rev-1", "edited", "v-prod", "prod",
        edited=json.dumps({"answer": "the corrected answer"}),
    )
    db.commit()

    pairs = build_dpo_pairs("policy_assistant_answer", min_pairs=1, session=db)
    assert len(pairs) == 1
    assert pairs[0].source == "edited"
    assert "corrected answer" in pairs[0].chosen
    assert pairs[0].prompt == "hashA"


def test_cross_arm_pair_from_same_query_hash(db):
    _seed_version(db, "v-prod", status="prod", version=1)
    _seed_version(db, "v-canary", status="canary", version=2)
    _seed_trace(db, "t-prod", "hashB", "v-prod", "prod")
    _seed_trace(db, "t-canary", "hashB", "v-canary", "canary")
    _seed_feedback(db, "f-prod", "t-prod", "rev-1", "rejected", "v-prod", "prod")
    _seed_feedback(db, "f-canary", "t-canary", "rev-1", "approved", "v-canary", "canary")
    db.commit()

    pairs = build_dpo_pairs("policy_assistant_answer", min_pairs=1, session=db)
    cross = [p for p in pairs if p.source == "cross_arm"]
    assert len(cross) == 1
    assert cross[0].chosen_version_id == "v-canary"
    assert cross[0].rejected_version_id == "v-prod"


def test_empty_feedback_returns_no_pairs(db):
    assert build_dpo_pairs("policy_assistant_answer", min_pairs=0, session=db) == []


# ── Win rates ─────────────────────────────────────────────────────────────────


def test_compute_win_rates_math_and_ci(db):
    _seed_version(db, "v-prod")
    for i in range(8):
        _seed_trace(db, f"ta{i}", f"h{i}", "v-prod", "prod")
        _seed_feedback(db, f"fa{i}", f"ta{i}", f"r{i}", "approved", "v-prod", "prod")
    for i in range(2):
        _seed_trace(db, f"tr{i}", f"hr{i}", "v-prod", "prod")
        _seed_feedback(db, f"fr{i}", f"tr{i}", f"rr{i}", "rejected", "v-prod", "prod")
    db.commit()

    rates = compute_win_rates("policy_assistant_answer", session=db)
    wr = rates["v-prod"]
    assert wr.approvals == 8
    assert wr.total == 10
    assert wr.win_rate == pytest.approx(0.8)
    assert 0.0 <= wr.ci_low <= wr.win_rate <= wr.ci_high <= 1.0


def test_wilson_interval_zero_total():
    ci = wilson_interval(0, 0)
    assert ci == {"rate": 0.0, "low": 0.0, "high": 0.0}


# ── FK enforcement (acceptance criterion) ─────────────────────────────────────


def test_feedback_fk_to_prompt_versions_is_enforced(db):
    # No prompt_versions row 'ghost' exists → FK violation on insert.
    from sqlalchemy.exc import IntegrityError

    _seed_trace(db, "t-x", "hashX", "ghost", "prod")
    with pytest.raises(IntegrityError):
        _seed_feedback(db, "f-x", "t-x", "rev-1", "approved", "ghost", "prod")
        db.commit()


# ── JSONL writer ──────────────────────────────────────────────────────────────


def test_write_jsonl_well_formed(tmp_path):
    pairs = [
        DPOPair(
            prompt="hashA",
            chosen="good",
            rejected="bad",
            task_key="policy_assistant_answer",
            chosen_version_id="v1",
            rejected_version_id="v2",
            source="cross_arm",
        )
    ]
    out = tmp_path / "ds.jsonl"
    n = write_jsonl(pairs, out)
    assert n == 1
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["prompt"] == "hashA"
    assert obj["chosen"] == "good"
    assert obj["rejected"] == "bad"
    assert obj["metadata"]["source"] == "cross_arm"
