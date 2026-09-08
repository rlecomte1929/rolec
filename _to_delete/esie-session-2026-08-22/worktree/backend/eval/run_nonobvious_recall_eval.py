"""
Sliced non-obvious recall eval runner \u2014 the replacement for the retired
aggregate 'corridor completeness %' reporting.

Scores produced roadmaps per (corridor x employee_type) slice against the
lawyer-verified HLP baseline (``hlp_nonobvious_baseline.json``) and emits the
``nonobvious_recall_<date>.json`` dashboard report. The report's top-level
``aggregate`` is the WORST slice's recall \u2014 a minimum, never an average \u2014 so
the dashboard alert fires exactly when any one slice misses any one
non-obvious requirement.

Usage
\u2500\u2500\u2500\u2500\u2500
    # Score the committed sample and emit the dashboard report:
    python -m backend.eval.run_nonobvious_recall_eval \
        --produced backend/tests/fixtures/eval/nonobvious/produced_slices_sample.json \
        --out audit/rag_eval --gate

``--produced`` is a JSON object mapping ``"<CORRIDOR>:<employee_type>"`` (e.g.
``"ES_IE:non_eu_passport_holder"``) to a list of produced roadmaps; each
roadmap is a list of step objects or ``{"steps": [...]}``.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .nonobvious_recall import load_baseline, score_slices


def _normalise_roadmaps(raw: Any) -> List[List[Dict[str, Any]]]:
    """Accept ``[[step,...], ...]`` or ``[{"steps": [...]}, ...]``."""
    out: List[List[Dict[str, Any]]] = []
    for roadmap in raw or []:
        if isinstance(roadmap, dict):
            out.append(roadmap.get("steps") or [])
        else:
            out.append(roadmap)
    return out


def load_produced(path: Path) -> Dict[str, List[List[Dict[str, Any]]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("slices"), dict):
        data = data["slices"]
    if not isinstance(data, dict):
        raise ValueError("--produced must be a JSON object mapping 'CORRIDOR:employee_type' to roadmaps")
    return {key: _normalise_roadmaps(value) for key, value in data.items()}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grade non-obvious requirement recall per (corridor x employee_type) "
        "slice vs the lawyer-verified HLP baseline. No averages: worst slice first."
    )
    parser.add_argument("--baseline", type=Path, default=None,
                        help="HLP baseline JSON (default: backend/eval/hlp_nonobvious_baseline.json).")
    parser.add_argument("--produced", type=Path, required=True,
                        help="JSON object mapping 'CORRIDOR:employee_type' to produced roadmaps.")
    parser.add_argument("--min-recall", type=float, default=1.0,
                        help="Gate threshold applied to the WORST slice (default 1.0 \u2014 a single "
                             "missed non-obvious requirement anywhere fails the gate).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if the worst slice's recall < --min-recall or any slice has no data.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Dir to write nonobvious_recall_<date>.json (rag-eval dashboard).")
    parser.add_argument("--today", type=str, default=None,
                        help="YYYY-MM-DD stamp for the report filename (default: today).")
    args = parser.parse_args(argv)

    baseline = load_baseline(args.baseline)
    produced = load_produced(args.produced)
    result = score_slices(baseline, produced)

    report = {
        "metric": "nonobvious_recall",
        "baseline_version": baseline.get("version"),
        **result,
    }
    print(json.dumps(report, indent=2))

    if result["worst_recall"] is None:
        print("GATE FAILED: no slice has any produced roadmaps \u2014 nothing was measured.", file=sys.stderr)
        return 1

    if args.out:
        from .dashboard_report import write_dashboard_report
        today = date.fromisoformat(args.today) if args.today else None
        # aggregate == worst slice recall (a minimum, deliberately NOT a mean).
        dest = write_dashboard_report(args.out, "nonobvious_recall", result["worst_recall"], report, today=today)
        print(f"wrote {dest}", file=sys.stderr)

    if args.gate:
        failed = False
        if result["worst_recall"] < args.min_recall:
            worst = result["worst_slice"]
            print(
                f"GATE FAILED: worst slice {worst['corridor']} x {worst['employee_type']} "
                f"recall {worst['recall']} < {args.min_recall}. Missing: {worst['missing']}",
                file=sys.stderr,
            )
            failed = True
        if result["unscored_slices"]:
            unmeasured = [
                f"{s['corridor']} x {s['employee_type']}" for s in result["slices"] if s["recall"] is None
            ]
            print(f"GATE FAILED: slices with no produced roadmaps (unmeasured): {unmeasured}", file=sys.stderr)
            failed = True
        if failed:
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
