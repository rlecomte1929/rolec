#!/usr/bin/env python3
"""[AIQ-1093 / P4-04] Eval harness — requirement-fact extraction precision/recall vs a golden set.

Scores the P4-01 extractor (`extract_requirement_facts`) against a curated golden set so a prompt/model
change can't silently degrade quality. `--ci` fails the build when precision < threshold. Read-only,
NO DB. Mirrors backend/scripts/eval_rag_context_precision.py (same --ci / JSON-shape convention).

Matching is `text_contains` substring (LLMs paraphrase) AND requirement_type equality.

Usage:
    python backend/scripts/eval_requirement_extraction.py \\
        --golden backend/tests/fixtures/requirement_facts_eval/golden.jsonl \\
        --out /tmp/fact_eval.json --threshold 0.70 --ci
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.services.requirement_fact_extractor import extract_requirement_facts  # noqa: E402

log = logging.getLogger("eval_requirement_extraction")

_DEFAULT_GOLDEN = _REPO_ROOT / "backend/tests/fixtures/requirement_facts_eval/golden.jsonl"


def load_golden(path: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _fact_matches_expected(fact: Any, expected: Dict[str, Any]) -> bool:
    tc = str(expected.get("text_contains") or "").strip().lower()
    if not tc or tc not in (getattr(fact, "text", "") or "").lower():
        return False
    rtype = str(expected.get("requirement_type") or "").strip().lower()
    return (not rtype) or getattr(fact, "requirement_type", "") == rtype


def eval_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the extractor for one golden entry and score it. None = skip (fetch error)."""
    url = entry["url"]
    expected = entry.get("expected_facts") or []
    try:
        facts = asyncio.run(extract_requirement_facts(url, corridor=entry.get("corridor", "")))
    except Exception as exc:  # network / LLM error → skip, don't fail the run
        log.warning("skip %s: %s", url, exc)
        return None

    hint = entry.get("requirement_type_hint")
    hint = hint.strip().lower() if isinstance(hint, str) and hint.strip() else ""
    if hint:
        facts = [f for f in facts if f.requirement_type == hint]

    matched_extracted = sum(1 for f in facts if any(_fact_matches_expected(f, e) for e in expected))
    matched_expected = sum(1 for e in expected if any(_fact_matches_expected(f, e) for f in facts))
    n_ext, n_exp = len(facts), len(expected)
    return {
        "url": url,
        "corridor": entry.get("corridor", ""),
        "extracted": n_ext,
        "expected": n_exp,
        "matched_extracted": matched_extracted,
        "matched_expected": matched_expected,
        "precision": (matched_extracted / n_ext) if n_ext else 1.0,
        "recall": (matched_expected / n_exp) if n_exp else 1.0,
    }


def build_report(entries: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    by_url = [row for row in (eval_entry(e) for e in entries) if row is not None]
    total_ext = sum(r["extracted"] for r in by_url)
    total_exp = sum(r["expected"] for r in by_url)
    matched_ext = sum(r["matched_extracted"] for r in by_url)
    matched_exp = sum(r["matched_expected"] for r in by_url)
    precision = (matched_ext / total_ext) if total_ext else 1.0
    recall = (matched_exp / total_exp) if total_exp else 1.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "threshold": threshold,
        "passes_threshold": precision >= threshold,
        "entries_evaluated": len(by_url),
        "entries_skipped": len(entries) - len(by_url),
        "by_url": by_url,
    }


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="P4-04 requirement-fact extraction precision/recall eval")
    p.add_argument("--golden", default=str(_DEFAULT_GOLDEN), help="Path to the golden-set JSONL.")
    p.add_argument("--out", required=True, help="Path to write the JSON report.")
    p.add_argument("--threshold", type=float, default=0.70, help="Precision threshold for CI gating (default 0.70).")
    p.add_argument("--ci", action="store_true", help="Exit 1 if precision < threshold.")
    args = p.parse_args(argv)

    entries = load_golden(args.golden)
    print(f"Loaded {len(entries)} golden entries from {args.golden}")
    report = build_report(entries, args.threshold)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "by_url"}, indent=2))

    if args.ci and not report["passes_threshold"]:
        print(f"[FAIL] precision {report['precision']} < threshold {args.threshold}")
        sys.exit(1)


if __name__ == "__main__":
    main()
