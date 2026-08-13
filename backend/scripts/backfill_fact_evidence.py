#!/usr/bin/env python3
"""[AIQ-1821] Give the review queue something to show: archive sources, then prove the quotes.

WHY. 686 requirement facts are pending across 12 destinations and only 51 have archived source
text to check a claim against (average 441 chars, because the old ingest capped excerpts at 5k
and mostly failed to fetch). A queue built on that shows an approve button with no evidence
behind it. This backfill is the precondition for the queue being honest.

WHAT IT DOES
  1. Re-fetches each distinct source_url through the FIXED parser (immigration_page_parser),
     the one PR #1828 wired in — the old path fed raw HTML head-first and captured nav chrome.
  2. Updates knowledge_docs: content_excerpt, content_sha256, fetch_status, last_verified_at.
  3. Per fact, runs the evidence check and stores evidence_verified / evidence_offset /
     evidence_checked_at.

--dry-run (THE DEFAULT) writes nothing and prints exactly what would change. A dead source is
signal, not failure: a fact whose page has vanished is precisely a fact to re-check.

Usage:
    python backend/scripts/backfill_fact_evidence.py                  # dry run, all destinations
    python backend/scripts/backfill_fact_evidence.py --dest NO        # one destination
    python backend/scripts/backfill_fact_evidence.py --apply          # write
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.app.services.fact_evidence import (  # noqa: E402
    NO_SOURCE,
    UNVERIFIED,
    VERIFIED,
    check_evidence,
)
from backend.crawler.parsers import immigration_page_parser  # noqa: E402

log = logging.getLogger("backfill_fact_evidence")

# Matches requirement_fact_extractor._MAX_CONTENT_CHARS. The old value was 5_000, which truncated
# the article before the requirement in a long page.
MAX_EXCERPT_CHARS = 24_000
FETCH_TIMEOUT_S = 30.0
USER_AGENT = "ReloPassBot/1.0 (evidence-backfill)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_and_parse(url: str) -> Dict[str, Any]:
    """Fetch one source and return its readable article text. Never raises."""
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_S, follow_redirects=True,
                          headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return {"ok": False, "reason": f"http_{resp.status_code}", "text": ""}
        parsed = (immigration_page_parser.parse(resp.text).get("text") or "").strip()
        if not parsed:
            # A JS-only shell. Recording this is the point — it tells a reviewer why there is
            # no evidence, instead of leaving them to guess.
            return {"ok": False, "reason": "js_shell_or_empty", "text": ""}
        return {"ok": True, "reason": "fetched", "text": parsed[:MAX_EXCERPT_CHARS]}
    except Exception as exc:
        return {"ok": False, "reason": f"error_{type(exc).__name__}", "text": ""}


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="Archive requirement-fact sources and verify quotes")
    p.add_argument("--apply", action="store_true", help="Write. Omit for a dry run.")
    p.add_argument("--dest", help="Limit to one destination_country, e.g. NO")
    p.add_argument("--status", default="pending", help="Fact status to process (default pending)")
    p.add_argument("--limit-urls", type=int, help="Process at most N source URLs (for a smoke run)")
    args = p.parse_args(argv)

    from backend.database import db

    where_dest = "AND e.destination_country = :dest" if args.dest else ""
    params: Dict[str, Any] = {"status": args.status}
    if args.dest:
        params["dest"] = args.dest

    with db.engine.connect() as conn:
        facts = conn.execute(text(f"""
            SELECT f.id, f.source_doc_id, f.source_url, f.evidence_quote,
                   e.destination_country
            FROM requirement_facts f
            JOIN requirement_entities e ON e.id = f.entity_id
            WHERE f.status = :status {where_dest}
        """), params).fetchall()

    by_doc: Dict[str, List[Any]] = {}
    for row in facts:
        by_doc.setdefault(str(row[1]), []).append(row)

    doc_urls: Dict[str, str] = {str(r[1]): r[2] for r in facts}
    doc_ids = list(by_doc)
    if args.limit_urls:
        doc_ids = doc_ids[: args.limit_urls]

    mode = "APPLY" if args.apply else "DRY RUN — nothing will be written"
    print(f"{mode}")
    print(f"{len(facts)} facts across {len(by_doc)} source documents"
          f"{f' (processing {len(doc_ids)})' if args.limit_urls else ''}\n")

    fetch_reasons: Counter = Counter()
    verdicts: Counter = Counter()
    per_dest: Dict[str, Counter] = {}
    dead_sources: List[str] = []

    for i, doc_id in enumerate(doc_ids, 1):
        url = doc_urls[doc_id]
        rows = by_doc[doc_id]
        res = fetch_and_parse(url)
        fetch_reasons[res["reason"]] += 1
        if not res["ok"]:
            dead_sources.append(f"{res['reason']:<22} {url}")

        source_text = res["text"]
        sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest() if source_text else None

        if args.apply and res["ok"]:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    UPDATE knowledge_docs
                       SET content_excerpt = :excerpt,
                           content_sha256 = :sha,
                           fetch_status = 'fetched',
                           fetched_at = :now,
                           last_verified_at = :now
                     WHERE id = :id
                """), {"excerpt": source_text, "sha": sha, "now": _now(), "id": doc_id})

        for fid, _doc, _url, quote, dest in rows:
            check = check_evidence(quote, source_text)
            verdicts[check.status] += 1
            per_dest.setdefault(dest, Counter())[check.status] += 1
            if args.apply:
                with db.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE requirement_facts
                           SET evidence_verified = :ver,
                               evidence_offset = :off,
                               evidence_checked_at = :now
                         WHERE id = :id
                    """), {"ver": check.verified, "off": check.offset,
                           "now": _now(), "id": str(fid)})

        if i % 25 == 0:
            print(f"  … {i}/{len(doc_ids)} sources")

    checked = sum(verdicts.values())
    print(f"\nFETCH ({len(doc_ids)} sources)")
    for reason, n in fetch_reasons.most_common():
        print(f"   {n:>4}  {reason}")

    print(f"\nEVIDENCE ({checked} facts)")
    for status in (VERIFIED, UNVERIFIED, NO_SOURCE):
        n = verdicts.get(status, 0)
        pct = (100 * n / checked) if checked else 0
        print(f"   {n:>4}  {status:<12} {pct:5.1f}%")

    print("\nBY DESTINATION")
    for dest in sorted(per_dest):
        c = per_dest[dest]
        tot = sum(c.values())
        print(f"   {dest}  {c.get(VERIFIED,0):>3} verified / {tot:>3}"
              f"   ({100*c.get(VERIFIED,0)/tot:5.1f}%)")

    if dead_sources:
        print(f"\nSOURCES WITH NO USABLE TEXT ({len(dead_sources)}) — these are the facts whose"
              f"\nevidence a reviewer cannot check; that is the finding, not a failure:")
        for line in dead_sources[:25]:
            print(f"   {line}")
        if len(dead_sources) > 25:
            print(f"   … and {len(dead_sources)-25} more")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to persist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
