"""Score over-serving: what a roadmap told an audience that it must never tell them.

    python -m backend.eval.run_overserving_eval --profiles &lt;jsonl&gt; [--gate] [--out DIR]

Runs the committed case profiles through the real `derive_roadmap` and counts
`must_not_serve` matches in the produced steps and advisories.

**Report filename.** `dashboard_report.write_dashboard_report` names the file by metric key,
and `rag_eval_reports._metric_key_for_filename` matches by `startswith` over `METRIC_SPECS`
in list order. A key beginning `nonobvious_recall` would therefore be captured by the recall
spec and plotted on the recall chart. This metric is `overserved_requirements` for that
reason, and must never be renamed into that prefix.

**Direction.** `load_live_reports` hardcodes `passes_threshold = aggregate &gt;= threshold`, so a
count-down metric reads backwards on that dashboard. The emitted `aggregate` is therefore
1.0 (clean) or 0.0 (any violation), with the raw count and the named violations carried in
the payload where they can be read without being inverted.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .dashboard_report import write_dashboard_report
from .nonobvious_recall import load_baseline
from .overserving import score_overserving

METRIC_KEY = "overserved_requirements"


def _load_produced(path: Path) -> Dict[str, List[List[Dict[str, Any]]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "slices" in raw:
        raw = raw["slices"]
    out: Dict[str, List[List[Dict[str, Any]]]] = {}
    for sid, roadmaps in (raw or {}).items():
        norm: List[List[Dict[str, Any]]] = []
        for rm in roadmaps or []:
            norm.append(list(rm.get("steps", [])) if isinstance(rm, dict) else list(rm))
        out[sid] = norm
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Score corridor over-serving.")
    ap.add_argument("--baseline", type=Path, default=None)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--profiles", type=Path,
                     help="Committed case profiles, run through the real engine.")
    src.add_argument("--produced", type=Path,
                     help="Hand-written roadmaps. For poisoned-input tests ONLY — this is "
                          "not a measurement of the engine.")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--max-violations", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--today", default=None)
    args = ap.parse_args(argv)

    baseline = load_baseline(args.baseline)

    if args.profiles is not None:
        from .nonobvious_harness import build_produced, load_profiles
        steps, advisories = build_produced(load_profiles(args.profiles))
    else:
        print("WARNING: --produced is hand-written input; this is not a measurement of the "
              "engine.", file=sys.stderr)
        steps, advisories = _load_produced(args.produced), {}

    result = score_overserving(baseline, steps, advisories)

    # "Nothing was checked" must never print like "nothing was wrong".
    if result["measured_slices"] == 0:
        print("FAIL: no slice produced a roadmap — nothing was measured.", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.out:
        aggregate = 1.0 if result["violations"] == 0 else 0.0
        write_dashboard_report(args.out, METRIC_KEY, aggregate, result, today=args.today)

    if args.gate:
        if result["unmeasured_slices"]:
            print(f"FAIL: unmeasured slices {result['unmeasured_slices']}", file=sys.stderr)
            return 1
        if result["violations"] > args.max_violations:
            print(f"FAIL: {result['violations']} over-serving violation(s) "
                  f"(max {args.max_violations})", file=sys.stderr)
            for s in result["slices"]:
                for v in s["violated"]:
                    print(f"  {s['corridor']}:{s['employee_type']} -> {v['key']} "
                          f"(match={v['match']!r})", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
