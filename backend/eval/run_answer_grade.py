"""
Answer-faithfulness grader runner (deepen-evals slice 1).

Reads immigration-answer replay records and reports grounding/citation/refusal
metrics (answer_metrics.grade_answer_records). Emits the dashboard metric
`answer_grounding`. No LLM, no deploy needed.

    python -m backend.eval.run_answer_grade --from-db --out audit/rag_eval --gate
    python -m backend.eval.run_answer_grade --records recs.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .answer_metrics import grade_answer_records

ANSWER_GROUNDING_THRESHOLD = 0.90


def _load_from_db(corridor: Optional[str]) -> List[Dict[str, Any]]:
    from backend.app.services.ai_replay_store import list_replay_records

    return list_replay_records(feature_key="immigration_answer", corridor=corridor, limit=5000)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Grade immigration-answer faithfulness from replay records.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-db", action="store_true")
    src.add_argument("--records", type=Path)
    parser.add_argument("--corridor", default=None)
    parser.add_argument("--out", type=Path, default=None,
                        help="Dir to write answer_grounding_<date>.json (rag-eval dashboard).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if grounding_rate < threshold (only when answers exist).")
    args = parser.parse_args(argv)

    records = _load_from_db(args.corridor) if args.from_db else json.loads(args.records.read_text())
    report = grade_answer_records(records)
    print(json.dumps(report, indent=2))

    if args.out:
        from .dashboard_report import write_dashboard_report
        dest = write_dashboard_report(args.out, "answer_grounding", report["aggregate"], report)
        print(f"wrote {dest}", file=sys.stderr)

    if args.gate and report["extra"]["n_answered"] > 0 and report["aggregate"] < ANSWER_GROUNDING_THRESHOLD:
        print(f"GATE FAILED: answer_grounding {report['aggregate']} < {ANSWER_GROUNDING_THRESHOLD}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
