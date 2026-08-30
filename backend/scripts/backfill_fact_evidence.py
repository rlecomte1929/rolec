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

RE-CHECKING THE SERVED COHORT — use --only-unchecked. `--status approved` selects facts the
product is serving right now, and this script rewrites evidence_verified for EVERY fact it
selects. On a re-check that means an already-verified fact can flip to FALSE (page reworded,
publisher started refusing us, parser output shifted) and drop straight out of
`list_approved_requirement_facts`, which filters `COALESCE(evidence_verified, TRUE) = TRUE`.
A remediation that removes a working citation is worse than the gap it set out to close, so
narrow the run to the facts that have never been checked.

Note NULL is not a synonym for "never checked": check_evidence returns None for TRANSLATED
(the quote is a translation of the source, so a verbatim match is impossible) as well as for
NO_SOURCE. Those stay NULL after a run and keep being served — only evidence_checked_at moves,
which is what distinguishes "never ran" from "ran, did not apply".

Usage:
    python backend/scripts/backfill_fact_evidence.py                  # dry run, all destinations
    python backend/scripts/backfill_fact_evidence.py --dest NO        # one destination
    python backend/scripts/backfill_fact_evidence.py --apply          # write
    python backend/scripts/backfill_fact_evidence.py \\
        --dest IE --status approved --only-unchecked                  # re-check the served gap
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
import urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

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
# What we STORE as knowledge_docs.content_excerpt — bounded, because a row is queried often.
MAX_EXCERPT_CHARS = 24_000
# What we FETCH and MATCH a quote against. Much larger: statutory sources (eur-lex Directive
# 2004/38, Reg 883/2004) run to hundreds of KB and the cited article can sit well past 24k.
# Truncating the MATCH text at 24k false-flagged five sound EU-law quotes as `unverified`
# (measured 2026-08-30). So we match on the full page and store only the bounded head.
MAX_MATCH_CHARS = 2_000_000
FETCH_TIMEOUT_S = 30.0

# Measured 2026-08-20 across the sources behind the approved facts. There is NO single
# User-Agent that works everywhere, which is why this is a chain rather than a constant:
#
#   citizensinformation.ie   bot UA -> 403          browser UA -> 200
#   immi.homeaffairs.gov.au  bot UA -> 403          browser UA -> 200
#   canada.ca                bot UA -> 200          browser UA -> connection reset in 0.15s
#   travel.state.gov         403 to everything (Cloudflare)
#
# Order is deliberate and is the whole ethical point: we identify as ourselves FIRST, and only
# present as a browser to a publisher that has actually refused our own name. A first pass that
# led with the browser token dropped Canada from 13.6% evidenced to 0%.
UA_HONEST = "ReloPassBot/1.0 (evidence-backfill)"
UA_BROWSER = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
#: Tried in order until one returns a usable page. `None` sends no User-Agent header at all,
#: which is the only thing some anti-bot front ends accept.
USER_AGENTS: Tuple[Optional[str], ...] = (UA_HONEST, UA_BROWSER, None)

#: Kept for callers and tests that ask "what do we identify as by default".
USER_AGENT = UA_HONEST

#: One request per second per host.
HOST_DELAY_S = 1.0


class HostRateLimiter:
    """Space requests to the same host. Politeness is the other half of a UA fallback chain."""

    def __init__(self, delay_s: float = HOST_DELAY_S) -> None:
        self.delay_s = delay_s
        self._last: Dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower()
        prev = self._last.get(host)
        now = time.monotonic()
        if prev is not None:
            remaining = self.delay_s - (now - prev)
            if remaining > 0:
                time.sleep(remaining)
        self._last[host] = time.monotonic()


class RobotsPolicy:
    """robots.txt per host, fetched through the same UA chain as the pages.

    `urllib.robotparser.RobotFileParser.read()` fetches with urllib's own `Python-urllib/3.x`
    User-Agent and treats a 403 on robots.txt as *disallow everything*. On 2026-08-20 that
    silently blocked every citizensinformation.ie, travel.state.gov and france-visas.gouv.fr
    URL — the robots check defeated the very UA fallback it was paired with, and Ireland went
    from 6.8% evidenced to 0%. So fetch robots ourselves and only then parse it.

    A 4xx is treated as "no policy published" and allows, matching the conventional reading
    (and citizensinformation.ie really does 404 its robots.txt). A 5xx disallows: the server
    has a policy and cannot currently tell us what it is.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def _load(self, origin: str) -> Optional[urllib.robotparser.RobotFileParser]:
        body, status = None, None
        for ua in USER_AGENTS:
            headers = {"User-Agent": ua} if ua else {}
            try:
                with httpx.Client(timeout=FETCH_TIMEOUT_S, follow_redirects=True,
                                  headers=headers) as client:
                    resp = client.get(origin + "/robots.txt")
                status = resp.status_code
                if resp.status_code == 200:
                    body = resp.text
                    break
            except Exception:
                continue
        if body is None:
            if status is not None and 500 <= status < 600:
                rp = urllib.robotparser.RobotFileParser()
                rp.disallow_all = True
                return rp
            return None  # no readable policy -> allow
        # A soft 404 serves an HTML page as robots.txt. Parsing that yields no directives, but
        # be explicit rather than relying on the parser shrugging.
        if "user-agent" not in body.lower():
            return None
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(body.splitlines())
        return rp

    def allowed(self, url: str) -> bool:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            try:
                self._cache[origin] = self._load(origin)
            except Exception:
                self._cache[origin] = None
        rp = self._cache[origin]
        if rp is None:
            return True
        try:
            return rp.can_fetch(UA_HONEST, url)
        except Exception:
            return True


def fetch_status_for(res: Dict[str, Any]) -> str:
    """`knowledge_docs.fetch_status` for one fetch outcome.

    `not_fetched` means nobody ever tried, so a failure must never be written as that — on
    2026-08-20 exactly that conflation left 140 docs claiming `not_fetched` while holding a real
    archived excerpt. `fetch_failed` is the existing third value (official_ingest_service.py:168)
    and is what a refusal or an unparseable shell deserves. A robots skip really is "not
    fetched": we chose not to ask.
    """
    if res.get("ok"):
        return "fetched"
    if res.get("reason") == "robots_disallowed":
        return "not_fetched"
    return "fetch_failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_and_parse(
    url: str,
    robots: Optional[Any] = None,
    limiter: Optional[HostRateLimiter] = None,
) -> Dict[str, Any]:
    """Fetch one source and return its readable article text. Never raises.

    Walks `USER_AGENTS` in order, stopping at the first identity that yields a usable page, and
    reports which one worked. `blocked` distinguishes "every identity was refused" from "there
    is nothing there": the evidence checker only ever sees empty text, so if that difference is
    not preserved here, a live page reads as a missing source and a fact gets a verdict it never
    earned.
    """
    if robots is not None and not robots.allowed(url):
        log.warning("robots.txt disallows %s — skipping", url)
        return {"ok": False, "reason": "robots_disallowed", "text": "", "blocked": False,
                "ua": None}

    last: Dict[str, Any] = {"ok": False, "reason": "no_attempt", "text": "", "blocked": False,
                            "ua": None}
    for ua in USER_AGENTS:
        if limiter is not None:
            limiter.wait(url)
        headers = {"User-Agent": ua} if ua else {}
        try:
            with httpx.Client(timeout=FETCH_TIMEOUT_S, follow_redirects=True,
                              headers=headers) as client:
                resp = client.get(url)
        except Exception as exc:
            # A connection reset is how some anti-bot front ends refuse a UA they dislike —
            # canada.ca resets the browser token in 0.15s but serves the page with no UA header.
            last = {"ok": False, "reason": f"error_{type(exc).__name__}", "text": "",
                    "blocked": False, "ua": ua}
            continue

        if resp.status_code != 200:
            blocked = resp.status_code in (401, 403, 429)
            last = {"ok": False, "reason": f"http_{resp.status_code}", "text": "",
                    "blocked": blocked, "ua": ua}
            if not blocked:
                # Not a refusal — a 404 or 5xx will say the same thing to every identity.
                return last
            continue

        parsed = (immigration_page_parser.parse(resp.text).get("text") or "").strip()
        if not parsed:
            # A JS-only shell. Recording this is the point — it tells a reviewer why there is
            # no evidence, instead of leaving them to guess. Another UA will not render it.
            return {"ok": False, "reason": "js_shell_or_empty", "text": "", "blocked": False,
                    "ua": ua}
        return {"ok": True, "reason": "fetched", "text": parsed[:MAX_MATCH_CHARS],
                "blocked": False, "ua": ua}

    # Every identity refused. That is a block, whatever the last status line said.
    last["blocked"] = True
    return last


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description="Archive requirement-fact sources and verify quotes")
    p.add_argument("--apply", action="store_true", help="Write. Omit for a dry run.")
    p.add_argument("--dest", help="Limit to one destination_country, e.g. NO")
    p.add_argument("--status", default="pending",
                   help="Fact status to process. DEFAULTS TO 'pending' — pass --status approved "
                        "to touch the served cohort, which is a different set of facts.")
    p.add_argument("--limit-urls", type=int, help="Process at most N source URLs (for a smoke run)")
    p.add_argument("--only-unchecked", action="store_true",
                   help="Only facts with evidence_verified IS NULL. Use this on the SERVED cohort "
                        "(--status approved): without it, a re-check rewrites the verdict of every "
                        "fact in scope, so an already-verified fact can flip to FALSE and silently "
                        "leave the served surface.")
    args = p.parse_args(argv)

    from backend.database import db

    where_dest = "AND e.destination_country = :dest" if args.dest else ""
    # Filter on the FACT, not the document. One source document routinely carries both an
    # already-verified fact and an unchecked one; scoping by document would drag the verified
    # fact back through the check and put its verdict at risk, which is the whole thing this
    # flag exists to prevent.
    where_unchecked = "AND f.evidence_verified IS NULL" if args.only_unchecked else ""
    params: Dict[str, Any] = {"status": args.status}
    if args.dest:
        params["dest"] = args.dest

    with db.engine.connect() as conn:
        facts = conn.execute(text(f"""
            SELECT f.id, f.source_doc_id, f.source_url, f.evidence_quote,
                   e.destination_country
            FROM requirement_facts f
            JOIN requirement_entities e ON e.id = f.entity_id
            WHERE f.status = :status {where_dest} {where_unchecked}
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
    # Say which cohort this is. The default is 'pending', and a run aimed at the served surface
    # needs --status approved — silently processing the wrong set is how a remediation reports
    # success while the facts it was meant to fix stay untouched.
    print(f"status={args.status!r}" + (f"  dest={args.dest}" if args.dest else "")
          + ("  only-unchecked=True" if args.only_unchecked else ""))
    print(f"{len(facts)} facts across {len(by_doc)} source documents"
          f"{f' (processing {len(doc_ids)})' if args.limit_urls else ''}\n")

    fetch_reasons: Counter = Counter()
    verdicts: Counter = Counter()
    per_dest: Dict[str, Counter] = {}
    dead_sources: List[str] = []
    blocked_sources: List[str] = []

    robots = RobotsPolicy()
    limiter = HostRateLimiter()

    for i, doc_id in enumerate(doc_ids, 1):
        url = doc_urls[doc_id]
        rows = by_doc[doc_id]
        res = fetch_and_parse(url, robots=robots, limiter=limiter)
        fetch_reasons[res["reason"]] += 1
        if not res["ok"]:
            (blocked_sources if res.get("blocked") else dead_sources).append(
                f"{res['reason']:<22} {url}")

        source_text = res["text"]
        # Match against the full fetched text (below); archive only a bounded head, and
        # fingerprint what we actually store so change-detection stays consistent.
        stored_excerpt = source_text[:MAX_EXCERPT_CHARS]
        sha = hashlib.sha256(stored_excerpt.encode("utf-8")).hexdigest() if stored_excerpt else None

        if args.apply:
            # Record the failure too. Writing fetch_status only on success let the column drift
            # from reality — a doc whose URL now refuses us kept whatever it last claimed.
            if res["ok"]:
                with db.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE knowledge_docs
                           SET content_excerpt = :excerpt,
                               content_sha256 = :sha,
                               fetch_status = 'fetched',
                               fetched_at = :now,
                               last_verified_at = :now
                         WHERE id = :id
                    """), {"excerpt": stored_excerpt, "sha": sha, "now": _now(), "id": doc_id})
            else:
                # Leave content_excerpt alone: a previously archived excerpt is still the best
                # evidence we hold, and a refusal today is no reason to discard it.
                with db.engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE knowledge_docs
                           SET fetch_status = :status, fetched_at = :now
                         WHERE id = :id
                    """), {"status": fetch_status_for(res), "now": _now(), "id": doc_id})

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

    if blocked_sources:
        print(f"\nPUBLISHER REFUSED US ({len(blocked_sources)}) — 401/403/429. This says NOTHING"
              f"\nabout whether the quote is on the page; do not read these as missing sources:")
        for line in blocked_sources[:25]:
            print(f"   {line}")
        if len(blocked_sources) > 25:
            print(f"   … and {len(blocked_sources)-25} more")

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
