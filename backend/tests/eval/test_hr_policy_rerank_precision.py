"""
P4 — the reranker must not regress, and should lift, HR-policy context-precision
on the committed golden seed set (fully offline lexical eval).

Asserts precision@5 ON >= precision@5 OFF (hard gate) and, on the current seed
corpus, a strict improvement (demonstrates the second pass earns its keep).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "backend" / "scripts" / "eval_hr_policy_context_precision.py"
_QUERIES = _REPO_ROOT / "backend" / "tests" / "fixtures" / "rag_eval" / "hr_policy" / "queries.jsonl"
_CHUNKS = _REPO_ROOT / "backend" / "tests" / "fixtures" / "rag_eval" / "hr_policy" / "chunks.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_hr_policy_ctx_rr", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _aggregates():
    mod = _load_module()
    queries = mod.load_queries(str(_QUERIES))
    chunks = mod._load_chunks(str(_CHUNKS))
    retriever = mod.LexicalPolicyRetriever(chunks)
    off = mod.aggregate_report(
        mod.evaluate(queries, retriever, k=5, rerank=False),
        metric_name="precision_at_k", threshold=0.5,
    )["aggregate"]
    on = mod.aggregate_report(
        mod.evaluate(queries, retriever, k=5, rerank=True),
        metric_name="precision_at_k", threshold=0.5,
    )["aggregate"]
    return off, on


def test_rerank_does_not_regress_precision():
    off, on = _aggregates()
    assert on >= off, f"reranker regressed precision: ON={on} < OFF={off}"


def test_rerank_lifts_precision_on_seed_set():
    off, on = _aggregates()
    assert on > off, f"reranker did not lift precision on seed set: ON={on} OFF={off}"


def test_rerank_is_deterministic():
    off1, on1 = _aggregates()
    off2, on2 = _aggregates()
    assert (off1, on1) == (off2, on2)
