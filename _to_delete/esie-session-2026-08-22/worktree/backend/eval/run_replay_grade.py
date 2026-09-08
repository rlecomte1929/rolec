"""
Offline replay grader (Phase 1 eval keystone).

Reads masked replay records written by backend/app/services/ai_replay_store.py and
aggregates them into the OUTCOME_ACCURACY metric (+ supporting signals) that feeds
rag_eval_reports / METRIC_SPECS. This is the evaluator that the 0.90
outcome_accuracy threshold was reserved for but never had.

Grading model (faithfulness oracle, per the locked design)
──────────────────────────────────────────────────────────
A roadmap step is "accurate" iff the pipeline's own factual_verifier already judged
it `supported` AND `citation_ok` against the retrieved authority chunks. The grader
aggregates those stored per-step verdicts — it does NOT re-run the LLM, so it is
deterministic, free, and CI-safe. RULE_NOT_FOUND is a coverage outcome (correctly
refusing on an uncovered corridor), not an accuracy failure, so it is excluded from
the outcome_accuracy denominator and reported separately.

Usage
─────
    # Grade the roadmap replay records currently in the DB, write a dated report:
    python -m backend.eval.run_replay_grade --from-db --out audit/rag_eval
    # CI gate (exit non-zero if below the outcome_accuracy threshold):
    python -m backend.eval.run_replay_grade --from-db --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROADMAP_FEATURE = "rag_roadmap"
OUTCOME_ACCURACY_THRESHOLD = 0.90  # mirrors rag_eval_reports.METRIC_SPECS


def _verification(step: Dict[str, Any]) -> Dict[str, Any]:
    return step.get("verification") or {}


def _grade_roadmap(output: Dict[str, Any]) -> Dict[str, Any]:
    """Score one assembled roadmap from its stored per-step verifier verdicts."""
    steps = output.get("steps") or []
    n_supported = sum(1 for s in steps if _verification(s).get("supported"))
    n_citation_ok = sum(1 for s in steps if _verification(s).get("citation_ok"))
    return {
        "result": output.get("result"),
        "approved": bool(output.get("approved")),
        "n_steps": len(steps),
        "n_supported": n_supported,
        "n_citation_ok": n_citation_ok,
    }


def _safe_load_output(rec: Dict[str, Any]) -> Dict[str, Any]:
    raw = rec.get("output_masked") or rec.get("output") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def grade_replay_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate roadmap replay records into an outcome_accuracy report.

    Report shape matches the files rag_eval_reports.load_live_reports() reads:
    a top-level float `aggregate` (= outcome_accuracy), a `by_corridor` map, and an
    `extra` block of supporting metrics. Safe on empty input (aggregate 0.0).
    """
    ok_grades: List[Dict[str, Any]] = []
    n_rule_not_found = 0
    by_corridor_ok: Dict[str, List[bool]] = defaultdict(list)

    for rec in records:
        if rec.get("feature_key") != _ROADMAP_FEATURE:
            continue
        grade = _grade_roadmap(_safe_load_output(rec))
        if grade["result"] == "RULE_NOT_FOUND":
            n_rule_not_found += 1
            continue
        if grade["result"] != "OK":
            continue
        ok_grades.append(grade)
        by_corridor_ok[rec.get("corridor") or "UNKNOWN"].append(grade["approved"])

    n_ok = len(ok_grades)
    n_approved = sum(1 for g in ok_grades if g["approved"])
    total_steps = sum(g["n_steps"] for g in ok_grades)
    total_supported = sum(g["n_supported"] for g in ok_grades)
    total_citation_ok = sum(g["n_citation_ok"] for g in ok_grades)

    outcome_accuracy = (n_approved / n_ok) if n_ok else 0.0
    step_support_rate = (total_supported / total_steps) if total_steps else 0.0
    citation_validity = (total_citation_ok / total_steps) if total_steps else 0.0

    by_corridor = {
        corridor: round(sum(1 for a in approvals if a) / len(approvals), 4)
        for corridor, approvals in sorted(by_corridor_ok.items())
        if approvals
    }

    return {
        "aggregate": round(outcome_accuracy, 4),
        "by_corridor": by_corridor,
        "extra": {
            "metric": "outcome_accuracy",
            "n_ok": n_ok,
            "n_approved": n_approved,
            "n_rule_not_found": n_rule_not_found,
            "step_support_rate": round(step_support_rate, 4),
            "citation_validity": round(citation_validity, 4),
            "threshold": OUTCOME_ACCURACY_THRESHOLD,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_from_db(corridor: Optional[str]) -> List[Dict[str, Any]]:
    from backend.app.services.ai_replay_store import list_replay_records

    return list_replay_records(feature_key=_ROADMAP_FEATURE, corridor=corridor, limit=5000)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade immigration-roadmap replay records.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-db", action="store_true", help="Read replay records from the DB.")
    src.add_argument("--records", type=Path, help="Read replay records from a JSON array file.")
    parser.add_argument("--corridor", default=None, help="Scope to one corridor (e.g. IN_DE).")
    parser.add_argument("--out", type=Path, default=None,
                        help="Directory to write outcome_accuracy_<date>.json into.")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if aggregate < outcome_accuracy threshold.")
    args = parser.parse_args(argv)

    if args.from_db:
        records = _load_from_db(args.corridor)
    else:
        records = json.loads(args.records.read_text())

    report = grade_replay_records(records)
    print(json.dumps(report, indent=2))

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        stamp = report["generated_at"][:10].replace("-", "")
        dest = args.out / f"outcome_accuracy_{stamp}.json"
        dest.write_text(json.dumps(report, indent=2))
        print(f"wrote {dest}", file=sys.stderr)

    if args.gate and report["aggregate"] < OUTCOME_ACCURACY_THRESHOLD:
        print(
            f"GATE FAILED: outcome_accuracy {report['aggregate']} "
            f"< {OUTCOME_ACCURACY_THRESHOLD}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
