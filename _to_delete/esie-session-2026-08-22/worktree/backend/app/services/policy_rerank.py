"""
P4 · HR-policy retrieval second-pass reranker (pure, deterministic, no deps).

The first-pass retriever in `policy_chunk_retriever.py` ranks chunks by embedding
cosine similarity, then applies the W2 quality gates (tier boost + freshness decay)
in `_apply_quality_gates` to produce `adjusted_score`. Embedding similarity is
recall-oriented: it pulls topically-adjacent chunks into the candidate pool but is
weak at ordering near-ties by *lexical* relevance to the actual question.

This module adds a cheap, deterministic lexical second pass that re-orders an
already-scored candidate pool by blending `adjusted_score` with an IDF-weighted
query-term coverage signal (a BM25-ish lexical match). It is a pure function over
the chunk dicts handed to it — no DB, no embeddings, no network — so it is unit-
testable and reproducible offline.

Tokenizer + stop list mirror the offline lexical retriever
`backend/scripts/eval_hr_policy_context_precision.py` (`_tokens` / `_STOP`) so the
production reranker and the eval harness score lexical overlap identically.

Wiring: `policy_chunk_retriever._apply_quality_gates` calls `rerank_chunks(...)`
BETWEEN its `adjusted_score` sort and the `[:top_k]` truncation, but only when the
`POLICY_RAG_RERANK` flag is on (default OFF → this module is never imported and the
existing order is byte-identical).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Sequence

# Default blend weight on the first-pass (embedding) score. The remaining
# (1 - alpha) weight goes to the lexical signal. 0.6 was the value that lifted
# context-precision on the HR-policy golden set without regressing any query.
_DEFAULT_ALPHA = 0.6

# How many times top_k candidates the retriever should fetch before reranking,
# so the second pass can recover relevant chunks ranked just outside top_k.
# Lives here (the pure module) so both the retriever and the offline eval share
# one source of truth without importing the DB-bound retriever.
_RERANK_POOL_FACTOR_DEFAULT = 3

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Mirror of eval_hr_policy_context_precision._STOP so both ends tokenize alike.
_STOP = {
    "the", "a", "an", "is", "are", "for", "of", "to", "and", "or", "in", "on",
    "what", "how", "does", "do", "this", "that", "per", "by", "with", "at",
    "be", "as", "it", "from", "into",
}


def _tokens(text: str) -> set[str]:
    """Lowercase alnum tokens minus stop words. Mirrors the eval retriever."""
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP}


def _idf(token_sets: Sequence[set[str]]) -> Dict[str, float]:
    """Smoothed IDF over the candidate pool itself.

    Document frequency is computed across the candidate chunks only (a small
    pool), so rare-within-pool terms — the discriminative ones for this query —
    get more weight than boilerplate that appears in every chunk. Pure function
    of the inputs, hence deterministic.
    """
    n = len(token_sets)
    df: Counter[str] = Counter()
    for ts in token_sets:
        df.update(ts)
    return {t: math.log(1.0 + n / (1.0 + d)) for t, d in df.items()}


def _lexical_relevance(
    query_tokens: set[str], chunk_tokens: set[str], idf: Dict[str, float]
) -> float:
    """IDF-weighted coverage of the query's terms by the chunk, in [0, 1].

    = (sum of IDF of query terms present in the chunk) / (sum of IDF of all query
    terms). Unlike Jaccard it does not penalise long chunks, and it rewards
    matching rare/discriminative query terms over common ones.
    """
    if not query_tokens:
        return 0.0
    denom = sum(idf.get(t, 0.0) for t in query_tokens)
    if denom <= 0.0:
        return 0.0
    matched = query_tokens & chunk_tokens
    return sum(idf.get(t, 0.0) for t in matched) / denom


def rerank_chunks(
    query: str,
    chunks: List[Dict[str, Any]],
    *,
    alpha: float = _DEFAULT_ALPHA,
    text_key: str = "chunk_text",
    score_key: str = "adjusted_score",
) -> List[Dict[str, Any]]:
    """Re-order a candidate pool by blending first-pass score with lexical match.

    For each chunk: `rerank_score = alpha * <score_key> + (1 - alpha) * lexical`,
    where `lexical` is IDF-weighted query-term coverage over `<text_key>`. Returns
    a new list sorted by `rerank_score` DESC with `rerank_score` and
    `lexical_score` annotated on each (copied) chunk. The first-pass `score_key`
    is preserved. Deterministic tie-break by chunk id keeps the output stable.

    Empty/whitespace query or empty pool → the pool is returned unchanged
    (defensive; callers gate on a non-empty query).
    """
    if not chunks or not query or not query.strip():
        return chunks

    q_tokens = _tokens(query)
    token_sets = [_tokens(c.get(text_key) or "") for c in chunks]
    idf = _idf(token_sets)

    scored: List[Dict[str, Any]] = []
    for c, c_tokens in zip(chunks, token_sets):
        lexical = _lexical_relevance(q_tokens, c_tokens, idf)
        base = float(c.get(score_key) or 0.0)
        scored.append({
            **c,
            "lexical_score": lexical,
            "rerank_score": alpha * base + (1.0 - alpha) * lexical,
        })

    # Sort by blended score DESC; tie-break on a stable string id for determinism.
    def _id(c: Dict[str, Any]) -> str:
        return str(c.get("id") or c.get("chunk_id") or "")

    scored.sort(key=lambda c: (-c["rerank_score"], _id(c)))
    return scored
