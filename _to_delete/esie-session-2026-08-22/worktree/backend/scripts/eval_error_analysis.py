"""CLI: run the offline AI eval gates and write an error-analysis report.

    # Human summary + write audit/eval/error_analysis_<date>.{md,json}
    python -m backend.scripts.eval_error_analysis

    # Machine-readable only (no file write)
    python -m backend.scripts.eval_error_analysis --json

    # Custom output dir
    python -m backend.scripts.eval_error_analysis --out-dir audit/eval

Exit code is the combined gate verdict (0 = all offline gates green, 1 = a gate
failed), so this doubles as a local "are the AI eval gates green?" check. (The
individual refusal/PII gates are already enforced in CI via their pytest
assertions in backend/tests/; this script adds the cross-gate error-analysis
view the dashboard lacked.)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Make ``backend...`` importable from repo root or from inside backend/.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.eval.error_analysis import build_error_analysis, render_markdown  # noqa: E402
from backend.eval.grader import run_all_offline_gates  # noqa: E402


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AI eval error analysis.")
    parser.add_argument(
        "--out-dir",
        default=os.path.join(_REPO_ROOT, "audit", "eval"),
        help="Directory to write error_analysis_<date>.{md,json} (default: audit/eval).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the JSON analysis to stdout and do NOT write report files.",
    )
    args = parser.parse_args(argv)

    combined = run_all_offline_gates()
    analysis = build_error_analysis(combined)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        md_path = out_dir / f"error_analysis_{stamp}.md"
        json_path = out_dir / f"error_analysis_{stamp}.json"
        md_path.write_text(render_markdown(analysis, generated_at), encoding="utf-8")
        json_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        print(render_markdown(analysis, generated_at))
        print(f"\nWrote {md_path}\nWrote {json_path}")

    return 0 if combined["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
