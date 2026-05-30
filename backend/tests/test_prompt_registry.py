"""
Tests for backend/app/services/prompt_registry.py — Parker Step D.

Covers:
- _pick_arm distribution (seeded, ~canary_share over many draws)
- render_user_message {{var}} substitution + None passthrough
- get_active_prompt returns the prod row (canary_arm='prod')
- canary served when canary_share == 1.0 (canary_arm='canary')
- promote() demotes the prior prod to 'archived' (one-prod invariant)
- the partial unique index rejects a 2nd prod insert
- get_active_prompt returns None when the table is absent (consumer-fallback)

Schema is built via a SQLite-compatible fixture; functions take an explicit
session so they never touch the prod engine.
"""
from __future__ import annotations

import os
import random
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import prompt_registry as pr  # noqa: E402


_SCHEMA = [
    """
    CREATE TABLE prompt_versions (
      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
      task_key TEXT NOT NULL,
      version INTEGER NOT NULL,
      system_prompt TEXT NOT NULL,
      user_template TEXT,
      model_name TEXT NOT NULL,
      temperature NUMERIC NOT NULL DEFAULT 0.0,
      max_tokens INTEGER NOT NULL DEFAULT 1024,
      status TEXT NOT NULL DEFAULT 'draft',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      created_by TEXT,
      notes TEXT,
      UNIQUE (task_key, version)
    )
    """,
    "CREATE UNIQUE INDEX ux_one_prod ON prompt_versions(task_key) WHERE status='prod'",
    """
    CREATE TABLE prompt_routing (
      task_key TEXT PRIMARY KEY,
      canary_share NUMERIC NOT NULL DEFAULT 0.0
    )
    """,
]


def _make_session(with_schema: bool = True):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if with_schema:
        with engine.begin() as conn:
            for stmt in _SCHEMA:
                conn.execute(text(stmt))
    Session = sessionmaker(bind=engine)
    return Session()


@pytest.fixture
def session():
    s = _make_session()
    try:
        yield s
    finally:
        s.close()


# ── Pure helpers ──────────────────────────────────────────────────────────────


def test_pick_arm_extremes():
    rng = random.Random(0)
    assert pr._pick_arm(0.0, rng) == "prod"
    assert pr._pick_arm(1.0, rng) == "canary"
    assert pr._pick_arm(-5, rng) == "prod"
    assert pr._pick_arm("bad", rng) == "prod"


def test_pick_arm_distribution_seeded():
    rng = random.Random(42)
    draws = [pr._pick_arm(0.1, rng) for _ in range(10000)]
    share = draws.count("canary") / len(draws)
    assert 0.085 <= share <= 0.115, share


def test_render_user_message_substitution():
    out = pr.render_user_message(
        "DOC (truncated={{truncated}}):\n{{document_text}}",
        {"truncated": True, "document_text": "hello"},
    )
    assert out == "DOC (truncated=True):\nhello"


def test_render_user_message_missing_var_is_empty():
    assert pr.render_user_message("a={{x}}b", {}) == "a=b"


def test_render_user_message_none_passthrough():
    assert pr.render_user_message(None, {"x": 1}) is None


# ── Read path ─────────────────────────────────────────────────────────────────


def test_create_and_get_active_prompt(session):
    created = pr.create_version(
        task_key="policy_extraction",
        system_prompt="SYS",
        model_name="claude-sonnet-4-6",
        user_template="t={{truncated}}",
        max_tokens=4096,
        status="prod",
        session=session,
    )
    assert created["version"] == 1
    active = pr.get_active_prompt("policy_extraction", session=session)
    assert active is not None
    assert active.system_prompt == "SYS"
    assert active.model_name == "claude-sonnet-4-6"
    assert active.max_tokens == 4096
    assert active.canary_arm == "prod"
    assert active.user_template == "t={{truncated}}"


def test_get_active_prompt_none_when_no_prod(session):
    pr.create_version(
        task_key="policy_extraction",
        system_prompt="SYS",
        model_name="m",
        status="draft",
        session=session,
    )
    assert pr.get_active_prompt("policy_extraction", session=session) is None


def test_canary_served_when_share_one(session):
    pr.create_version(
        task_key="t",
        system_prompt="PROD",
        model_name="m",
        status="prod",
        session=session,
    )
    pr.create_version(
        task_key="t",
        system_prompt="CANARY",
        model_name="m2",
        status="canary",
        session=session,
    )
    pr.set_canary_share("t", 1.0, session=session)
    active = pr.get_active_prompt("t", session=session)
    assert active is not None
    assert active.canary_arm == "canary"
    assert active.system_prompt == "CANARY"
    assert active.model_name == "m2"


def test_canary_ignored_when_share_zero(session):
    pr.create_version(task_key="t", system_prompt="PROD", model_name="m", status="prod", session=session)
    pr.create_version(task_key="t", system_prompt="CANARY", model_name="m2", status="canary", session=session)
    pr.set_canary_share("t", 0.0, session=session)
    active = pr.get_active_prompt("t", session=session)
    assert active is not None
    assert active.canary_arm == "prod"
    assert active.system_prompt == "PROD"


# ── Promotion / invariants ────────────────────────────────────────────────────


def test_promote_demotes_prior_prod(session):
    v1 = pr.create_version(task_key="t", system_prompt="V1", model_name="m", status="prod", session=session)
    v2 = pr.create_version(task_key="t", system_prompt="V2", model_name="m", status="draft", session=session)
    pr.promote(v2["id"], "prod", session=session)

    active = pr.get_active_prompt("t", session=session)
    assert active is not None and active.system_prompt == "V2"

    rows = pr.list_versions("t", session=session)
    by_id = {r["id"]: r for r in rows}
    assert by_id[v1["id"]]["status"] == "archived"
    assert by_id[v2["id"]]["status"] == "prod"


def test_partial_unique_rejects_second_prod(session):
    pr.create_version(task_key="t", system_prompt="V1", model_name="m", status="prod", session=session)
    # Raw insert of a 2nd prod (bypassing create_version's demote) must violate
    # the partial unique index.
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO prompt_versions (task_key, version, system_prompt, model_name, status) "
                "VALUES ('t', 99, 'X', 'm', 'prod')"
            )
        )
        session.commit()


def test_get_active_prompt_none_when_table_missing():
    s = _make_session(with_schema=False)
    try:
        assert pr.get_active_prompt("policy_extraction", session=s) is None
    finally:
        s.close()


# ── Seed reproduces literals byte-for-byte ────────────────────────────────────

_MIGRATION = os.path.join(
    _REPO_ROOT, "supabase", "migrations", "20260601050000_prompt_registry.sql"
)


def test_seed_reproduces_extractor_literal_byte_for_byte():
    from backend.app.services.llm_policy_extractor import SYSTEM_PROMPT
    sql = open(_MIGRATION, encoding="utf-8").read()
    assert SYSTEM_PROMPT in sql, "extractor SYSTEM_PROMPT drifted from the seed"


def test_seed_reproduces_rag_literal_byte_for_byte():
    from backend.app.services.policy_assistant_rag_engine import SYSTEM_PROMPT
    sql = open(_MIGRATION, encoding="utf-8").read()
    assert SYSTEM_PROMPT in sql, "rag SYSTEM_PROMPT drifted from the seed"
