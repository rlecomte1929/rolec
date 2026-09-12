#!/usr/bin/env python3
"""RPX-05 consensus CLI — merge N independent research passes into candidate corridor facts.

Pipeline shape (authoring layer; nothing here serves or calls an LLM):

    N research workers  ─►  passes/*.jsonl  ─►  [this script]  ─►  <batch>.consensus.jsonl
    (Otto / LLM, each a       (one file per         merge +          <batch>.gaps.jsonl
     small single-corridor     pass, JSONL of       eval             <batch>.run-report.md
     task, files to GCS)       FactRow objects)                            │
                                                                          ▼
                                            scripts/import_otto_facts.py <consensus.jsonl>
                                            --apply --promote  → requirement_items (pending)

The reliability lives in the *deterministic merge* (see backend/imports/otto/consensus.py),
not in any single model call — that is what makes corridor knowledge trustworthy at scale and
refreshable on a schedule (re-run the passes; a fact that falls out of consensus is your
staleness signal).

Run from the repo root:

    # one JSONL file per research pass, all in a directory
    python scripts/rpx_consensus.py path/to/passes_dir --batch-id RPX-05-fr-no-2026-09-12

    # or an explicit glob
    python scripts/rpx_consensus.py 'audos-workspace-776786/data/RPX-05-*pass*.jsonl' \\
        --batch-id RPX-05-fr-no-2026-09-12 --out-dir audos-workspace-776786/data
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.otto.consensus import (  # noqa: E402
    ConsensusResult,
    evaluate_consensus,
    merge_passes,
)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"✖ {path}:{i}: invalid JSON — {exc}")
    return rows


def _resolve_pass_files(target: str) -> List[Path]:
    p = Path(target)
    if p.is_dir():
        return sorted(p.glob("*.jsonl"))
    return sorted(Path(m) for m in glob.glob(target))


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _run_report_md(batch_id: str, result: ConsensusResult, ev: Dict[str, Any], n_passes: int) -> str:
    hist = ev.get("pass_count_histogram", {})
    hist_lines = "\n".join(f"| {k}/{n_passes} | {v} |" for k, v in hist.items()) or "| — | 0 |"
    gaps_lines = "\n".join(
        f"| {g['destination_country']} | {g['entity_topic_key']} | {g['fact_key']} | "
        f"{g['pass_count']}/{n_passes} | {g['reason']} |"
        for g in result.gaps
    ) or "| — | — | — | — | (none) |"
    return f"""# RPX-05 run report — {batch_id}

**Passes:** {n_passes}  ·  **Verdict:** {ev['verdict']}

| Metric | Value |
|---|---|
| consensus rows | {ev['n_consensus']} |
| needs_review rows | {ev['n_needs_review']} |
| gaps | {ev['n_gaps']} |
| citation coverage (consensus) | {ev['citation_coverage']:.0%} |
| statutory ratio (consensus) | {ev['statutory_ratio']:.0%} |
| gap ratio | {ev['gap_ratio']:.0%} |

## Pass-count histogram (included rows)

| pass_count | rows |
|---|---|
{hist_lines}

## Gaps — the re-sourcing worklist (never fabricated into a fact)

| dest | entity_topic | fact_key | pass_count | reason |
|---|---|---|---|---|
{gaps_lines}

{("**Warnings:** " + "; ".join(ev["warnings"])) if ev.get("warnings") else ""}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("passes", help="directory of *.jsonl pass files, or a glob")
    ap.add_argument("--batch-id", required=True, help="batch id, used for output filenames")
    ap.add_argument("--out-dir", default=".", help="where to write the three deliverables (default: cwd)")
    ap.add_argument("--n-passes", type=int, help="override pass count (default: number of files read)")
    args = ap.parse_args()

    files = _resolve_pass_files(args.passes)
    if not files:
        print(f"✖ no pass files matched: {args.passes}")
        return 2

    passes = [_read_jsonl(f) for f in files]
    print(f"read {len(files)} pass file(s):")
    for f, rows in zip(files, passes):
        print(f"  {f}  ({len(rows)} fact(s))")
    print()

    result = merge_passes(passes, n_passes=args.n_passes)
    n = args.n_passes if args.n_passes is not None else len(files)
    ev = evaluate_consensus(result)

    out = Path(args.out_dir)
    consensus_path = out / f"{args.batch_id}.consensus.jsonl"
    gaps_path = out / f"{args.batch_id}.gaps.jsonl"
    report_path = out / f"{args.batch_id}.run-report.md"
    _write_jsonl(consensus_path, result.consensus)
    _write_jsonl(gaps_path, result.gaps)
    report_path.write_text(_run_report_md(args.batch_id, result, ev, n), encoding="utf-8")

    print(f"verdict: {ev['verdict']}   "
          f"consensus={ev['n_consensus']}  needs_review={ev['n_needs_review']}  gaps={ev['n_gaps']}")
    print(f"citation_coverage={ev['citation_coverage']:.0%}  statutory_ratio={ev['statutory_ratio']:.0%}  "
          f"gap_ratio={ev['gap_ratio']:.0%}")
    for w in ev.get("warnings", []):
        print(f"  ⚠ {w}")
    print()
    print("wrote:")
    for p in (consensus_path, gaps_path, report_path):
        n_lines = len(p.read_text(encoding="utf-8").splitlines())
        print(f"  {p}  ({n_lines} line(s))")
    print()
    print("Next: review the run-report, then load the consensus file as candidates (pending):")
    print(f"  python scripts/import_otto_facts.py {consensus_path} --apply --promote")

    # needs_review rows are candidates too, just lawyer-flagged; emit them beside consensus so
    # nothing is silently dropped. They share the consensus file's fate at load time.
    if result.needs_review:
        nr_path = out / f"{args.batch_id}.needs_review.jsonl"
        _write_jsonl(nr_path, result.needs_review)
        print(f"  (also wrote {nr_path} — {len(result.needs_review)} lawyer-flagged candidate(s))")

    return 0 if ev["verdict"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
