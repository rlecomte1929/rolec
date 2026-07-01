"""Unit tests for claim-level RAG error localization.

Covers the three classifications on small synthetic inputs, the grounding
override, the aggregate, and an end-to-end hermetic run of the CLI over the
immigration golden set.
"""
from __future__ import annotations

import os
import sys

import pytest

from backend.eval.rag_error_localization import (
    GENERATOR_HALLUCINATION,
    GROUNDED,
    LABELS,
    RETRIEVER_MISS,
    aggregate_localization,
    localize_step,
)

# scripts/ is on sys.path as a flat dir for the CLI import (mirrors
# test_eval_rag_context_precision.py).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SCRIPTS = os.path.join(_REPO_ROOT, "backend", "scripts")
for _p in (_REPO_ROOT, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# localize_step — the three classifications
# ---------------------------------------------------------------------------


def test_grounded_when_gold_support_retrieved():
    assert (
        localize_step(
            step="s1",
            retrieved_ids=["c1", "c2"],
            corpus_ids=["c1", "c2", "c3"],
            gold_support_ids=["c1"],
        )
        == GROUNDED
    )


def test_retriever_miss_when_support_in_corpus_but_not_retrieved():
    assert (
        localize_step(
            step="s1",
            retrieved_ids=["c2", "c3"],
            corpus_ids=["c1", "c2", "c3"],
            gold_support_ids=["c1"],  # exists in corpus, not retrieved
        )
        == RETRIEVER_MISS
    )


def test_generator_hallucination_when_support_absent_from_corpus():
    assert (
        localize_step(
            step="s1",
            retrieved_ids=["c2", "c3"],
            corpus_ids=["c2", "c3"],
            gold_support_ids=["c1"],  # nowhere in the corpus
        )
        == GENERATOR_HALLUCINATION
    )


def test_empty_gold_is_hallucination():
    # A step claiming support it cannot name has no corpus backing.
    assert (
        localize_step(step="s", retrieved_ids=["c1"], corpus_ids=["c1"], gold_support_ids=[])
        == GENERATOR_HALLUCINATION
    )


# ---------------------------------------------------------------------------
# grounded override (the live-path seam)
# ---------------------------------------------------------------------------


def test_grounded_override_true_wins_even_without_overlap():
    assert (
        localize_step(
            step="s",
            retrieved_ids=["c9"],
            corpus_ids=["c1", "c9"],
            gold_support_ids=["c1"],
            grounded=True,
        )
        == GROUNDED
    )


def test_grounded_override_false_localizes_to_retriever_miss():
    assert (
        localize_step(
            step="s",
            retrieved_ids=["c1"],  # would be grounded by the heuristic
            corpus_ids=["c1", "c2"],
            gold_support_ids=["c2"],
            grounded=False,
        )
        == RETRIEVER_MISS
    )


# ---------------------------------------------------------------------------
# aggregate_localization
# ---------------------------------------------------------------------------


def test_aggregate_counts_and_rates():
    labels = [GROUNDED, GROUNDED, RETRIEVER_MISS, GENERATOR_HALLUCINATION]
    agg = aggregate_localization(labels)
    assert agg["n"] == 4
    assert agg["grounded"] == 2
    assert agg["retriever_miss"] == 1
    assert agg["generator_hallucination"] == 1
    assert agg["grounded_rate"] == 0.5
    assert agg["retriever_miss_rate"] == 0.25
    assert agg["generator_hallucination_rate"] == 0.25


def test_aggregate_accepts_result_dicts():
    results = [{"localization": GROUNDED}, {"localization": RETRIEVER_MISS}]
    agg = aggregate_localization(results)
    assert agg["n"] == 2
    assert agg["grounded"] == 1 and agg["retriever_miss"] == 1


def test_aggregate_empty_is_zero_not_divide_error():
    agg = aggregate_localization([])
    assert agg["n"] == 0
    assert agg["grounded_rate"] == 0.0


def test_aggregate_rejects_unknown_label():
    with pytest.raises(ValueError):
        aggregate_localization(["not_a_label"])


# ---------------------------------------------------------------------------
# CLI end-to-end (hermetic) over the real golden set
# ---------------------------------------------------------------------------


def test_cli_offline_run_over_golden_set():
    import eval_rag_error_localization as elc

    queries = elc.load_queries(str(elc.DEFAULT_QUERIES))
    corpus = elc.load_corpus(str(elc.DEFAULT_CHUNKS))
    results = elc.evaluate_offline(queries, corpus, k=5)
    report = elc.build_report(results, k=5, mode="offline")

    split = report["split"]
    # Every step lands in exactly one bucket and the buckets sum to n.
    assert split["n"] == len(queries)
    assert (
        split["grounded"] + split["retriever_miss"] + split["generator_hallucination"]
        == split["n"]
    )
    # The golden set's gold ids all live in the corpus, so no step can be a
    # hallucination offline — the eval localizes purely between grounded and
    # retriever_miss. (Hallucination is exercised by the synthetic tests above
    # and by the --live path.)
    assert split["generator_hallucination"] == 0
    assert all(r["localization"] in LABELS for r in results)


def test_lexical_retrieve_is_deterministic():
    import eval_rag_error_localization as elc

    chunks = [
        {"chunk_id": "a", "body": "passport and residence registration document"},
        {"chunk_id": "b", "body": "totally unrelated penguins antarctic"},
        {"chunk_id": "c", "body": "residence registration form"},
    ]
    out1 = elc.lexical_retrieve("residence registration document", chunks, k=2)
    out2 = elc.lexical_retrieve("residence registration document", chunks, k=2)
    assert out1 == out2
    assert "b" not in out1  # the off-topic chunk must not rank in the top-2
