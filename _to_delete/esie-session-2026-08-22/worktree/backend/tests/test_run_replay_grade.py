"""
Phase 1, Slice 3 — the offline replay grader.

Reads masked replay records (ai_replay_store) and computes the aggregate quality
metrics that feed rag_eval_reports — most importantly OUTCOME_ACCURACY, the metric
that has a 0.90 threshold in METRIC_SPECS but had no evaluator producing it.

Faithfulness oracle (per the locked design): a roadmap step is "accurate" iff the
pipeline's own factual_verifier judged it supported by + correctly cited to the
retrieved authority chunks. The grader aggregates those stored per-step verdicts;
it does not re-run the LLM. RULE_NOT_FOUND is a coverage outcome, not an accuracy
failure, so it is excluded from the outcome_accuracy denominator and reported
separately.
"""
from __future__ import annotations

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.eval.run_replay_grade import grade_replay_records


def _roadmap_record(corridor, result, approved, steps):
    return {
        "feature_key": "rag_roadmap",
        "corridor": corridor,
        "result": result,
        "approved": 1 if approved else 0,
        "output_masked": json.dumps(
            {"result": result, "approved": approved, "corridor": corridor, "steps": steps}
        ),
    }


def _step(supported, citation_ok):
    return {"order": 1, "title": "x", "verification": {"supported": supported, "citation_ok": citation_ok}}


def test_outcome_accuracy_counts_approved_among_produced_roadmaps():
    records = [
        # OK + every step supported → approved (accurate)
        _roadmap_record("IN_DE", "OK", True, [_step(True, True), _step(True, True)]),
        # OK but one step unsupported → not approved (inaccurate)
        _roadmap_record("IN_DE", "OK", False, [_step(True, True), _step(False, False)]),
        # RULE_NOT_FOUND → coverage outcome, excluded from accuracy denominator
        _roadmap_record("JP_NO", "RULE_NOT_FOUND", False, []),
    ]

    report = grade_replay_records(records)

    # 1 approved of 2 produced (OK) roadmaps.
    assert report["aggregate"] == 0.5
    assert report["extra"]["n_ok"] == 2
    assert report["extra"]["n_rule_not_found"] == 1
    # 3 of 4 OK-roadmap steps supported; 3 of 4 correctly cited.
    assert report["extra"]["step_support_rate"] == 0.75
    assert report["extra"]["citation_validity"] == 0.75


def test_by_corridor_breakdown():
    records = [
        _roadmap_record("IN_DE", "OK", True, [_step(True, True)]),
        _roadmap_record("FR_NO", "OK", False, [_step(False, False)]),
    ]

    report = grade_replay_records(records)

    assert report["by_corridor"]["IN_DE"] == 1.0
    assert report["by_corridor"]["FR_NO"] == 0.0


def test_empty_input_is_safe():
    report = grade_replay_records([])
    assert report["aggregate"] == 0.0
    assert report["extra"]["n_ok"] == 0


def test_end_to_end_persist_then_grade_reproduces():
    """Plan verification #1: a generation persisted via ai_replay_store reads back
    and grades correctly — and PII masking of the output never breaks gradeability."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import StaticPool

    from backend.app.services.ai_replay_store import (
        list_replay_records,
        persist_replay_record,
    )

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE ai_replay_records ("
            "id TEXT PRIMARY KEY, trace_id TEXT, feature_key TEXT, corridor TEXT, "
            "query_masked TEXT, output_masked TEXT, retrieved_chunk_ids TEXT DEFAULT '[]', "
            "prompt_version_id TEXT, canary_arm TEXT, result TEXT, approved INTEGER DEFAULT 0, "
            "created_at TEXT NOT NULL)"
        ))

    # An approved roadmap whose step description carries an email (PII) — masking
    # must redact it without destroying the verification structure the grader reads.
    persist_replay_record(
        engine=eng, trace_id="t1", feature_key="rag_roadmap", corridor="IN_DE",
        query="Blue Card", result="OK", approved=True,
        retrieved_chunk_ids=["c1"],
        output={"result": "OK", "approved": True, "corridor": "IN_DE",
                "steps": [{"order": 1, "title": "Apply; contact anna@example.com",
                           "verification": {"supported": True, "citation_ok": True}}]},
    )
    persist_replay_record(
        engine=eng, trace_id="t2", feature_key="rag_roadmap", corridor="IN_DE",
        query="Blue Card spouse", result="OK", approved=False,
        retrieved_chunk_ids=["c2"],
        output={"result": "OK", "approved": False, "corridor": "IN_DE",
                "steps": [{"order": 1, "title": "x",
                           "verification": {"supported": False, "citation_ok": False}}]},
    )

    records = list_replay_records(engine=eng, feature_key="rag_roadmap")
    report = grade_replay_records(records)

    assert report["aggregate"] == 0.5  # 1 approved of 2 produced
    assert "anna@example.com" not in json.dumps(records)  # PII masked at rest
    assert report["extra"]["n_ok"] == 2
