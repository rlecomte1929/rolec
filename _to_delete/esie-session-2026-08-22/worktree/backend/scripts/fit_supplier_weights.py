"""[P2] Offline fitter for learned per-segment supplier-ranking weights.

Usage:
    # Dry-run (fit + print would-be weights, write nothing):
    python -m backend.scripts.fit_supplier_weights --dry-run --json
    # Fit and persist (service role / admin DB):
    python -m backend.scripts.fit_supplier_weights
    python -m backend.scripts.fit_supplier_weights --category banks --min-pairs 50

Reads logged ``recommendation_slates`` ⋈ selection events (``supplier_selected`` /
``quote_accepted`` in ``analytics_events``), builds chosen-vs-shown examples, fits
a logistic LTR per ``(category, segment)`` cell, and writes ONE new
``supplier_ranking_weights`` row per cell that clears ``--min-pairs``. Cells below
the threshold (or with a single class) are SKIPPED — the static weights stand.

This is data-blocked until real slate⋈selection volume accrues, so an empty/thin
DB makes it a clean no-op (it reports the skip; it never fabricates weights).
Serving any weights it writes still requires the ``SUPPLIER_LEARNED_WEIGHTS`` flag
(see recommendations/weights.get_weights) — fitting alone changes no rankings.

Suggested schedule (do NOT auto-create): weekly off-peak, after enough data.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

log = logging.getLogger("fit_supplier_weights")


def _load_slates_and_selections(session) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Best-effort read of slates + selection events. Returns ([], []) if the
    tables are absent (pre-migration) or anything fails."""
    from sqlalchemy import text

    slates: List[Dict[str, Any]] = []
    selections: List[Dict[str, Any]] = []
    try:
        rows = session.execute(
            text(
                "select category, segment, case_id, items_json "
                "from public.recommendation_slates"
            )
        ).all()
        for r in rows:
            items = r[3]
            if not isinstance(items, list):
                try:
                    items = json.loads(items) if items else []
                except (TypeError, ValueError):
                    items = []
            slates.append(
                {"category": r[0], "segment": r[1], "case_id": r[2], "items_json": items}
            )
    except Exception as exc:
        log.warning("recommendation_slates read failed (table may not exist): %s", exc)

    try:
        rows = session.execute(
            text(
                "select payload_json from public.analytics_events "
                "where event_name in ('supplier_selected', 'quote_accepted')"
            )
        ).all()
        for (payload_raw,) in rows:
            try:
                payload = payload_raw if isinstance(payload_raw, dict) else json.loads(payload_raw)
            except (TypeError, ValueError):
                continue
            extra = payload.get("extra") or {}
            item_id = extra.get("vendor_id") or extra.get("supplier_id")
            case_id = payload.get("case_id") or payload.get("canonical_case_id")
            if case_id and item_id:
                selections.append({"case_id": case_id, "item_id": item_id})
    except Exception as exc:
        log.warning("analytics_events read failed: %s", exc)

    return slates, selections


def run(category: Optional[str], min_pairs: int, dry_run: bool) -> Dict[str, Any]:
    from backend.app.recommendations import weight_learner
    from backend.app.recommendations.ranking_weights_store import save_segment_weights
    from backend.app.recommendations.weights import WEIGHTS

    try:
        from backend.app.db import SessionLocal
    except Exception as exc:  # pragma: no cover - env without DB
        return {"error": f"no DB: {exc}", "cells": []}

    report: Dict[str, Any] = {"dry_run": dry_run, "min_pairs": min_pairs, "cells": []}
    with SessionLocal() as session:
        slates, selections = _load_slates_and_selections(session)
        examples = weight_learner.build_training_examples(slates, selections)
        cells = weight_learner.group_by_cell(examples)
        report["n_slates"] = len(slates)
        report["n_selections"] = len(selections)
        report["n_examples"] = len(examples)

        for (cat, seg), cell_examples in sorted(cells.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            if category and cat != category:
                continue
            factors = list(WEIGHTS.get(cat, {}).keys())
            if not factors:
                report["cells"].append({"category": cat, "segment": seg, "fitted": False, "reason": "unknown category"})
                continue
            weights, reason = weight_learner.fit_cell(cell_examples, factors, min_pairs=min_pairs)
            entry = {"category": cat, "segment": seg, "fitted": weights is not None, "reason": reason}
            if weights is not None:
                entry["weights"] = weights
                if not dry_run:
                    save_segment_weights(
                        session,
                        category=cat,
                        segment=seg,
                        weights=weights,
                        metadata={"n_training_pairs": len(cell_examples), "model_kind": "logistic_ltr"},
                    )
            report["cells"].append(entry)
        if not dry_run:
            session.commit()

    report["n_fitted"] = sum(1 for c in report["cells"] if c.get("fitted"))
    return report


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Fit learned supplier-ranking weights (P2).")
    parser.add_argument("--category", default=None, help="Only fit this category.")
    parser.add_argument("--min-pairs", type=int, default=None, help="Override MIN_TRAINING_PAIRS.")
    parser.add_argument("--dry-run", action="store_true", help="Fit + print; write nothing.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args(argv)

    from backend.app.recommendations.weight_learner import MIN_TRAINING_PAIRS

    report = run(
        category=args.category,
        min_pairs=args.min_pairs if args.min_pairs is not None else MIN_TRAINING_PAIRS,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report.get("error"):
            print(f"fit_supplier_weights: {report['error']}")
        else:
            print(
                f"slates={report.get('n_slates',0)} selections={report.get('n_selections',0)} "
                f"examples={report.get('n_examples',0)} cells={len(report['cells'])} "
                f"fitted={report.get('n_fitted',0)} (dry_run={report['dry_run']})"
            )
            for c in report["cells"]:
                tag = "FIT" if c["fitted"] else "skip"
                print(f"  [{tag}] {c['category']}/{c['segment']}: {c['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
