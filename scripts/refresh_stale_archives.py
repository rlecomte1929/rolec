#!/usr/bin/env python3
"""[AIQ-2211] Recover approved requirement_facts that are withheld because their
knowledge_docs archive is stale (a cookie-truncated capture or an "Otto bridge
capture" placeholder), NOT because the claim is wrong.

The reader serves `status='approved' AND COALESCE(evidence_verified, TRUE) = TRUE`,
so a fact at evidence_verified=FALSE is withheld from every corridor dossier. AIQ-2160
proved (Andrea, ES->IE) that many of these are recoverable: the quote is verbatim on
the live source, only the archived text is stale. This re-fetches each source and,
self-gating on the canonical normalizer, recovers what it can.

Invariants (safety is by construction, not by care):
  * A fact is flipped TRUE only when its evidence_quote normalized-verifies
    (verify_batch_quotes.norm — the same normalizer the backfill uses) against the
    text it will be stored against. Never on a manual assertion.
  * An archive is refreshed only when NO fact that currently verifies against the old
    text would stop verifying against the fresh text (superset-safe: never break a
    co-citing fact, TRUE or FALSE).
  * The claim (fact_text) and the quote are never invented or edited here. A quote
    that is not on the live source stays FALSE — that is a genuine defect for
    re-source/drop, reported, not written over.
  * DRY-RUN by default; every write is inside one transaction and is reversible.

    python -m scripts.refresh_stale_archives           # dry run (default)
    python -m scripts.refresh_stale_archives --apply    # write

Reads DATABASE_URL (the prod pooler lives in the MAIN checkout .env).
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_verifier():
    spec = importlib.util.spec_from_file_location("vbq", REPO / "scripts/verify_batch_quotes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover FALSE-withheld facts from stale archives.")
    ap.add_argument("--apply", action="store_true", help="Write. Omit for a dry run (default).")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2

    vbq = _load_verifier()
    fetch, to_text, norm = vbq.fetch, vbq.to_text, vbq.norm
    import psycopg2

    # Session mode (5432), not the transaction pooler (6543): the slow per-source curls
    # would otherwise idle the pooled connection out mid-run.
    db_url = db_url.replace(":6543/", ":5432/")

    # ── Phase A: read everything up front, then CLOSE the connection so no DB link is
    #    held open across the slow fetches. ────────────────────────────────────────────
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT k.id, k.source_url
        FROM public.knowledge_docs k
        JOIN public.requirement_facts f ON f.source_doc_id = k.id
        WHERE f.status = 'approved' AND f.evidence_verified IS FALSE
        """
    )
    docs = cur.fetchall()
    facts_by_doc = {}
    old_archive_by_doc = {}
    for doc_id, _url in docs:
        cur.execute(
            "SELECT id, fact_key, evidence_quote, status, evidence_verified "
            "FROM public.requirement_facts WHERE source_doc_id = %s", (doc_id,))
        facts_by_doc[doc_id] = cur.fetchall()
        cur.execute("SELECT text_content FROM public.knowledge_docs WHERE id = %s", (doc_id,))
        old_archive_by_doc[doc_id] = cur.fetchone()[0]
    cur.close()
    conn.close()

    # ── Phase B: fetch every source (no DB connection open). ───────────────────────────
    # verify_batch_quotes.fetch defaults to HTTP/2; canada.ca closes those streams early
    # (curl 92). Force HTTP/1.1, which every one of these statutory sites answers cleanly.
    import subprocess

    def robust_fetch(u: str) -> bytes:
        proc = subprocess.run(
            ["curl", "-sS", "-L", "--http1.1", "--max-time", "60", "-A", vbq.UA, u],
            capture_output=True, timeout=90)
        if proc.returncode != 0 or not proc.stdout:
            raise RuntimeError((proc.stderr.decode(errors="replace")[:70]) or "empty body")
        return proc.stdout

    fresh_by_doc, fetch_fail = {}, []
    for doc_id, url in docs:
        try:
            fresh = to_text(robust_fetch(url))
        except Exception as exc:
            fetch_fail.append((url, str(exc)[:60])); continue
        if len(norm(fresh)) < 200:
            fetch_fail.append((url, f"thin({len(norm(fresh))}) — likely JS-rendered/PDF-gated")); continue
        fresh_by_doc[doc_id] = fresh

    # ── Phase C: apply the recovery in one fast pass. ──────────────────────────────────
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()
    recovered, still_false, refreshed_docs = [], [], 0
    skipped_break = []

    for doc_id, url in docs:
        facts = facts_by_doc[doc_id]
        nold = norm(old_archive_by_doc.get(doc_id) or "")

        # 0. Free recovery: a FALSE fact whose quote already verifies against the CURRENT
        #    archive was simply mis-flagged — flip it, no refresh.
        for fid, fk, q, st, ev in facts:
            if ev is False and norm(q) and norm(q) in nold:
                recovered.append(fk)
                if args.apply:
                    cur.execute(
                        "UPDATE public.requirement_facts SET evidence_verified = TRUE, "
                        "evidence_checked_at = now() WHERE id::text = %s", (str(fid),))

        fresh = fresh_by_doc.get(doc_id)
        if fresh is None:  # fetch failed / thin (already recorded)
            for fid, fk, q, st, ev in facts:
                if ev is False and fk not in recovered:
                    still_false.append((fk, url))
            continue
        nfresh = norm(fresh)

        # 1. Superset-safe: refuse to refresh if it would break a fact that currently verifies.
        would_break = [fk for fid, fk, q, st, ev in facts
                       if norm(q) and norm(q) in nold and norm(q) not in nfresh]
        if would_break:
            skipped_break.append((url, would_break))
            continue

        # 2. Refresh, then flip the FALSE facts that now verify against the fresh text.
        did_flip = False
        for fid, fk, q, st, ev in facts:
            if ev is False and fk in recovered:
                continue
            if ev is False and norm(q) and norm(q) in nfresh:
                recovered.append(fk)
                did_flip = True
                if args.apply:
                    cur.execute(
                        "UPDATE public.requirement_facts SET evidence_verified = TRUE, "
                        "evidence_checked_at = now() WHERE id::text = %s", (str(fid),))
            elif ev is False:
                still_false.append((fk, url))
        if did_flip and args.apply:
            cur.execute("UPDATE public.knowledge_docs SET text_content = %s WHERE id = %s",
                        (fresh, doc_id))
        if did_flip:
            refreshed_docs += 1

    if args.apply:
        conn.commit()
    else:
        conn.rollback()
    cur.close()
    conn.close()

    mode = "APPLIED" if args.apply else "DRY RUN — nothing written"
    print(f"refresh_stale_archives — {mode}")
    print(f"  docs with FALSE facts : {len(docs)}")
    print(f"  RECOVERED -> TRUE     : {len(recovered)}  (archives refreshed: {refreshed_docs})")
    print(f"  still FALSE (defect)  : {len(still_false)}")
    print(f"  fetch failed/JS/PDF   : {len(fetch_fail)}")
    print(f"  skipped (would break) : {len(skipped_break)}")
    if fetch_fail:
        print("\n  Sources needing browser/PDF or a reachability check (AIQ-2159):")
        for u, why in fetch_fail[:40]:
            print(f"    - {why:42} {u}")
    if skipped_break:
        print("\n  Refresh skipped to protect a co-citing fact:")
        for u, fks in skipped_break:
            print(f"    - {u} would break {fks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
