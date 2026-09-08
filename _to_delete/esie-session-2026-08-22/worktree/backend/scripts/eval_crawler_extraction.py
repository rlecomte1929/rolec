#!/usr/bin/env python3
"""[AIQ-1096 / CRAWL-03] Eval harness — crawler LLM-extraction yield vs rule-based baseline.

Runs BOTH resource extractors over a fixed fixture of pages and reports how many candidates
each yields, validating (and regression-guarding) Phase-2's claim that the LLM extractor
recovers recall on pages where the rule-based extractor finds nothing.

Read-only: fetches pages and runs extractors; NO DB writes. Mirrors the CLI of
backend/scripts/eval_rag_context_precision.py.

Usage:
    python backend/scripts/eval_crawler_extraction.py \\
        --pages backend/tests/fixtures/crawler_eval/sample_pages.jsonl \\
        --out /tmp/crawler_eval.json --ci
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

from backend.crawler.fetchers.http_fetcher import fetch_page  # noqa: E402
from backend.crawler.parsers.html_parser import parse_html  # noqa: E402
from backend.crawler.chunkers.chunker import chunk_document  # noqa: E402
from backend.crawler.extractors.resource_extractor import extract_resource_candidates  # noqa: E402
from backend.crawler.extractors.llm_resource_extractor import extract_resource_candidates_llm  # noqa: E402
from backend.crawler.config.models import CrawlSource  # noqa: E402

log = logging.getLogger("eval_crawler_extraction")

_DEFAULT_PAGES = _REPO_ROOT / "backend/tests/fixtures/crawler_eval/sample_pages.jsonl"


def load_pages(path: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _source_for(entry: Dict[str, Any]) -> CrawlSource:
    return CrawlSource(
        source_name=f"eval:{entry.get('country_code', '??')}",
        base_url=entry["url"],
        country_code=entry.get("country_code", ""),
        country_name=entry.get("country_name", ""),
        trust_tier=entry.get("trust_tier", "T0"),
        content_domain=entry.get("content_domain", "admin_essentials"),
    )


def eval_page(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fetch + chunk one page, run both extractors, return a per-page row (None = skip).

    Fetch/parse errors (e.g. a 404 during CI) are logged and skipped rather than failing
    the whole run — the eval is best-effort over live pages.
    """
    url = entry["url"]
    try:
        fetched = fetch_page(url)
        if not fetched.success:
            log.warning("skip %s: fetch failed (%s)", url, getattr(fetched, "error", None) or getattr(fetched, "http_status", "?"))
            return None
        doc = parse_html(fetched.content, url)
        chunks = chunk_document(
            doc,
            source_url=fetched.final_url,
            page_title=doc.page_title,
            country_code=entry.get("country_code", ""),
            city_name="",
        )
    except Exception as exc:  # network / parse error → skip, don't fail the run
        log.warning("skip %s: %s", url, exc)
        return None

    source = _source_for(entry)
    title = doc.page_title or url
    rule = extract_resource_candidates(chunks, source, fetched.final_url, title)
    llm = asyncio.run(extract_resource_candidates_llm(chunks, source, fetched.final_url, title))
    rb, lc = len(rule), len(llm)
    return {
        "url": url,
        "country_code": entry.get("country_code", ""),
        "rule_based_count": rb,
        "llm_count": lc,
        "recovered": rb == 0 and lc > 0,
        "expected_min_candidates": entry.get("expected_min_candidates"),
    }


def build_report(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_page = [row for row in (eval_page(e) for e in entries) if row is not None]
    rule_based_yield = sum(r["rule_based_count"] for r in by_page)
    llm_yield = sum(r["llm_count"] for r in by_page)
    low_recall = [r for r in by_page if r["rule_based_count"] == 0]
    return {
        "pages_evaluated": len(by_page),
        "pages_skipped": len(entries) - len(by_page),
        "rule_based_yield": rule_based_yield,
        "llm_yield": llm_yield,
        "llm_lift": llm_yield - rule_based_yield,
        "low_recall_pages": len(low_recall),
        "pages_where_llm_recovers_recall": sum(1 for r in low_recall if r["llm_count"] > 0),
        "by_page": by_page,
    }


def ci_exit_code(report: Dict[str, Any]) -> int:
    """Core Phase-2 gate: on any page where rule-based yields 0, the LLM must yield > 0.
    Also fails if the overall lift went negative."""
    low_recall = [r for r in report["by_page"] if r["rule_based_count"] == 0]
    if any(r["llm_count"] == 0 for r in low_recall):
        return 1
    if report["llm_lift"] < 0:
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="CRAWL-03 crawler LLM-extraction yield eval (vs rule-based baseline)")
    p.add_argument("--pages", default=str(_DEFAULT_PAGES), help="Path to the fixture JSONL.")
    p.add_argument("--out", required=True, help="Path to write the JSON report.")
    p.add_argument("--ci", action="store_true", help="Exit 1 if the LLM fails to recover recall on a low-recall page.")
    args = p.parse_args(argv)

    entries = load_pages(args.pages)
    print(f"Loaded {len(entries)} fixture pages from {args.pages}")
    report = build_report(entries)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "by_page"}, indent=2))

    if args.ci:
        sys.exit(ci_exit_code(report))


if __name__ == "__main__":
    main()
