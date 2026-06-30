"""P1 — tests for the groundedness gate-impact canary.

Pure-function tests over synthetic in-memory trace-row dicts (no DB) plus one
SQLite-backed test of the SQL rollup, exercising the gate predicate at its
boundaries and the helpfulness false-refusal join.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text

from backend.eval import gate_impact as gi


def _row(
    answer_kind="answer",
    verdict="grounded",
    score=0.9,
    verification_skipped=False,
    company="co-1",
    helpful=None,
):
    r = {
        "answer_kind": answer_kind,
        "grounding_verdict": verdict,
        "grounding_score": score,
        "verification_skipped": verification_skipped,
        "company_id": company,
    }
    if helpful is not None:
        r["helpful"] = helpful
    return r


# ── predicate boundaries ──────────────────────────────────────────────────


def test_score_exactly_at_min_is_not_refused():
    # engine uses `< min`, so a score equal to min is grounded enough.
    assert gi.would_refuse(_row(verdict="partially_grounded", score=0.5), 0.5) is False


def test_score_below_min_is_refused():
    assert gi.would_refuse(_row(verdict="partially_grounded", score=0.49), 0.5) is True


def test_none_score_is_not_refused_when_verdict_ok():
    assert gi.would_refuse(_row(verdict="partially_grounded", score=None), 0.5) is False


def test_ungrounded_verdict_is_refused_regardless_of_score():
    assert gi.would_refuse(_row(verdict="ungrounded", score=0.99), 0.5) is True


def test_grounded_high_score_is_not_refused():
    assert gi.would_refuse(_row(verdict="grounded", score=0.95), 0.5) is False


def test_refusal_kind_is_never_gated():
    assert gi.would_refuse(_row(answer_kind="refusal_out_of_policy", verdict="ungrounded"), 0.5) is False


def test_verification_skipped_fails_open():
    assert gi.would_refuse(_row(verdict="ungrounded", verification_skipped=True), 0.5) is False


# ── estimate_gate_impact ───────────────────────────────────────────────────


def test_estimate_counts_and_rate():
    rows = [
        _row(verdict="grounded", score=0.9),              # keep
        _row(verdict="ungrounded", score=0.9),            # refuse
        _row(verdict="partially_grounded", score=0.3),    # refuse (low score)
        _row(verdict="partially_grounded", score=0.6),    # keep
        _row(answer_kind="refusal_validation_failed"),    # not an answer
    ]
    out = gi.estimate_gate_impact(rows, 0.5)
    assert out["n_answers"] == 4
    assert out["n_would_refuse"] == 2
    assert out["would_refuse_rate"] == 0.5
    assert out["min_score"] == 0.5
    assert out["by_verdict"] == {"ungrounded": 1, "partially_grounded": 1}


def test_estimate_empty_is_zero_not_crash():
    out = gi.estimate_gate_impact([], 0.5)
    assert out["n_answers"] == 0
    assert out["would_refuse_rate"] == 0.0


def test_by_company_breakdown():
    rows = [
        _row(company="a", verdict="ungrounded"),
        _row(company="a", verdict="grounded"),
        _row(company="b", verdict="ungrounded"),
    ]
    out = gi.estimate_gate_impact(rows, 0.5, by_company=True)
    assert out["by_company"]["a"] == {"n_answers": 2, "n_would_refuse": 1}
    assert out["by_company"]["b"] == {"n_answers": 1, "n_would_refuse": 1}


# ── threshold sweep ────────────────────────────────────────────────────────


def test_sweep_is_monotonic_non_decreasing():
    rows = [
        _row(verdict="partially_grounded", score=0.2),
        _row(verdict="partially_grounded", score=0.4),
        _row(verdict="partially_grounded", score=0.6),
        _row(verdict="grounded", score=0.95),
    ]
    results = gi.sweep(rows)  # [0.3, 0.5, 0.7]
    refused = [r["n_would_refuse"] for r in results]
    assert refused == [1, 2, 3]
    assert [r["min_score"] for r in results] == [0.3, 0.5, 0.7]


# ── false-refusal helpfulness signal ───────────────────────────────────────


def test_false_refusal_signal_counts_helpful_votes():
    rows = [
        _row(verdict="ungrounded", helpful=True),    # would-refuse + helpful => false refusal
        _row(verdict="ungrounded", helpful=False),   # would-refuse + unhelpful
        _row(verdict="ungrounded", helpful=None),    # would-refuse + no vote
        _row(verdict="grounded", helpful=True),      # kept (not would-refuse) — ignored
    ]
    out = gi.false_refusal_signal(rows, 0.5)
    assert out["n_would_refuse"] == 3
    assert out["n_would_refuse_helpful"] == 1
    assert out["n_would_refuse_unhelpful"] == 1
    assert out["n_would_refuse_no_vote"] == 1
    assert out["false_refusal_rate"] == round(1 / 3, 4)


def test_false_refusal_signal_empty():
    out = gi.false_refusal_signal([], 0.5)
    assert out["n_would_refuse"] == 0
    assert out["false_refusal_rate"] == 0.0


# ── default min score sourced from the engine constant ─────────────────────


def test_default_min_score_matches_engine_constant():
    assert gi.default_min_score() == 0.5


# ── SQL rollup (SQLite) ────────────────────────────────────────────────────


def _make_db():
    """Minimal MiscMixin instance backed by in-memory SQLite + the two tables."""
    from backend.db.misc import MiscMixin

    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "CREATE TABLE policy_assistant_traces ("
            "id TEXT PRIMARY KEY, company_id TEXT, feature_key TEXT, "
            "answer_kind TEXT, grounding_verdict TEXT, grounding_score REAL, "
            "verification_skipped BOOLEAN, created_at TEXT)"
        ))
        c.execute(text(
            "CREATE TABLE policy_answer_helpfulness ("
            "id TEXT PRIMARY KEY, trace_session_id TEXT, helpful BOOLEAN)"
        ))

    class _Db(MiscMixin):
        def __init__(self, eng):
            self.engine = eng

    return _Db(engine), engine


def _insert_trace(engine, tid, **kw):
    row = {
        "id": tid,
        "company_id": kw.get("company_id", "co-1"),
        "feature_key": kw.get("feature_key", "policy_assistant"),
        "answer_kind": kw.get("answer_kind", "answer"),
        "grounding_verdict": kw.get("grounding_verdict", "grounded"),
        "grounding_score": kw.get("grounding_score", 0.9),
        "verification_skipped": kw.get("verification_skipped", False),
        "created_at": kw.get("created_at", "2026-06-01T00:00:00"),
    }
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO policy_assistant_traces "
            "(id, company_id, feature_key, answer_kind, grounding_verdict, "
            "grounding_score, verification_skipped, created_at) VALUES "
            "(:id, :company_id, :feature_key, :answer_kind, :grounding_verdict, "
            ":grounding_score, :verification_skipped, :created_at)"
        ), row)


def test_rollup_matches_pure_predicate_and_helpfulness_join():
    db, engine = _make_db()
    _insert_trace(engine, "t1", grounding_verdict="grounded", grounding_score=0.9)
    _insert_trace(engine, "t2", grounding_verdict="ungrounded", grounding_score=0.9)
    _insert_trace(engine, "t3", grounding_verdict="partially_grounded", grounding_score=0.3)
    _insert_trace(engine, "t4", answer_kind="refusal_out_of_policy")
    _insert_trace(engine, "t5", grounding_verdict="ungrounded", verification_skipped=True)
    # t2 (would-refuse) got a helpful vote => candidate false refusal.
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO policy_answer_helpfulness (id, trace_session_id, helpful) "
            "VALUES ('h1', 't2', 1)"
        ))

    out = db.get_gate_impact_rollup(min_score=0.5)
    assert out["n_answers"] == 4          # t1,t2,t3,t5 (t4 is a refusal)
    assert out["n_would_refuse"] == 2     # t2 (ungrounded) + t3 (low score); t5 fails open
    assert out["would_refuse_rate"] == 0.5
    assert out["n_would_refuse_helpful"] == 1
    assert out["by_verdict"] == {"ungrounded": 1, "low_score": 1}


def test_rollup_missing_table_returns_zero():
    from backend.db.misc import MiscMixin

    engine = create_engine("sqlite://")  # no tables created

    class _Db(MiscMixin):
        def __init__(self, eng):
            self.engine = eng

    out = _Db(engine).get_gate_impact_rollup(min_score=0.5)
    assert out["n_answers"] == 0
    assert out["n_would_refuse"] == 0
    assert out["min_score"] == 0.5
