#!/usr/bin/env python3
"""
WS-C · HR-policy context-precision evaluator (offline, hermetic).

The immigration context-precision evaluator (eval_rag_context_precision.py)
wires to the live `policy_assistant_chunks` pgvector retriever. The HR-policy
retriever (backend/app/services/policy_chunk_retriever.py, same table) had NO
offline eval. This script fills that gap with a fully deterministic, no-network
lexical retriever over the committed synthetic golden corpus
(backend/tests/fixtures/rag_eval/hr_policy/chunks.jsonl), so the metric is
reproducible in CI without a database or secrets.

It reuses the shared harness (backend/scripts/rag_eval_harness.py):
precision_at_k / recall_at_k / f1 / aggregate_report / write_report /
exit_for_ci — identical reporting + CI-gate semantics to the immigration suite.

CLI:
    python backend/scripts/eval_hr_policy_context_precision.py \\
        --queries backend/tests/fixtures/rag_eval/hr_policy/queries.jsonl \\
        --chunks  backend/tests/fixtures/rag_eval/hr_policy/chunks.jsonl \\
        --out audit/rag_eval/hr_policy_context_precision_$(date +%Y%m%d).json \\
        --k 5 --ci --threshold 0.5

Exit codes (with --ci):
    0 — aggregate precision >= threshold
    1 — aggregate precision <  threshold (CI gate fails the build)
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import sys

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent  # backend/scripts -> backend -> repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from rag_eval_harness import (  # noqa: E402
    GoldenQuery,
    QueryResult,
    RetrievedChunk,
    aggregate_report,
    exit_for_ci,
    f1,
    load_queries,
    precision_at_k,
    recall_at_k,
    write_report,
)

_DEFAULT_QUERIES = _REPO_ROOT / "backend/tests/fixtures/rag_eval/hr_policy/queries.jsonl"
_DEFAULT_CHUNKS = _REPO_ROOT / "backend/tests/fixtures/rag_eval/hr_policy/chunks.jsonl"

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Lightweight stop list so high-frequency glue words don't dominate overlap.
_STOP = {
    "the", "a", "an", "is", "are", "for", "of", "to", "and", "or", "in", "on",
    "what", "how", "does", "do", "this", "that", "per", "by", "with", "at",
    "be", "as", "it", "from", "into",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP}


def _load_chunks(path: str | Path) -> list[dict]:
    """Load the synthetic chunk corpus, skipping the _meta line."""
    p = Path(path)
    out: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if any(k.startswith("_meta") for k in obj):
                continue
            out.append(obj)
    if not out:
        raise ValueError(f"No chunks found in {p}")
    return out


class LexicalPolicyRetriever:
    """Deterministic offline retriever over the HR-policy chunk corpus.

    Scores each chunk by token-overlap between the query and the chunk body,
    scoped to the query's `corridor` (= company/policy pack) — mirroring how the
    immigration adapter scopes retrieval by corridor. No DB, no embeddings, no
    network: the same inputs always produce the same ranking.
    """

    def __init__(self, chunks: list[dict]):
        self._by_company: dict[str, list[dict]] = defaultdict(list)
        for c in chunks:
            company = (c.get("company") or "").strip()
            self._by_company[company].append(
                {**c, "_tokens": _tokens(c.get("body") or "")}
            )
        self._current: GoldenQuery | None = None

    def set_current_query(self, q: GoldenQuery) -> None:
        self._current = q

    def retrieve(self, query: str, k: int = 5) -> Sequence[RetrievedChunk]:
        company = self._current.corridor if self._current else ""
        q_tokens = _tokens(query)
        scored: list[tuple[float, str, dict]] = []
        for c in self._by_company.get(company, []):
            overlap = len(q_tokens & c["_tokens"])
            if not overlap:
                continue
            # Jaccard-style score, stable and bounded in [0, 1].
            denom = len(q_tokens | c["_tokens"]) or 1
            scored.append((overlap / denom, c["chunk_id"], c))
        # Sort by score desc, then chunk_id asc for a deterministic tie-break.
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [
            RetrievedChunk(
                chunk_id=cid,
                score=round(score, 6),
                text=c.get("body"),
                source_url=c.get("source_url"),
            )
            for score, cid, c in scored[:k]
        ]


def evaluate(queries: list[GoldenQuery], retriever: LexicalPolicyRetriever, k: int) -> list[QueryResult]:
    results: list[QueryResult] = []
    for q in queries:
        retriever.set_current_query(q)
        retrieved = retriever.retrieve(q.query_text, k=k)
        retrieved_ids = [c.chunk_id for c in retrieved]
        p = precision_at_k(retrieved_ids, q.expected_chunk_ids, k)
        r = recall_at_k(retrieved_ids, q.expected_chunk_ids, k)
        results.append(
            QueryResult(
                query=q,
                metrics={
                    "precision_at_k": round(p, 4),
                    "recall_at_k": round(r, 4),
                    "f1_at_k": round(f1(p, r), 4),
                },
                retrieved_ids=retrieved_ids,
            )
        )
    return results


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="WS-C HR-policy context-precision evaluator (offline lexical retriever)."
    )
    p.add_argument("--queries", default=str(_DEFAULT_QUERIES), help="Golden-set JSONL path.")
    p.add_argument("--chunks", default=str(_DEFAULT_CHUNKS), help="Chunk-corpus JSONL path.")
    p.add_argument("--out", help="Path to write the JSON report (optional; printed to stdout if omitted).")
    p.add_argument("--k", type=int, default=5, help="Top-k for precision@k (default 5).")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Aggregate-precision threshold for CI gating (default 0.5).",
    )
    p.add_argument("--ci", action="store_true", help="Exit non-zero if aggregate is below threshold.")
    args = p.parse_args(argv)

    queries = load_queries(args.queries)
    chunks = _load_chunks(args.chunks)
    print(f"Loaded {len(queries)} queries and {len(chunks)} chunks.")

    retriever = LexicalPolicyRetriever(chunks)
    results = evaluate(queries, retriever, k=args.k)
    report = aggregate_report(
        results,
        metric_name="precision_at_k",
        threshold=args.threshold,
        extra={"k": args.k, "retriever": type(retriever).__name__, "corpus": str(args.chunks)},
    )

    if args.out:
        write_report(report, args.out)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    if args.ci:
        exit_for_ci(report)


if __name__ == "__main__":
    main()
