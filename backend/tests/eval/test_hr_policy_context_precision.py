# WS-C — unit tests for the HR-policy context-precision evaluator (deliverable 3).
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "backend" / "scripts" / "eval_hr_policy_context_precision.py"
_QUERIES = _REPO_ROOT / "backend" / "tests" / "fixtures" / "rag_eval" / "hr_policy" / "queries.jsonl"
_CHUNKS = _REPO_ROOT / "backend" / "tests" / "fixtures" / "rag_eval" / "hr_policy" / "chunks.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_hr_policy_ctx", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fixtures_exist_and_have_min_expected_chunks():
    mod = _load_module()
    queries = mod.load_queries(str(_QUERIES))
    assert len(queries) >= 15
    for q in queries:
        assert len(q.expected_chunk_ids) >= 3


def test_context_precision_is_a_real_number_on_seed():
    mod = _load_module()
    queries = mod.load_queries(str(_QUERIES))
    chunks = mod._load_chunks(str(_CHUNKS))
    retriever = mod.LexicalPolicyRetriever(chunks)
    results = mod.evaluate(queries, retriever, k=5)
    report = mod.aggregate_report(results, metric_name="precision_at_k", threshold=0.5)
    # A non-trivial, deterministic number (not 0, not necessarily 1.0).
    assert 0.0 < report["aggregate"] <= 1.0
    assert report["queries_evaluated"] == len(queries)


def test_retriever_is_deterministic():
    mod = _load_module()
    chunks = mod._load_chunks(str(_CHUNKS))
    queries = mod.load_queries(str(_QUERIES))
    r1 = mod.LexicalPolicyRetriever(chunks)
    r2 = mod.LexicalPolicyRetriever(chunks)
    q = queries[0]
    r1.set_current_query(q)
    r2.set_current_query(q)
    assert [c.chunk_id for c in r1.retrieve(q.query_text, k=5)] == \
           [c.chunk_id for c in r2.retrieve(q.query_text, k=5)]
