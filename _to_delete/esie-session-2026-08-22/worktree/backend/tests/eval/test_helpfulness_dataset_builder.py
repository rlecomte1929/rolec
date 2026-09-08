"""WS-E — tests for the helpfulness → golden-set candidate builder.

Pure-function tests over synthetic in-memory rows (no DB).
"""
from __future__ import annotations

import json

from backend.app.services import helpfulness_dataset_builder as b


def _row(query_hash, helpful, trace, company="co-1"):
    return {
        "query_hash": query_hash,
        "helpful": helpful,
        "trace_session_id": trace,
        "company_id": company,
    }


def test_groups_by_query_hash_and_classifies():
    rows = [
        _row("hashA", True, "t1"),
        _row("hashA", True, "t2"),
        _row("hashA", False, "t3"),  # net +1 → positive
        _row("hashB", False, "t4"),
        _row("hashB", False, "t5"),  # net -2 → negative
        _row("hashC", True, "t6"),
        _row("hashC", False, "t7"),  # net 0 → contested
    ]
    cands = b.build_candidates(rows)
    by_prompt = {c.prompt: c for c in cands}
    assert by_prompt["hashA"].label == b.LABEL_POSITIVE
    assert by_prompt["hashA"].helpful_votes == 2
    assert by_prompt["hashA"].unhelpful_votes == 1
    assert by_prompt["hashA"].net_score == 1
    assert by_prompt["hashB"].label == b.LABEL_NEGATIVE
    assert by_prompt["hashC"].label == b.LABEL_CONTESTED
    # All candidates are flagged for human curation.
    assert all(c.needs_review for c in cands)
    assert all(c.source == "end_user_helpfulness" for c in cands)


def test_min_votes_drops_thin_groups():
    rows = [_row("hashA", True, "t1"), _row("hashB", True, "t2"), _row("hashB", True, "t3")]
    cands = b.build_candidates(rows, min_votes=2)
    prompts = {c.prompt for c in cands}
    assert prompts == {"hashB"}  # hashA had only 1 vote


def test_deterministic_order_and_no_fabrication():
    assert b.build_candidates([]) == []
    rows = [_row("hashZ", True, "t1"), _row("hashA", True, "t2")]
    cands = b.build_candidates(rows)
    assert [c.prompt for c in cands] == ["hashA", "hashZ"]  # sorted


def test_rows_without_query_hash_are_skipped():
    rows = [{"helpful": True, "trace_session_id": "t1"}, _row("hashA", True, "t2")]
    cands = b.build_candidates(rows)
    assert [c.prompt for c in cands] == ["hashA"]


def test_to_jsonl_shape():
    rows = [_row("hashA", True, "t1"), _row("hashA", True, "t2")]
    cands = b.build_candidates(rows)
    line = b.to_jsonl(cands)
    obj = json.loads(line)
    assert obj["prompt"] == "hashA"
    assert obj["label"] == b.LABEL_POSITIVE
    assert obj["needs_review"] is True
    assert obj["metadata"]["helpful_votes"] == 2
    assert obj["metadata"]["company_id"] == "co-1"
    assert obj["metadata"]["trace_session_ids"] == ["t1", "t2"]
