#!/usr/bin/env python3
"""
P3-01b · Context-precision evaluator (wired to immigration_retriever).

For each query in the golden set (backend/tests/fixtures/rag_eval/queries.jsonl),
builds a UserProfile + PathClassification from the query's `profile` block,
calls `immigration_retriever.retrieve_for_profile`, and computes precision@k
against the `expected_chunk_ids`. Outputs a JSON report with aggregate +
per-corridor / per-intent / per-difficulty breakdowns and the 10
worst-performing queries.

Wire-up history:
    Initial stubbed delivery was AIQ-708 (P3-01b). FU1 (this change) wires
    the real retriever via `ImmigrationRetrieverAdapter`. The chunk_id
    returned by the retriever is the deterministic corpus id (e.g.
    "us_fr_lsv_passport"), matching the `expected_chunk_ids` in the
    golden set — no DB-uuid mapping needed because the ingester
    (P2-06d) uses deterministic ids as the chunk primary key.

CLI:
    python backend/scripts/eval_rag_context_precision.py \\
        --queries backend/tests/fixtures/rag_eval/queries.jsonl \\
        --out audit/rag_eval/context_precision_$(date +%Y%m%d).json \\
        --k 5 --ci --threshold 0.85

Exit codes (with --ci):
    0 — aggregate precision >= threshold
    1 — aggregate precision < threshold (CI gate fails the build)

Empty-corpus behaviour:
    If no immigration chunks have been ingested (e.g. before P2-06d runs),
    the retriever returns empty lists and aggregate precision is 0.0. The
    CI smoke ``--ci --threshold 0.0`` still passes (0.0 >= 0.0); use
    ``--threshold 0.85`` once the corpus is live.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

# Repo-root on sys.path so `from backend.app.services...` imports work
# when this script is run directly.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent  # backend/scripts -> backend -> repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Local: shared eval harness sits alongside this script.
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from rag_eval_harness import (  # noqa: E402
    GoldenQuery,
    QueryResult,
    RetrievedChunk,
    RetrieverProtocol,
    aggregate_report,
    exit_for_ci,
    f1,
    load_queries,
    precision_at_k,
    recall_at_k,
    write_report,
)

# Retriever import is deferred so `--help` and unit tests can import this
# module without standing up the full backend.
from backend.app.services import immigration_retriever  # noqa: E402
from backend.app.services.immigration_retriever import (  # noqa: E402
    PathClassification,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Adapter: bridge the golden-set profile block to the retriever's typed input.
# ---------------------------------------------------------------------------


# Map (corridor, profile_signals) -> pathway_type used by the corpus and
# ingested chunks. Sourced from the `path_classifier_rules` blocks in each
# corpus JSON. Kept inline here so the eval has no runtime dependency on the
# corpus files themselves — the corpus is the source of truth at ingestion
# time; this mirror is the source of truth at eval time.
_PATHWAY_DEFAULTS = {
    "FR→NO": "eu_free_movement",      # EEA → EEA: free movement
    "US→FR": "long_stay_visa",        # default; upgraded below if qualified
    "IN→DE": "blue_card",             # default; downgraded below if below threshold
    "UK→DE": "blue_card",             # post-Brexit UK is third country
    "BR→PT": "cplp_residence",        # CPLP facilitation is the default route
}


# EEA membership for is_eea derivation. Static list adequate for the 5
# corridors in the golden set; expand if more corridors land.
_EEA_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL",
    "PT", "RO", "SK", "SI", "ES", "SE",
}


def _normalize_corridor(s: str) -> str:
    """The golden set uses ASCII '->' (e.g. 'US->FR'); the retriever uses the
    Unicode arrow '→'. Convert and uppercase."""
    return s.replace("->", "→").strip().upper()


def _derive_pathway_type(profile: dict, corridor_norm: str) -> str:
    """
    Map (corridor + profile signals) -> pathway_type that the corpus uses.

    Default per corridor lives in _PATHWAY_DEFAULTS; the conditionals below
    encode the upgrade / fallback rules taken straight from each corpus's
    `path_classifier_rules` block:

      * US→FR: profile with master_or_higher + salary≥€43,243 → passeport_talent
      * IN→DE / UK→DE: salary <€45,934.20 falls back to skilled_worker;
                       salary≥€50,700 stays on blue_card (general);
                       between the two relies on shortage_occupation flag.
      * BR→PT: intent 'retired' or 'passive_income' chooses d7_visa;
               intent 'self_employed' chooses d2_visa;
               otherwise stays on cplp_residence.
    """
    pathway = _PATHWAY_DEFAULTS.get(corridor_norm, "long_stay_visa")
    qual = (profile.get("qualification_level") or "").lower()
    intent = (profile.get("intent") or "").lower()
    salary = profile.get("salary_eur_annual")
    occ = (profile.get("occupation_category") or "").lower()

    if corridor_norm == "US→FR":
        if qual == "master_or_higher" and salary is not None and salary >= 43243:
            pathway = "passeport_talent"
    elif corridor_norm in ("IN→DE", "UK→DE"):
        if salary is not None:
            if salary < 45934.20:
                pathway = "skilled_worker"
            elif salary >= 50700:
                pathway = "blue_card"
            elif occ == "shortage" or qual == "master_or_higher":
                pathway = "blue_card"
    elif corridor_norm == "BR→PT":
        if intent in ("retired", "passive_income"):
            pathway = "d7_visa"
        elif intent == "self_employed":
            pathway = "d2_visa"
        # else: stays on cplp_residence (default for Brazilians)

    return pathway


def _build_typed_inputs(profile: dict, corridor_norm: str) -> tuple[UserProfile, PathClassification]:
    """Lift the golden-set profile dict into the retriever's typed inputs."""
    nationality = (profile.get("nationality") or "").upper()
    destination = (profile.get("destination") or "").upper()
    # Derive is_eea from membership; the retriever uses this only in the
    # query text it builds, not for filtering, so an approximation is fine.
    is_eea = nationality in _EEA_COUNTRIES if nationality else None

    user = UserProfile(
        nationality=nationality,
        origin_country=nationality,           # golden set treats origin == nationality
        destination_country=destination,
        is_eea=is_eea,
    )
    classification = PathClassification(
        pathway_type=_derive_pathway_type(profile, corridor_norm),
        corridor=corridor_norm,
    )
    return user, classification


class ImmigrationRetrieverAdapter:
    """Adapts `immigration_retriever.retrieve_for_profile` to RetrieverProtocol.

    The retriever needs a typed (UserProfile, PathClassification) — the eval
    pipeline carries a single free-text query plus a `profile` block on each
    GoldenQuery. This adapter stitches them together.
    """

    def __init__(self, *, default_top_k: int = 5):
        self._default_top_k = default_top_k
        self._current_query: GoldenQuery | None = None

    # The harness calls retrieve(query_text, k) without the per-query
    # GoldenQuery in scope. Set it via set_current_query() before retrieve()
    # so we can build the typed inputs from the profile block.
    def set_current_query(self, q: GoldenQuery) -> None:
        self._current_query = q

    def retrieve(self, query: str, k: int = 5) -> Sequence[RetrievedChunk]:
        if self._current_query is None:
            raise RuntimeError(
                "ImmigrationRetrieverAdapter.retrieve called before "
                "set_current_query — see evaluate() for the wiring."
            )
        profile = self._current_query.extra.get("profile") or {}
        corridor_norm = _normalize_corridor(self._current_query.corridor)
        user, classification = _build_typed_inputs(profile, corridor_norm)

        hits = immigration_retriever.retrieve_for_profile(
            profile=user,
            classification=classification,
            top_k=k,
        )
        out: list[RetrievedChunk] = []
        for h in hits:
            meta = h.get("chunk_metadata") or {}
            out.append(RetrievedChunk(
                chunk_id=str(h["id"]),
                score=float(h.get("score", 0.0)),
                text=h.get("chunk_text"),
                source_url=meta.get("source_url"),
            ))
        return out


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def evaluate(
    queries: list[GoldenQuery],
    retriever: ImmigrationRetrieverAdapter,
    k: int,
) -> list[QueryResult]:
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="P3-01b context-precision evaluator (wired to immigration_retriever)"
    )
    p.add_argument(
        "--queries",
        default=str(_REPO_ROOT / "backend/tests/fixtures/rag_eval/queries.jsonl"),
        help="Path to the golden-set JSONL (default: repo fixture path).",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Path to write the JSON report.",
    )
    p.add_argument("--k", type=int, default=5, help="Top-k for precision@k")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Aggregate-precision threshold for CI gating (default 0.85).",
    )
    p.add_argument(
        "--ci",
        action="store_true",
        help="Exit non-zero if aggregate is below threshold.",
    )
    args = p.parse_args(argv)

    queries = load_queries(args.queries)
    print(f"Loaded {len(queries)} queries from {args.queries}")

    retriever = ImmigrationRetrieverAdapter(default_top_k=args.k)
    results = evaluate(queries, retriever, k=args.k)
    report = aggregate_report(
        results,
        metric_name="precision_at_k",
        threshold=args.threshold,
        extra={"k": args.k, "retriever": type(retriever).__name__},
    )
    write_report(report, args.out)

    if args.ci:
        exit_for_ci(report)


if __name__ == "__main__":
    main()
