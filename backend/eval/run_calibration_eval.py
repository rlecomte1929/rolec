"""
Confidence-calibration runner (deepen-evals slice 2).

Reads immigration-answer replay records and reports the reliability curve + ECE +
calibration_score (calibration_metrics.score_calibration). Emits the dashboard
metric `calibration_score`. No LLM, no deploy needed.

    python -m backend.eval.run_calibration_eval --from-db --out audit/rag_eval
    python -m backend.eval.run_calibration_eval --records recs.json --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .calibration_metrics import score_calibration

CALIBRATION_THRESHOLD = 0.90


def _load_from_db(corridor: Optional[str]) -> List[Dict[str, Any]]:
    from backend.app.services.ai_replay_store import list_replay_records

    return list_replay_records(feature_key="immigration_answer", corridor=corridor, limit=5000)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Score immigration-answer confidence calibration.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-db", action="store_true")
    src.add_argument("--records", type=Path)
    parser.add_argument("--corridor", default=None)
    parser.add_argument("--out", type=Path, default=None,
                        help="Dir to write calibration_score_<date>.json (rag-eval dashboard).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if calibration_score < threshold (only when answers exist).")
    args = parser.parse_args(argv)

    records = _load_from_db(args.corridor) if args.from_db else json.loads(args.records.read_text())
    report = score_calibration(records)
    print(json.dumps(report, indent=2))

    if args.out:
        from .dashboard_report import write_dashboard_report
        dest = write_dashboard_report(args.out, "calibration_score", report["aggregate"], report)
        print(f"wrote {dest}", file=sys.stderr)

    if args.gate and report["extra"]["n_answered"] > 0 and report["aggregate"] < CALIBRATION_THRESHOLD:
        print(f"GATE FAILED: calibration_score {report['aggregate']} < {CALIBRATION_THRESHOLD} "
              f"(overconfident: {report['extra']['overconfident_buckets']})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
