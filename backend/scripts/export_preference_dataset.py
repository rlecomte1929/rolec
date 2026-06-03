#!/usr/bin/env python3
"""
Export a DPO-style preference dataset (Parker Step E) as newline-delimited JSON.

Pulls human review verdicts (``ai_human_feedback``) for a task, builds
``{prompt, chosen, rejected}`` pairs via preference_dataset_builder, and writes
them to a ``.jsonl`` file for offline DPO/KTO fine-tuning or canary re-ranking.
No training is run here — this just emits the dataset.

Usage::

    python -m backend.scripts.export_preference_dataset \
        --task-key policy_assistant_answer \
        --out preferences/policy_assistant_answer_$(date +%Y%m%d).jsonl

    # Default --out path (preferences/<task>_<YYYYMMDD>.jsonl) if omitted:
    python -m backend.scripts.export_preference_dataset --task-key policy_extraction

Exit codes:
  0 — dataset written (possibly empty)
  2 — bad arguments
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.preference_dataset_builder import (  # noqa: E402
    DPOPair,
    build_dpo_pairs,
)


def write_jsonl(pairs: List[DPOPair], out_path: Path) -> int:
    """Write one JSON object per line. Creates parent dirs. Returns line count."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair.to_jsonl_obj(), ensure_ascii=False))
            fh.write("\n")
    return len(pairs)


def _default_out(task_key: str) -> Path:
    return Path("preferences") / f"{task_key}_{date.today():%Y%m%d}.jsonl"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a DPO preference dataset (JSONL) from human review verdicts."
    )
    parser.add_argument("--task-key", required=True, help="prompt_versions.task_key to export")
    parser.add_argument("--out", default=None, help="output .jsonl path (default: preferences/<task>_<date>.jsonl)")
    parser.add_argument("--min-pairs", type=int, default=50, help="soft target; warns if fewer (default: 50)")
    args = parser.parse_args(argv)

    out_path = Path(args.out) if args.out else _default_out(args.task_key)
    pairs = build_dpo_pairs(args.task_key, min_pairs=args.min_pairs)
    n = write_jsonl(pairs, out_path)
    print(f"Wrote {n} preference pair(s) for task_key={args.task_key!r} → {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
