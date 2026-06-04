#!/usr/bin/env python3
"""
P3-01c · Factual-consistency evaluator (wired to the P1-01c verifier).

For each query in the golden set that has a generated roadmap step (supplied via
a ``--generated-steps {query_id: step_text}`` JSON sidecar), retrieves the top-k
chunks and asks the factual verifier (P1-01c, ``factual_verifier.verify_step``)
whether the step is supported by those chunks. Records 1.0 / 0.0 per query and
logs every unsupported step so reviewers can spot-check. Emits a JSON report
with aggregate %-supported + per-corridor / per-intent / per-difficulty
breakdowns and a ``flagged_steps_sample``.

Wire-up history:
    P3-01c (AIQ-709) shipped the structural evaluator against a StubVerifier in
    Cowork but never landed in-repo. P3-01c-FU1 (this change) lands it and wires
    the real verifier now that P1-01c (AIQ-628) is on main (#276). The retriever
    side reuses ``ImmigrationRetrieverAdapter`` from the context-precision
    evaluator (P3-01b-FU1) — same RetrieverProtocol.

CLI:
    python backend/scripts/eval_factual_consistency.py \\
        --queries backend/tests/fixtures/rag_eval/queries.jsonl \\
        --generated-steps audit/rag_eval/generated_steps.json \\
        --out audit/rag_eval/factual_consistency_$(date +%Y%m%d).json \\
        --k 5 --ci --threshold 0.95

Exit codes (with --ci):
    0 — aggregate factual-consistency >= threshold (or nothing to evaluate)
    1 — aggregate < threshold (CI gate fails the build)

Pre-launch behaviour:
    Generated steps come from the JSON sidecar so the eval can run before
    closed-case outcome data exists (P1-07). Queries without a generated step
    are skipped (and counted), not failed, so the metric is not artificially
    deflated. With no sidecar, nothing is evaluated and the script exits 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

# Repo-root + scripts dir on sys.path so `from backend.app.services...` and the
# sibling-script / harness imports resolve when run directly.
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
    VerificationVerdict,
    aggregate_report,
    exit_for_ci,
    load_queries,
    write_report,
)

# Reuse the retriever adapter from the context-precision evaluator — both
# evaluators satisfy the same RetrieverProtocol, so there is one adapter.
from eval_rag_context_precision import ImmigrationRetrieverAdapter  # noqa: E402

# Deferred so --help / unit tests can import without standing up the backend.
from backend.app.services import factual_verifier  # noqa: E402

_METRIC = "factual_consistency"


# ---------------------------------------------------------------------------
# Adapter: bridge the P1-01c verifier to the harness FactualVerifierProtocol.
# ---------------------------------------------------------------------------


class FactualVerifierAdapter:
    """Adapts ``factual_verifier.verify_step`` (P1-01c) to FactualVerifierProtocol.

    The harness passes a generated step (free text) plus the retrieved sources.
    ``verify_step`` operates on a step dict + chunk dicts and returns a
    ``StepVerdict``; we map that onto ``VerificationVerdict``. A generated step
    carries no citation of its own, so we leave ``source_chunk_id`` empty and
    let the verifier search all retrieved chunks for grounding — ``supported``
    is True only when the verifier finds a real supporting chunk.
    """

    def __init__(self, *, client=None, model: Optional[str] = None) -> None:
        self._client = client
        self._model = model

    def verify(
        self, generated_step: str, retrieved_sources: Sequence[RetrievedChunk]
    ) -> VerificationVerdict:
        chunks = [
            {
                "id": c.chunk_id,
                "chunk_text": c.text or "",
                "source_url": c.source_url or "",
                "source_ref": c.source_url or "",
                "chunk_metadata": {},
            }
            for c in retrieved_sources
        ]
        verdict = factual_verifier.verify_step(
            step={
                "order": 1,
                "title": generated_step,
                "description": generated_step,
                "source_url": "",
                "source_chunk_id": "",
            },
            chunks=chunks,
            client=self._client,
            model=self._model,
        )
        return VerificationVerdict(
            supported=verdict.supported,
            confidence=1.0 if verdict.supported else 0.0,
            rationale=verdict.reason,
            unsupported_claims=[] if verdict.supported else [generated_step],
        )


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def load_generated_steps(path: str | Path) -> dict[str, str]:
    """Load the ``{query_id: step_text}`` bootstrap sidecar."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("--generated-steps must be a JSON object {query_id: step_text}")
    return {str(k): str(v) for k, v in data.items()}


def evaluate(
    queries: list[GoldenQuery],
    retriever: ImmigrationRetrieverAdapter,
    verifier: FactualVerifierAdapter,
    generated_steps: dict[str, str],
    k: int,
) -> tuple[list[QueryResult], int]:
    """Run the evaluator. Returns ``(results, skipped)`` where ``skipped`` is the
    count of queries that had no generated step (excluded, not failed)."""
    results: list[QueryResult] = []
    skipped = 0
    for q in queries:
        step_text = (generated_steps.get(q.query_id) or "").strip()
        if not step_text:
            skipped += 1
            continue
        retriever.set_current_query(q)
        retrieved = retriever.retrieve(q.query_text, k=k)
        verdict = verifier.verify(step_text, retrieved)
        results.append(
            QueryResult(
                query=q,
                metrics={
                    _METRIC: 1.0 if verdict.supported else 0.0,
                    "confidence": round(verdict.confidence, 4),
                },
                retrieved_ids=[c.chunk_id for c in retrieved],
                notes=verdict.rationale,
            )
        )
    return results, skipped


def build_flagged_steps(
    results: list[QueryResult], generated_steps: dict[str, str]
) -> list[dict]:
    """Every unsupported step, with enough context for a reviewer to spot-check."""
    return [
        {
            "query_id": r.query.query_id,
            "corridor": r.query.corridor,
            "intent": r.query.intent_category,
            "generated_step": generated_steps.get(r.query.query_id, ""),
            "rationale": r.notes or "",
        }
        for r in results
        if r.metrics.get(_METRIC, 0.0) == 0.0
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="P3-01c factual-consistency evaluator (wired to the P1-01c verifier)"
    )
    p.add_argument(
        "--queries",
        default=str(_REPO_ROOT / "backend/tests/fixtures/rag_eval/queries.jsonl"),
        help="Path to the golden-set JSONL (default: repo fixture path).",
    )
    p.add_argument(
        "--generated-steps",
        default=None,
        help="JSON sidecar {query_id: step_text}. Queries without an entry are skipped.",
    )
    p.add_argument("--out", required=True, help="Path to write the JSON report.")
    p.add_argument("--k", type=int, default=5, help="Top-k chunks to verify against.")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.95,
        help="Aggregate factual-consistency threshold for CI gating (default 0.95).",
    )
    p.add_argument(
        "--ci", action="store_true", help="Exit non-zero if aggregate is below threshold."
    )
    args = p.parse_args(argv)

    queries = load_queries(args.queries)
    generated = load_generated_steps(args.generated_steps) if args.generated_steps else {}
    print(f"Loaded {len(queries)} queries; {len(generated)} generated steps.")

    retriever = ImmigrationRetrieverAdapter(default_top_k=args.k)
    verifier = FactualVerifierAdapter()
    results, skipped = evaluate(queries, retriever, verifier, generated, k=args.k)

    if not results:
        print(
            f"No generated steps matched (skipped={skipped}); nothing to evaluate. "
            "Provide --generated-steps to bootstrap the eval."
        )
        return

    flagged = build_flagged_steps(results, generated)
    report = aggregate_report(
        results,
        metric_name=_METRIC,
        threshold=args.threshold,
        extra={
            "k": args.k,
            "verifier": type(verifier).__name__,
            "queries_evaluated_with_step": len(results),
            "queries_without_generated_step": skipped,
            "flagged_steps_total": len(flagged),
            "flagged_steps_sample": flagged[:20],
        },
    )
    write_report(report, args.out)

    if args.ci:
        exit_for_ci(report)


if __name__ == "__main__":
    main()
