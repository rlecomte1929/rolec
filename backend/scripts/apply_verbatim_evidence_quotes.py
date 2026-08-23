#!/usr/bin/env python3
"""Apply researched verbatim evidence quotes — but re-verify each against its live source first.

WHY THE RE-VERIFICATION IS THE POINT, not a formality.

`fact_evidence.check_evidence` proves a quote by finding it as a literal substring of the
archived page. So a quote is only worth storing if it IS one. The 11 Irish employment-permit
facts this batch targets each had a PARAPHRASE in that field — someone's summary, not the
page's sentence — so none could ever verify, and all 11 were served unverified.

Research came back with the real sentences. Six of twelve arrived CORRUPTED: every space
before a digit had been stripped somewhere in the relay, so "at least 12 weeks" became
"at least12 weeks", "up to 24 months" became "up to24 months". Those strings appear on no
page. Storing them would have left all 11 still failing, and the obvious next conclusion —
"the sources must be wrong" — would have been wrong, about sources that were fine.

Nothing about that was visible in the batch. It looked like clean JSON. The only thing that
caught it was fetching the page and checking, which is exactly what this script does before
every write:

    fetch source_url  ->  strip tags  ->  collapse whitespace  ->  quote in text?
                                            no  -> REFUSE that row, print why

A quote that cannot be found is not written. Ever. There is no --force.

FACT TEXT IS A SEPARATE, GATED THING. Fixing a quote is mechanical: the claim stands, the
evidence was badly transcribed. Fixing `fact_text` changes WHAT WE ASSERT to a person making
an immigration decision, and belongs to a human. Records may carry a `fact_text_correction`
block; it is written only under --apply-text-corrections, and the diff is printed in full
first. gep_7 is the live example: the fee table lists TWO renewal tiers and we publish three.

    python backend/scripts/apply_verbatim_evidence_quotes.py                        # dry run
    python backend/scripts/apply_verbatim_evidence_quotes.py --apply
    python backend/scripts/apply_verbatim_evidence_quotes.py --apply --apply-text-corrections
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import httpx  # noqa: E402
from sqlalchemy import text as sql  # noqa: E402

log = logging.getLogger("apply_verbatim_evidence_quotes")

DEFAULT_BATCH = os.path.join(
    _REPO_ROOT, "docs", "imports", "ie-employment-permit-quotes-2026-08-23.ndjson"
)
# A real browser UA: enterprise.gov.ie serves a challenge page to the default httpx agent,
# and a challenge page contains none of the quotes — which would read as "not found" and
# refuse every row for the wrong reason.
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"

_UPDATE_QUOTE = sql(
    "UPDATE requirement_facts SET evidence_quote = :q, evidence_verified = TRUE, "
    "evidence_checked_at = NOW() WHERE id::text = :id"
)
_UPDATE_TEXT = sql("UPDATE requirement_facts SET fact_text = :t WHERE id::text = :id")
_SELECT = sql("SELECT fact_key, fact_text, evidence_quote FROM requirement_facts WHERE id::text = :id")


def page_text(url: str, *, attempts: int = 3) -> Optional[str]:
    """Visible text of a page, whitespace-collapsed. None if it cannot be fetched.

    Retries: Irish government sites intermittently serve a placeholder, and we have recorded
    a live source as dead once already on one bad minute. A transient blip must not become a
    'not found' verdict on a page that is fine.
    """
    for attempt in range(attempts):
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": _UA})
            if r.status_code == 200 and len(r.text) > 2000:
                t = re.sub(r"<script.*?</script>|<style.*?</style>", "", r.text, flags=re.S | re.I)
                t = html.unescape(re.sub(r"<[^>]+>", " ", t))
                return re.sub(r"\s+", " ", t).strip()
            log.warning("  fetch %s -> HTTP %s len=%d (attempt %d)", url, r.status_code, len(r.text), attempt + 1)
        except Exception as exc:  # noqa: BLE001
            log.warning("  fetch %s failed: %s (attempt %d)", url, exc, attempt + 1)
        if attempt + 1 < attempts:
            time.sleep(5)
    return None


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def load_batch(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Apply verbatim evidence quotes, verified live")
    p.add_argument("--batch", default=DEFAULT_BATCH)
    p.add_argument("--apply", action="store_true", help="Write the quotes. Omit for a dry run.")
    p.add_argument(
        "--apply-text-corrections", action="store_true",
        help="ALSO rewrite fact_text where the batch carries a correction. Changes what we "
             "assert to a user — read the printed diff first.",
    )
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from backend.database import db  # noqa: E402

    rows = load_batch(args.batch)
    log.info("batch: %d record(s) from %s\n", len(rows), os.path.basename(args.batch))

    pages: Dict[str, Optional[str]] = {}
    ok: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    refused: List[Tuple[str, str]] = []
    text_changes: List[Dict[str, Any]] = []

    for rec in rows:
        key, fid, url = rec["fact_key"], rec["fact_id"], rec["source_url"]
        quote = normalise(rec["evidence_quote"])

        with db.engine.connect() as conn:
            current = conn.execute(_SELECT, {"id": fid}).mappings().first()
        if not current:
            refused.append((key, "no such fact_id in requirement_facts")); continue

        if url not in pages:
            pages[url] = page_text(url)
        body = pages[url]
        if body is None:
            refused.append((key, f"source unreachable after retries: {url}")); continue

        if quote not in body:
            # The corruption case. Say so precisely rather than "not found", because the
            # difference between "the page changed" and "the string was mangled in transit"
            # decides what someone does next.
            squashed_hit = re.sub(r"\s", "", quote) in re.sub(r"\s", "", body)
            why = ("present on the page but WHITESPACE DIFFERS — the quote was corrupted in "
                   "transit, re-extract it from the page"
                   if squashed_hit else "not on the page at all")
            refused.append((key, why)); continue

        ok.append((rec, dict(current)))
        if rec.get("fact_text_correction"):
            text_changes.append(rec)

    log.info("VERIFIED AGAINST THE LIVE PAGE — will write:")
    for rec, cur in ok:
        log.info("  %-9s %s", rec["fact_key"], normalise(rec["evidence_quote"])[:88])
    if refused:
        log.info("\nREFUSED — not written:")
        for key, why in refused:
            log.info("  %-9s %s", key, why)

    if text_changes:
        log.info("\nFACT TEXT CORRECTIONS (need --apply-text-corrections):")
        for rec in text_changes:
            c = rec["fact_text_correction"]
            log.info("  %s\n    why : %s\n    now : %s\n    new : %s",
                     rec["fact_key"], c["why"], c["current"], c["corrected"])

    log.info("\nverified=%d refused=%d text_corrections=%d", len(ok), len(refused), len(text_changes))
    if not args.apply:
        log.info("DRY RUN — nothing written. Re-run with --apply.")
        return 0

    wrote = 0
    for rec, _cur in ok:
        with db.engine.begin() as conn:
            conn.execute(_UPDATE_QUOTE, {"q": normalise(rec["evidence_quote"]), "id": rec["fact_id"]})
        wrote += 1
    log.info("APPLIED — %d quote(s) written, evidence_verified=TRUE.", wrote)

    if args.apply_text_corrections:
        for rec in text_changes:
            with db.engine.begin() as conn:
                conn.execute(_UPDATE_TEXT,
                             {"t": rec["fact_text_correction"]["corrected"], "id": rec["fact_id"]})
        log.info("APPLIED — %d fact_text correction(s).", len(text_changes))
    elif text_changes:
        log.info("fact_text left UNCHANGED (%d pending). Pass --apply-text-corrections to write.",
                 len(text_changes))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
