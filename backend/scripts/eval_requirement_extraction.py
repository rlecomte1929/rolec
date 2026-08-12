#!/usr/bin/env python3
"""[AIQ-1093 / P4-04] Eval harness — requirement-fact extraction precision/recall vs a golden set.

Scores the P4-01 extractor (`extract_requirement_facts`) against a curated golden set so a prompt/model
change can't silently degrade quality. `--ci` fails the build when precision OR recall < threshold.
Read-only, NO DB. Mirrors backend/scripts/eval_rag_context_precision.py (same --ci / JSON-shape convention).

[AIQ-1821] The gate used to be trivially satisfiable. Precision on an empty denominator
returned 1.0 and only precision was checked, so a run in which the extractor read nothing
at all scored a perfect 1.0 and exited 0 — which is exactly what happened when the fetch
path was feeding raw HTML `<head>` to the model. Now: a zero-yield URL scores 0.0, recall
is gated too, an all-skipped run fails, and `zero_yield_urls` names the offenders.

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
from backend.crawler.parsers import immigration_page_parser  # noqa: E402

log = logging.getLogger("eval_requirement_extraction")

_DEFAULT_GOLDEN = _REPO_ROOT / "backend/tests/fixtures/requirement_facts_eval/golden.jsonl"


_PAGES_DIR = _DEFAULT_GOLDEN.parent / "pages"


def load_golden(path: str) -> List[Dict[str, Any]]:
    """Load the golden set, skipping the `_meta` header line (repo fixture convention)."""
    entries: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "_meta" in row:
                continue
            entries.append(row)
    return entries


def _fixture_content(entry: Dict[str, Any], pages_dir: Path) -> Optional[str]:
    """Parsed article text from an entry's committed HTML snapshot, if it has one.

    [AIQ-1821] The golden set is snapshot-backed so this eval is deterministic and offline.
    Live government URLs made it flaky in both directions: a fetch failure was silently
    skipped, and a fully failed run still exited 0. `extract_requirement_facts` already
    accepts `content=` to bypass the network — that seam is what this uses.

    Returns PARSED text, not raw HTML, because that is what `fetch_url_content` returns
    post-fix. Passing raw HTML here would measure a pipeline that no longer exists.
    """
    name = entry.get("html_fixture")
    if not name:
        return None
    path = pages_dir / name
    if not path.exists():
        raise FileNotFoundError(f"golden entry references a missing snapshot: {path}")
    parsed = immigration_page_parser.parse(path.read_text(encoding="utf-8"))
    return (parsed.get("text") or "").strip()


def _fact_matches_expected(fact: Any, expected: Dict[str, Any]) -> bool:
    tc = str(expected.get("text_contains") or "").strip().lower()
    if not tc or tc not in (getattr(fact, "text", "") or "").lower():
        return False
    rtype = str(expected.get("requirement_type") or "").strip().lower()
    return (not rtype) or getattr(fact, "requirement_type", "") == rtype


def eval_entry(entry: Dict[str, Any], pages_dir: Path = _PAGES_DIR) -> Optional[Dict[str, Any]]:
    """Run the extractor for one golden entry and score it. None = skip (fetch error)."""
    url = entry["url"]
    expected = entry.get("expected_facts") or []
    content = _fixture_content(entry, pages_dir)
    try:
        facts = asyncio.run(
            extract_requirement_facts(url, corridor=entry.get("corridor", ""), content=content)
        )
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
    # [AIQ-1821] A URL the extractor read nothing from is a FAILURE, not a perfect score.
    # This previously returned 1.0 on the empty denominator, so a page whose body was
    # never parsed scored precision 1.0 and the --ci gate went green on a broken run.
    return {
        "url": url,
        "corridor": entry.get("corridor", ""),
        "extracted": n_ext,
        "expected": n_exp,
        "matched_extracted": matched_extracted,
        "matched_expected": matched_expected,
        "precision": (matched_extracted / n_ext) if n_ext else (1.0 if not n_exp else 0.0),
        "recall": (matched_expected / n_exp) if n_exp else 1.0,
    }


def build_report(entries: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    by_url = [row for row in (eval_entry(e) for e in entries) if row is not None]
    total_ext = sum(r["extracted"] for r in by_url)
    total_exp = sum(r["expected"] for r in by_url)
    matched_ext = sum(r["matched_extracted"] for r in by_url)
    matched_exp = sum(r["matched_expected"] for r in by_url)
    precision = (matched_ext / total_ext) if total_ext else 0.0
    recall = (matched_exp / total_exp) if total_exp else 0.0
    # [AIQ-1821] Count URLs the extractor returned nothing for. These are the runs the
    # old gate scored 1.0 — surfaced explicitly so a silently-degraded extractor is
    # visible in the report rather than hidden behind an aggregate.
    zero_yield = [r["url"] for r in by_url if r["extracted"] == 0]
    # Gate on BOTH precision and recall: precision alone is trivially satisfied by
    # extracting almost nothing, which is exactly the failure mode this eval missed.
    passes = (
        len(by_url) > 0
        and precision >= threshold
        and recall >= threshold
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "threshold": threshold,
        "passes_threshold": passes,
        "entries_evaluated": len(by_url),
        "entries_skipped": len(entries) - len(by_url),
        "zero_yield_urls": zero_yield,
        "by_url": by_url,
    }


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="P4-04 requirement-fact extraction precision/recall eval")
    p.add_argument("--golden", default=str(_DEFAULT_GOLDEN), help="Path to the golden-set JSONL.")
    p.add_argument("--out", required=True, help="Path to write the JSON report.")
    # [AIQ-1821] 0.60 is derived from a measured baseline, not chosen aspirationally: three
    # runs over the v2 snapshot set gave precision 0.698/0.734/0.729 and recall 0.909-1.000.
    # 0.60 sits ~0.10 below the observed precision minimum, which is the margin the observed
    # run-to-run spread (temperature 0.2) requires. Re-measure before tightening it.
    p.add_argument("--threshold", type=float, default=0.60,
                   help="Precision AND recall floor for CI gating (default 0.60, measured).")
    p.add_argument("--ci", action="store_true", help="Exit 1 if precision or recall < threshold.")
    p.add_argument("--emit-dashboard", metavar="DIR",
                   help="Also write <metric>_<date>.json to DIR for /admin/rag-quality.")
    args = p.parse_args(argv)

    entries = load_golden(args.golden)
    print(f"Loaded {len(entries)} golden entries from {args.golden}")
    report = build_report(entries, args.threshold)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "by_url"}, indent=2))

    if report["zero_yield_urls"]:
        print(f"[WARN] extractor returned 0 facts for {len(report['zero_yield_urls'])} URL(s):")
        for u in report["zero_yield_urls"]:
            print(f"         {u}")

    if args.emit_dashboard:
        # Filename prefix must equal the METRIC_SPECS key or load_live_reports skips the file.
        # `aggregate` is RECALL, not precision: with substring matching, precision is depressed
        # by every additional true fact the model finds beyond the curated expectations, so it
        # penalises a better extractor. Recall answers the question the dashboard is for —
        # is the pipeline still finding the requirements we know are on the page.
        from backend.eval.dashboard_report import write_dashboard_report

        dest = write_dashboard_report(
            Path(args.emit_dashboard),
            "requirement_extraction_recall",
            report["recall"],
            {k: v for k, v in report.items() if k != "by_url"},
        )
        print(f"[dashboard] wrote {dest}")

    if args.ci and not report["passes_threshold"]:
        if not report["entries_evaluated"]:
            # Every entry was skipped (fetch/LLM errors). Nothing was measured, so the
            # run proves nothing — it must not be reported as a pass.
            print("[FAIL] no golden entries were evaluated — nothing was measured")
        else:
            print(
                f"[FAIL] precision {report['precision']} / recall {report['recall']} "
                f"< threshold {args.threshold}"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
