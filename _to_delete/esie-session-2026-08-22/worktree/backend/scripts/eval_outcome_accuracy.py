#!/usr/bin/env python3
"""[AIQ-710 / P3-01d] Outcome-accuracy evaluator (closed cases only).

P3-01's third leg: measure real-world accuracy from terminal case outcomes. Read-only, no DB write.

SCOPE NOTE (see the PR/Notion): the brief's exact metric — "% of AI roadmap STEPS followed without
specialist correction" — needs a per-case total step count, which the platform does not reliably persist
today (the roadmap-representation schism: roadmap_steps is empty). So this evaluator uses the available,
faithful signal — `case_outcomes.specialist_corrections_count` → a CORRECTION-FREE closed-case rate, overall
and per corridor — gated by `--min-cases`. The step-level metric is a follow-up once roadmap steps persist.

Usage:
    python backend/scripts/eval_outcome_accuracy.py --out /tmp/oa.json --min-cases 20 --ci
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_TERMINAL_OUTCOMES = ("APPROVED", "REJECTED", "WITHDRAWN")  # PENDING = still open


def load_closed_outcomes() -> List[Dict[str, Any]]:
    """Read terminal (closed) rows from case_outcomes. The only DB seam — mocked in tests."""
    from sqlalchemy import text

    from backend.database import db

    sql = text(
        "SELECT case_ref_hash, origin_country_code, dest_country_code, outcome, "
        "       specialist_corrections_count "
        "FROM case_outcomes "
        "WHERE outcome IN ('APPROVED','REJECTED','WITHDRAWN')"
    )
    with db.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql)]


def _corridor(row: Dict[str, Any]) -> str:
    o = row.get("origin_country_code") or "??"
    d = row.get("dest_country_code") or "??"
    return f"{o}-{d}"


def build_report(rows: List[Dict[str, Any]], min_cases: int) -> Dict[str, Any]:
    """Pure aggregation — the tested core. correction_free = specialist_corrections_count == 0."""
    n = len(rows)
    corr_free = sum(1 for r in rows if (r.get("specialist_corrections_count") or 0) == 0)
    total_corr = sum(int(r.get("specialist_corrections_count") or 0) for r in rows)

    by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[_corridor(r)].append(r)

    by_corridor = []
    for corridor in sorted(by):
        grp = by[corridor]
        g_free = sum(1 for r in grp if (r.get("specialist_corrections_count") or 0) == 0)
        g_corr = sum(int(r.get("specialist_corrections_count") or 0) for r in grp)
        by_corridor.append({
            "corridor": corridor,
            "closed_cases": len(grp),
            "correction_free_rate": round(g_free / len(grp), 4) if grp else None,
            "mean_corrections": round(g_corr / len(grp), 4) if grp else None,
        })

    return {
        "sufficient": n >= min_cases,
        "closed_cases": n,
        "min_cases": min_cases,
        "accuracy": round(corr_free / n, 4) if n else None,
        "mean_corrections": round(total_corr / n, 4) if n else None,
        "by_corridor": by_corridor,
    }


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description="P3-01d outcome-accuracy evaluator (closed cases)")
    p.add_argument("--out", required=True, help="Path to write the JSON report.")
    p.add_argument("--min-cases", type=int, default=20, help="Minimum closed cases required (default 20).")
    p.add_argument("--ci", action="store_true", help="Exit 1 if there are fewer than --min-cases closed cases.")
    args = p.parse_args(argv)

    rows = load_closed_outcomes()
    report = build_report(rows, args.min_cases)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "by_corridor"}, indent=2))

    if args.ci and not report["sufficient"]:
        print(f"[INSUFFICIENT] {report['closed_cases']}/{args.min_cases} closed cases — gated until data arrives")
        sys.exit(1)


if __name__ == "__main__":
    main()
