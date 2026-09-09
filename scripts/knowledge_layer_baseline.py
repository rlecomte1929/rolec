"""Score the in-repo FR→NO seed. Never connects to production.

Usage (from repo root):

    python3 scripts/knowledge_layer_baseline.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from backend.app.services.knowledge_layer_scorecard import (  # noqa: E402
    count_resolved_citations,
    score_catalog,
)
from backend.scripts.seed_requirements import build_payloads  # noqa: E402

NORWAY_SEED = os.path.join(ROOT, "backend", "seeds", "requirements", "norway.yaml")


def score_norway_seed() -> dict:
    with open(NORWAY_SEED, encoding="utf-8") as fh:
        seed = yaml.safe_load(fh)
    payloads = build_payloads(seed)
    approved = pending = rejected = resolved = 0
    pillars: list[str] = []
    for p in payloads:
        status = (p.get("review_status") or "pending").strip().lower()
        if status == "pending":
            pending += 1
            continue
        if status == "rejected":
            rejected += 1
            continue
        approved += 1
        pillars.append(p.get("pillar") or "")
        if count_resolved_citations(p.get("citations_json"), {}) > 0:
            resolved += 1
    card = score_catalog(
        approved_count=approved,
        pending_count=pending,
        rejected_count=rejected,
        citation_resolved_approved=resolved,
        pillars=pillars,
    )
    return {"seed_rows": len(payloads), **card.as_dict()}


def main() -> None:
    out = score_norway_seed()
    print("FR→NO in-repo seed baseline (not production)")
    for k, v in out.items():
        print(f"  {k}: {v}")
    print("Live QBR columns: see docs/corridors/fr-no/QBR-knowledge-layer.md (N/A until measured)")


if __name__ == "__main__":
    main()
