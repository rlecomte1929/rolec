#!/usr/bin/env python3
"""Mint a staged test-drive fixture and report what its recommendations page will render.

WHY THIS EXISTS
---------------
AIQ-1903 (seed the destination catalog as the default vendor proposal) has been reverted
TWICE — #1907 and #1991 — both times because ``[R4X-B]`` failed with:

    Fixture qa-r4x-decisions-... (FR_NO @ shortlist_ready) rendered 1 provider cards;
    this assertion needs at least 2.

Both attempts were preceded by careful SQL measurement of the *catalog*, and both times
that evidence was the wrong kind. The catalog says what COULD be offered. What R4X-B
counts is what a freshly PROVISIONED fixture actually renders, which is a different
number arrived at three steps later:

    provision-staged  ->  seeds company_vendor_selections for the new company
                      ->  computes recommendations ONCE and persists them in
                          services_state.state_json.recommendations
                      ->  ALSO shortlists some of them into state_json.shortlist

The page shows one card per stored recommendation; a card already in the shortlist reads
"In package", not "Add to package". So R4X-B's count is:

    available = (cards in state_json.recommendations) - (cards in state_json.shortlist)

Measured on FR_NO / shortlist_ready, 2026-08-22: 8 cards, 6 shortlisted, **2 available** —
exactly the assertion's floor. The margin is zero, so ANY change that removes one
recommendation from Norway breaks the test.

Run this BEFORE proposing a change to vendor seeding. `--explain` prints the two
available cards by name, which is the number that actually matters.

Usage:
    python scripts/probe_vendor_fixture.py --corridor FR_NO --stage shortlist_ready
    python scripts/probe_vendor_fixture.py --case-id <uuid>        # re-read an existing one

Needs API_BASE (default https://api.relopass.com). Reads the DB only if DATABASE_URL is
set; without it, it reports what the API alone can show and says so.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("API_BASE", "https://api.relopass.com")


def _post(path: str, body: dict, token: str | None = None, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def mint(corridor: str, stage: str) -> dict:
    tag = str(int(time.time()))[-6:]
    body = {
        "first_name": f"Probe{tag}",
        # The endpoint gates on a qa-* campaign label; these fixtures are purged by the
        # e2e-purge workflow, so minting one is routine and self-cleaning.
        "campaign": f"qa-probe-{tag}",
        "corridor_id": corridor,
        "stage": stage,
    }
    print(f"minting {corridor} @ {stage} … (this drives the real pipeline; ~40s)")
    return _post("/api/test-drive/provision-staged", body)


_STATE_SQL = """
SELECT state_json::jsonb AS j
FROM public.services_state WHERE case_id::text = %s
"""


def read_state(case_id: str) -> dict | None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError:
        print("  (psycopg2 not installed — skipping the DB read)", file=sys.stderr)
        return None
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(_STATE_SQL, (case_id,))
        row = cur.fetchone()
    return row[0] if row else None


def report(state: dict, explain: bool) -> int:
    recs = state.get("recommendations") or {}
    shortlisted = set()
    for pair in state.get("shortlist") or []:
        if isinstance(pair, list) and len(pair) == 2:
            shortlisted.update(pair[1] or [])

    total = available = 0
    rows = []
    for category, block in sorted(recs.items()):
        cards = (block or {}).get("recommendations") or []
        for c in cards:
            total += 1
            in_pkg = c.get("item_id") in shortlisted
            if not in_pkg:
                available += 1
            rows.append((category, c.get("name"), c.get("item_id"), in_pkg))

    print(f"\n  cards stored      : {total}")
    print(f"  already in package: {total - available}")
    print(f"  AVAILABLE (what [R4X-B] counts): {available}   floor = 2")
    if explain:
        print("\n  the available cards — this is the margin that must survive a change:")
        for cat, name, item_id, in_pkg in rows:
            if not in_pkg:
                print(f"    {cat:10s} {name}  [{item_id}]")
    if available < 2:
        print("\n  ✗ BELOW THE FLOOR — [R4X-B] would fail on this fixture.")
        return 1
    if available == 2:
        print("\n  ⚠ EXACTLY at the floor: removing any one recommendation breaks [R4X-B].")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corridor", default="FR_NO")
    ap.add_argument("--stage", default="shortlist_ready")
    ap.add_argument("--case-id", help="skip minting; re-read an existing fixture")
    ap.add_argument("--explain", action="store_true", help="name the available cards")
    args = ap.parse_args(argv)

    case_id = args.case_id
    if not case_id:
        try:
            f = mint(args.corridor, args.stage)
        except urllib.error.HTTPError as exc:
            print(f"provision-staged failed: {exc.code} {exc.read()[:300]!r}", file=sys.stderr)
            return 2
        case_id = f.get("case_id")
        print(f"  case_id     : {case_id}")
        print(f"  assignment  : {f.get('assignment_id')}")
        print(f"  employee    : {(f.get('employee') or {}).get('email')}")
        print(f"  shortlist   : {f.get('shortlist')}")

    state = read_state(case_id)
    if state is None:
        print("\nDATABASE_URL not set, so the decisive number is unavailable.")
        print("The recommendations live in services_state.state_json, NOT behind an API:")
        print("  POST /api/recommendations/batch returns 'No selected services with")
        print("  recommendation support' for a staged fixture, because state_json.answers")
        print("  is empty. Do not read that as 'no providers' — it is the wrong door.")
        return 0
    return report(state, args.explain)


if __name__ == "__main__":
    raise SystemExit(main())
