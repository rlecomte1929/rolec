#!/usr/bin/env python3
"""
Crawler pipeline CLI. Run from project root:

  python scripts/crawl_resources.py --source oslo_kommune_newcomer --dry-run
  python scripts/crawl_resources.py --country NO --city Oslo
  python scripts/crawl_resources.py --bundle oslo_pilot
  python scripts/crawl_resources.py  # full configured run

Modes: --dry-run (no writes), --parse-only (fetch+parse, no extract), --extract-only (from existing docs - future)
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.crawler.config.models import CrawlConfig
from backend.crawler.config.registry import load_sources
from backend.crawler.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("crawl")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crawl trusted sources and extract to staging (no auto-publish)"
    )
    parser.add_argument("--config", type=Path, help="Path to sources JSON config")
    parser.add_argument("--source", type=str, help="Crawl only this source name")
    parser.add_argument("--country", type=str, help="Crawl only this country code (e.g. NO)")
    parser.add_argument("--city", type=str, help="Crawl only this city")
    parser.add_argument("--dry-run", action="store_true", help="No writes, log only")
    parser.add_argument("--parse-only", action="store_true", help="Fetch and parse only, no extraction")
    parser.add_argument("--output", type=Path, help="Write JSON report to file")
    args = parser.parse_args()

    sources = load_sources(args.config)
    if not sources:
        log.error("No sources loaded. Check config path.")
        return 1

    config = CrawlConfig(
        sources=sources,
        dry_run=args.dry_run,
        parse_only=args.parse_only,
    )

    report = run_pipeline(
        config,
        source_name=args.source,
        country_code=args.country,
        city_name=args.city,
        initiated_by="crawl_resources_cli",
    )

    print("\n=== Crawl Report ===")
    print(f"Run ID: {report.run_id}")
    print(f"Documents fetched: {report.documents_fetched}")
    print(f"Documents failed: {report.documents_failed}")
    print(f"Chunks created: {report.chunks_created}")
    print(f"Resources staged: {report.resources_staged}")
    print(f"Events staged: {report.events_staged}")
    print(f"Duplicates detected: {report.duplicates_detected}")
    if report.errors:
        print("\nErrors:")
        for e in report.errors:
            print(f"  - {e}")
    if report.warnings:
        print("\nWarnings:")
        for w in report.warnings:
            print(f"  - {w}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nReport written to {args.output}")

    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
