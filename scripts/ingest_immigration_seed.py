#!/usr/bin/env python3
"""[AIQ-1825] Ingest vetted immigration facts into the requirement pipeline as `pending`.

Every row lands `status='pending'`. Nothing here publishes anything: `pending` facts are not
served to an employee, and promotion into `requirement_items` stays a human decision behind
`/admin/requirement-facts` and `scripts/import_otto_facts.py --promote`.

Run from the repo root:

    # preview — fetches, decides everything, writes nothing (DEFAULT)
    python scripts/ingest_immigration_seed.py

    # write
    python scripts/ingest_immigration_seed.py --apply

    # one country at a time
    python scripts/ingest_immigration_seed.py --country GB --apply

Dry run is the default and takes the same code path as a real run — same reads, same fetches,
same decisions — so the preview's numbers are the numbers `--apply` produces. That is what makes
approving the preview meaningful.

Exits non-zero if any seed row was rejected or any source failed to fetch, unless
`--allow-rejections`: those two lists are the re-sourcing worklist, and a silent partial import
is how you end up believing you have coverage you do not.

Reads DATABASE_URL.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.immigration import executor, parsers  # noqa: E402
from backend.imports.immigration.fetcher import fetch_all  # noqa: E402

DEFAULT_SEED = REPO_ROOT / "supabase" / "seed" / "obligations" / "immigration_facts_seed.json"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("seed", nargs="?", type=Path, default=DEFAULT_SEED,
                    help=f"seed JSON (default: {DEFAULT_SEED.relative_to(REPO_ROOT)})")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default: dry run)")
    ap.add_argument("--country", metavar="CC",
                    help="restrict to one destination country, AFTER cleaning (use GB, not UK)")
    ap.add_argument(
        "--require-evidence", action="store_true",
        help="write ONLY facts whose evidence_quote was found in the fetched document. "
             "134 of the 142 seed facts carry no quote; they are stored with a real fetched "
             "source and evidence_quote=NULL unless this flag narrows the run.",
    )
    ap.add_argument(
        "--keep-unmatched-quotes", action="store_true",
        help="when an evidence_quote is NOT found in the fetched document, still write the "
             "fact with evidence_quote=NULL instead of skipping it. The unverified string is "
             "never stored either way. Use when the quotes are reviewer caveats rather than "
             "citations — which is the case for all 8 in this seed.",
    )
    ap.add_argument("--allow-rejections", action="store_true",
                    help="exit 0 even when rows were rejected or sources failed to fetch")
    ap.add_argument("--cache", type=Path, default=REPO_ROOT / ".immigration-fetch-cache.json",
                    help="where fetched bodies are stored so --apply writes the same documents "
                         "the preview was approved on (default: repo-root, gitignored)")
    ap.add_argument("--no-cache", action="store_true",
                    help="re-fetch every URL instead of reusing the cache")
    args = ap.parse_args()

    if not args.seed.exists():
        print(f"✖ no such seed file: {args.seed}")
        return 2

    try:
        seed = parsers.read_seed(args.seed)
    except parsers.RowError as exc:
        print(f"✖ {args.seed}: {exc}")
        return 2

    rows = seed.rows
    if args.country:
        wanted = args.country.upper()
        rows = [r for r in rows if r.destination_country == wanted]
        if not rows:
            print(f"✖ no facts for country {wanted!r} after cleaning "
                  f"(available: {', '.join(sorted({r.destination_country for r in seed.rows}))})")
            return 2

    print(f"read {args.seed.relative_to(REPO_ROOT) if args.seed.is_absolute() else args.seed}\n")
    print(parsers.summarise_seed(seed))
    if args.country:
        print(f"\n  --country {args.country.upper()}: {len(rows)} of {len(seed.rows)} fact(s)")
    print()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set — even a dry run reads knowledge_docs, "
              "requirement_entities and requirement_facts to decide what is a duplicate")
        return 2

    from sqlalchemy import create_engine

    # Fetch BEFORE opening the transaction. A transaction held across 86 HTTP requests gets
    # closed by the Supabase pooler, and re-fetching between the preview and --apply would mean
    # the run that lands is not the run that was approved. See fetcher.fetch_all.
    urls = list({r.source_url for r in rows})
    cached = args.cache.exists()
    print(f"fetching {len(urls)} source URL(s)"
          f"{' (reusing ' + str(args.cache.name) + ')' if cached else ''}…")

    def progress(i: int, total: int, url: str) -> None:
        print(f"  [{i}/{total}] {url}", flush=True)

    docs = fetch_all(urls, cache_path=None if args.no_cache else args.cache, progress=progress)
    print()

    engine = create_engine(db_url, future=True)
    # One transaction for the whole import: a failure halfway through must not leave one
    # country ingested and the next missing.
    with engine.begin() as conn:
        result = executor.ingest(
            conn, rows,
            fetcher=lambda url: docs[url],
            dry_run=not args.apply,
            require_evidence=args.require_evidence,
            keep_unmatched=args.keep_unmatched_quotes,
        )
        print(executor.summarise(result, dry_run=not args.apply,
                                 keep_unmatched=args.keep_unmatched_quotes))
        if not args.apply:
            conn.rollback()

    if not args.apply:
        print("\n→ nothing was written. Re-run with --apply once this preview is approved.")

    problems = len(seed.rejections) + len(result.fetch_failed) + len(result.needs_manual_evidence)
    if problems and not args.allow_rejections:
        print(f"\n✖ {problems} row(s)/source(s) need attention — see the lists above")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
