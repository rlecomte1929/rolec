"""
Shared harness for the P3-01 RAG evaluation suite.

This module provides:
  - load_queries(path)          : load the rag_eval_queries.jsonl golden set
  - GoldenQuery dataclass       : strongly-typed view of one query
  - RetrieverProtocol           : interface to wire up to relopass's retriever
  - FactualVerifierProtocol     : interface to wire up to relopass's verifier
  - aggregate_report(...)       : compute aggregate + per-corridor + per-intent
                                  metrics and write a JSON report

Each evaluator script (eval_context_precision.py, eval_factual_consistency.py,
eval_outcome_accuracy.py) imports from here so they share the same loading,
filtering, reporting, and CI-gating semantics.

Wire-up checklist for the reviewer:
  1. Replace the StubRetriever class in eval_context_precision.py with an
     adapter around the real retriever in the relopass codebase. The
     RetrieverProtocol interface defines what it must return.
  2. Replace StubVerifier in eval_factual_consistency.py with the real
     factual verifier (P1-01c output).
  3. Wire eval_outcome_accuracy.py to the case-outcomes table once P1-07
     ships.

CLI usage (from each evaluator):
    python scripts/eval_context_precision.py \\
        --queries backend/tests/fixtures/rag_eval_queries.jsonl \\
        --out audit/rag_eval/context_precision_$(date +%Y%m%d).json \\
        --k 5

CI gating:
    Each evaluator exits non-zero if the aggregate metric falls below its
    configured threshold (precision >= 0.85 for context_precision,
    factual_consistency >= 0.95 for factual_consistency). This makes the
    suite directly usable from GitHub Actions.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class GoldenQuery:
    """One row of the golden test set."""

    query_id: str
    corridor: str
    intent_category: str
    query_text: str
    expected_chunk_ids: list[str]
    difficulty: str = "medium"
    persona: str | None = None
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GoldenQuery":
        known = {
            "query_id",
            "corridor",
            "intent_category",
            "query_text",
            "expected_chunk_ids",
            "difficulty",
            "persona",
            "notes",
        }
        extra = {k: v for k, v in raw.items() if k not in known and not k.startswith("_meta")}
        return cls(
            query_id=raw["query_id"],
            corridor=raw["corridor"],
            intent_category=raw["intent_category"],
            query_text=raw["query_text"],
            expected_chunk_ids=list(raw["expected_chunk_ids"]),
            difficulty=raw.get("difficulty", "medium"),
            persona=raw.get("persona"),
            notes=raw.get("notes"),
            extra=extra,
        )


def load_queries(path: str | Path) -> list[GoldenQuery]:
    """Load the JSONL golden set, skipping _meta lines."""

    p = Path(path)
    queries: list[GoldenQuery] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if any(k.startswith("_meta") for k in obj):
                continue
            queries.append(GoldenQuery.from_dict(obj))
    if not queries:
        raise ValueError(f"No queries found in {p}")
    return queries


# ---------------------------------------------------------------------------
# Interfaces — wire these to the real retriever and verifier
# ---------------------------------------------------------------------------


@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float
    text: str | None = None
    source_url: str | None = None


class RetrieverProtocol(Protocol):
    """The minimal contract evaluators expect of a retriever.

    Implement this against relopass's actual retriever (semantic search over
    immigration_requirements + corpus chunks). The chunk_id MUST be the
    deterministic id used in the corpus files (matching expected_chunk_ids).
    """

    def retrieve(self, query: str, k: int = 5) -> Sequence[RetrievedChunk]:
        ...


@dataclass
class VerificationVerdict:
    supported: bool
    confidence: float
    rationale: str
    unsupported_claims: list[str] = field(default_factory=list)


class FactualVerifierProtocol(Protocol):
    """Verifier that judges whether a generated step is supported by retrieved sources.

    Implement against the verifier built in P1-01c.
    """

    def verify(self, generated_step: str, retrieved_sources: Sequence[RetrievedChunk]) -> VerificationVerdict:
        ...


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def precision_at_k(retrieved_ids: Sequence[str], expected_ids: Sequence[str], k: int) -> float:
    """Standard precision@k. Returns 0.0 if no retrieved chunks."""

    top_k = list(retrieved_ids[:k])
    if not top_k:
        return 0.0
    expected = set(expected_ids)
    hits = sum(1 for cid in top_k if cid in expected)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: Sequence[str], expected_ids: Sequence[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    top_k = set(list(retrieved_ids[:k]))
    expected = set(expected_ids)
    return len(top_k & expected) / len(expected)


def f1(p: float, r: float) -> float:
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    query: GoldenQuery
    metrics: dict[str, float]
    retrieved_ids: list[str] = field(default_factory=list)
    notes: str | None = None


def aggregate_report(
    results: Iterable[QueryResult],
    metric_name: str,
    threshold: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the JSON report: aggregate + per-corridor + per-intent + per-difficulty."""

    results_list = list(results)
    if not results_list:
        raise ValueError("No results to aggregate")

    def _mean(seq: list[float]) -> float:
        return round(sum(seq) / len(seq), 4) if seq else 0.0

    by_corridor: dict[str, list[float]] = defaultdict(list)
    by_intent: dict[str, list[float]] = defaultdict(list)
    by_difficulty: dict[str, list[float]] = defaultdict(list)
    all_values: list[float] = []

    for r in results_list:
        v = r.metrics.get(metric_name)
        if v is None:
            continue
        all_values.append(v)
        by_corridor[r.query.corridor].append(v)
        by_intent[r.query.intent_category].append(v)
        by_difficulty[r.query.difficulty].append(v)

    aggregate = _mean(all_values)
    passes_threshold = aggregate >= threshold

    return {
        "metric": metric_name,
        "threshold": threshold,
        "aggregate": aggregate,
        "passes_threshold": passes_threshold,
        "queries_evaluated": len(results_list),
        "by_corridor": {k: _mean(v) for k, v in sorted(by_corridor.items())},
        "by_intent": {k: _mean(v) for k, v in sorted(by_intent.items())},
        "by_difficulty": {k: _mean(v) for k, v in sorted(by_difficulty.items())},
        "lowest_queries": sorted(
            (
                {
                    "query_id": r.query.query_id,
                    "value": r.metrics.get(metric_name, 0.0),
                    "corridor": r.query.corridor,
                    "intent": r.query.intent_category,
                    "retrieved_ids": r.retrieved_ids,
                }
                for r in results_list
            ),
            key=lambda x: x["value"],
        )[:10],
        "extra": extra or {},
    }


def write_report(report: dict[str, Any], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"Wrote report -> {out}")


def exit_for_ci(report: dict[str, Any]) -> None:
    """Exit non-zero if aggregate is below threshold so CI can gate."""

    if report["passes_threshold"]:
        print(
            f"[PASS] {report['metric']} = {report['aggregate']:.4f} "
            f">= threshold {report['threshold']:.4f}"
        )
        sys.exit(0)
    print(
        f"[FAIL] {report['metric']} = {report['aggregate']:.4f} "
        f"< threshold {report['threshold']:.4f}"
    )
    sys.exit(1)
