#!/usr/bin/env python3
"""
Claim-level RAG error-localization eval (RAGChecker analog) over the
immigration golden set.

For each query/step in ``backend/tests/fixtures/rag_eval/queries.jsonl`` it
computes three id sets and classifies the step with
``backend.eval.rag_error_localization.localize_step``:

    RETRIEVED  — top-k ids from a deterministic lexical retriever over the
                 query's corridor corpus (offline; no DB, no embeddings).
    CORPUS     — every chunk id in that corridor (from chunks.jsonl).
    GOLD       — the query's ``expected_chunk_ids``.

The aggregate split answers the operational question: when steps are NOT
grounded, is the cause a **retriever_miss** (support exists in the corpus but
wasn't retrieved → fix RETRIEVAL) or a **generator_hallucination** (no support
in the corpus → fix the GENERATOR)?

The default run is hermetic and deterministic. An optional ``--live`` path
swaps in the real ``immigration_retriever`` for retrieval and
``factual_verifier`` for the grounding decision (needs a DB + API key; never
exercised by tests/CI).

CLI:
    python backend/scripts/eval_rag_error_localization.py
    python backend/scripts/eval_rag_error_localization.py --json
    python backend/scripts/eval_rag_error_localization.py --k 5 --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Repo-root + scripts dir on sys.path so both ``backend.eval...`` and the
# sibling ``rag_eval_harness`` import resolve when run directly.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent  # backend/scripts -> backend -> repo root
for _p in (str(_REPO_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rag_eval_harness import GoldenQuery, load_queries  # noqa: E402

from backend.eval.rag_error_localization import (  # noqa: E402
    GENERATOR_HALLUCINATION,
    RETRIEVER_MISS,
    aggregate_localization,
    localize_step,
)

DEFAULT_QUERIES = _REPO_ROOT / "backend/tests/fixtures/rag_eval/queries.jsonl"
DEFAULT_CHUNKS = _REPO_ROOT / "backend/tests/fixtures/rag_eval/chunks.jsonl"


# ---------------------------------------------------------------------------
# Corpus + deterministic lexical retriever (hermetic default)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "for", "of", "to", "and", "or", "in", "on",
    "what", "how", "does", "do", "this", "that", "per", "by", "with", "at",
    "be", "as", "it", "from", "into", "you", "your", "need", "needs",
}


def _tokens(text: str) -> set:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP}


def _overlap(a: str, b: str) -> float:
    """Jaccard token overlap in [0, 1]. 0 when either side is empty."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _corridor_key(query_corridor: str) -> str:
    """Golden set uses 'FR->NO'; chunks.jsonl uses 'FR_NO'."""
    return query_corridor.replace("->", "_").strip().upper()


def load_corpus(path: str | Path) -> Dict[str, List[dict]]:
    """Load chunks.jsonl into ``{corridor_key: [{chunk_id, body}, ...]}``."""
    by_corridor: Dict[str, List[dict]] = {}
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if any(k.startswith("_meta") for k in obj):
                continue
            corridor = (obj.get("corridor") or "").strip().upper()
            by_corridor.setdefault(corridor, []).append(
                {"chunk_id": obj["chunk_id"], "body": obj.get("body") or ""}
            )
    if not by_corridor:
        raise ValueError(f"No chunks found in {path}")
    return by_corridor


def lexical_retrieve(query_text: str, corpus_chunks: Sequence[dict], k: int) -> List[str]:
    """Deterministic top-k by token overlap; ties broken by chunk_id for stability."""
    ranked = sorted(
        corpus_chunks,
        key=lambda c: (-_overlap(query_text, c["body"]), c["chunk_id"]),
    )
    return [c["chunk_id"] for c in ranked[:k]]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_offline(
    queries: List[GoldenQuery],
    corpus: Dict[str, List[dict]],
    k: int,
) -> List[dict]:
    """Classify every query/step against retrieved-vs-corpus-vs-gold."""
    results: List[dict] = []
    for q in queries:
        corridor = _corridor_key(q.corridor)
        corridor_chunks = corpus.get(corridor, [])
        corpus_ids = [c["chunk_id"] for c in corridor_chunks]
        retrieved_ids = lexical_retrieve(q.query_text, corridor_chunks, k)
        gold = q.expected_chunk_ids

        label = localize_step(
            step=q.query_id,
            retrieved_ids=retrieved_ids,
            corpus_ids=corpus_ids,
            gold_support_ids=gold,
        )
        results.append(
            {
                "query_id": q.query_id,
                "corridor": q.corridor,
                "intent": q.intent_category,
                "localization": label,
                "n_gold": len(gold),
                "n_gold_in_corpus": len(set(gold) & set(corpus_ids)),
                "n_gold_retrieved": len(set(gold) & set(retrieved_ids)),
                "retrieved_ids": retrieved_ids,
            }
        )
    return results


def evaluate_live(queries: List[GoldenQuery], corpus: Dict[str, List[dict]], k: int) -> List[dict]:
    """Optional live path: real retriever + factual_verifier grounding.

    Reuses the corridor corpus from the fixtures as the CORPUS reference set,
    but takes RETRIEVED from ``immigration_retriever`` and the grounding
    decision from ``factual_verifier.verify_step``. Needs a live DB and an
    API key; never run by tests/CI.
    """
    import eval_rag_context_precision as evp  # sibling adapter, scripts/ on path
    from backend.app.services.factual_verifier import verify_step

    adapter = evp.ImmigrationRetrieverAdapter(default_top_k=k)
    results: List[dict] = []
    for q in queries:
        corridor = _corridor_key(q.corridor)
        corpus_ids = [c["chunk_id"] for c in corpus.get(corridor, [])]
        adapter.set_current_query(q)
        retrieved = adapter.retrieve(q.query_text, k=k)
        retrieved_ids = [c.chunk_id for c in retrieved]
        chunks = [{"id": c.chunk_id, "text": c.text or ""} for c in retrieved]
        verdict = verify_step(step={"title": q.query_text, "claims": [q.query_text]}, chunks=chunks)
        label = localize_step(
            step=q.query_id,
            retrieved_ids=retrieved_ids,
            corpus_ids=corpus_ids,
            gold_support_ids=q.expected_chunk_ids,
            grounded=verdict.supported,
        )
        results.append(
            {
                "query_id": q.query_id,
                "corridor": q.corridor,
                "intent": q.intent_category,
                "localization": label,
                "n_gold": len(q.expected_chunk_ids),
                "n_gold_in_corpus": len(set(q.expected_chunk_ids) & set(corpus_ids)),
                "n_gold_retrieved": len(set(q.expected_chunk_ids) & set(retrieved_ids)),
                "retrieved_ids": retrieved_ids,
            }
        )
    return results


def build_report(results: List[dict], k: int, mode: str) -> dict:
    split = aggregate_localization(results)
    return {
        "mode": mode,
        "k": k,
        "queries_evaluated": len(results),
        "split": split,
        "recommendation": _recommend(split),
        "results": results,
    }


def _recommend(split: dict) -> str:
    miss = split[RETRIEVER_MISS]
    hall = split[GENERATOR_HALLUCINATION]
    if miss == 0 and hall == 0:
        return "All steps grounded — no localized errors."
    if miss > hall:
        return "Ungrounded errors dominated by retriever_miss -> FIX RETRIEVAL (support exists but isn't retrieved)."
    if hall > miss:
        return "Ungrounded errors dominated by generator_hallucination -> FIX THE GENERATOR (claims absent from corpus)."
    return "Retriever_miss and generator_hallucination are tied -> investigate both."


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_human(report: dict) -> None:
    s = report["split"]
    lines = [
        "",
        f"=== RAG Error Localization ({report['mode']}, k={report['k']}) ===",
        f"Steps evaluated: {report['queries_evaluated']}",
        "",
        "  outcome                    count   rate",
        f"  grounded                  {s['grounded']:>6}  {s['grounded_rate']:>6.2%}",
        f"  retriever_miss            {s['retriever_miss']:>6}  {s['retriever_miss_rate']:>6.2%}",
        f"  generator_hallucination   {s['generator_hallucination']:>6}  {s['generator_hallucination_rate']:>6.2%}",
        "",
        f"  -> {report['recommendation']}",
        "",
    ]
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Claim-level RAG error-localization eval (retriever_miss vs generator_hallucination)."
    )
    p.add_argument("--queries", default=str(DEFAULT_QUERIES), help="Golden-set JSONL path.")
    p.add_argument("--chunks", default=str(DEFAULT_CHUNKS), help="Corpus chunks JSONL path.")
    p.add_argument("--k", type=int, default=5, help="Top-k for retrieval (default 5).")
    p.add_argument("--json", action="store_true", help="Emit a machine-readable JSON report.")
    p.add_argument(
        "--live",
        action="store_true",
        help="Use the real retriever + factual_verifier (needs DB + API key; default is hermetic).",
    )
    args = p.parse_args(argv)

    queries = load_queries(args.queries)
    corpus = load_corpus(args.chunks)

    if args.live:
        results = evaluate_live(queries, corpus, args.k)
        mode = "live"
    else:
        results = evaluate_offline(queries, corpus, args.k)
        mode = "offline"

    report = build_report(results, args.k, mode)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
