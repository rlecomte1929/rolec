#!/usr/bin/env python3
"""
[Stage 9 · Phase 1] Populate `suppliers.based_in_country`, recording which tier of evidence
supported each value.

Run from the repo root:

    # preview — gathers evidence, decides everything, writes nothing
    python scripts/backfill_supplier_base_country.py

    # write
    python scripts/backfill_supplier_base_country.py --apply

Dry run is the DEFAULT and takes the same code path as a real run.

REQUIRES `20261101030000_suppliers_based_in_country.sql` TO BE APPLIED. The script checks and
exits with a clear message rather than a psycopg error if the column is missing — the four
Phase 1 migrations are applied out-of-band by an operator, not by merging.

WHAT IT WRITES
--------------
    based_in_country          the ISO2
    entity_verified_source    which register said so, or `catalog_listing` for the proxy tier
    entity_verified_at        when we established it
    legal_registration_number a SIREN or Brønnøysund org nr, where one is available

All four were 0 of 116 populated before this ran, so nothing is overwritten. Re-running is
idempotent: an unchanged decision produces an unchanged row.

A catalog listing is NOT a register. It is recorded as `catalog_listing` precisely so a later
consumer can require registry-grade evidence, and so nobody mistakes a directory's placement
for a legal fact.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.imports.suppliers.base_country import (  # noqa: E402
    SupplierEvidence,
    resolve,
    summarise,
)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=25) as resp:  # noqa: S310 — fixed https registry
        return resp.read().decode("utf-8", errors="replace")


def _column_exists(conn) -> bool:
    from sqlalchemy import text

    row = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='suppliers' "
        "  AND column_name='based_in_country' LIMIT 1"
    )).fetchone()
    return bool(row)


def _load_evidence(conn) -> List[SupplierEvidence]:
    from sqlalchemy import text

    accreds: Dict[str, list] = {}
    numbers: Dict[str, list] = {}
    for r in conn.execute(text(
        "SELECT supplier_id::text AS sid, body, evidence_url, membership_number "
        "FROM supplier_accreditations"
    )).mappings():
        accreds.setdefault(r["sid"], []).append((r["body"], r["evidence_url"]))
        if r["membership_number"]:
            numbers.setdefault(r["sid"], []).append(r["membership_number"])

    catalog: Dict[str, str] = {}
    for r in conn.execute(text(
        "SELECT supplier_id::text AS sid, max(country) AS country "
        "FROM service_catalog_items WHERE supplier_id IS NOT NULL AND country IS NOT NULL "
        "GROUP BY supplier_id"
    )).mappings():
        catalog[r["sid"]] = r["country"]

    out: List[SupplierEvidence] = []
    for r in conn.execute(text(
        "SELECT id::text AS sid, name FROM suppliers ORDER BY name"
    )).mappings():
        sid = r["sid"]
        out.append(SupplierEvidence(
            supplier_id=sid,
            name=r["name"] or sid,
            accreditations=tuple(accreds.get(sid, ())),
            catalog_country=catalog.get(sid),
            membership_numbers=tuple(numbers.get(sid, ())),
        ))
    return out


def _attach_fidi_pages(evidence: List[SupplierEvidence]) -> List[SupplierEvidence]:
    """Fetch the FIDI affiliate page for suppliers that hold a FIDI accreditation.

    A failed fetch leaves `fidi_page_text` None, and `resolve()` then falls through to a weaker
    source rather than guessing — an unreachable page is not evidence.
    """
    out: List[SupplierEvidence] = []
    for ev in evidence:
        url = next(
            (u for (body, u) in ev.accreditations
             if body and "fidi" in body.lower() and u),
            None,
        )
        text_body = None
        if url:
            try:
                text_body = _fetch(url)
            except Exception as exc:  # noqa: BLE001 — any failure means "no evidence"
                print(f"  ⚠ {ev.name}: FIDI page unreachable ({type(exc).__name__})")
        out.append(SupplierEvidence(
            supplier_id=ev.supplier_id, name=ev.name, accreditations=ev.accreditations,
            catalog_country=ev.catalog_country, fidi_page_text=text_body,
            membership_numbers=ev.membership_numbers,
        ))
    return out


#: Never DOWNGRADE evidence. A re-run with --no-fetch cannot reach the FIDI pages, so a
#: supplier that resolved `registry:fidi` would fall through to its catalog listing — and
#: without this guard the second run would quietly replace a register-backed country with a
#: directory's guess. Nothing here can weaken a row: a registry source is only ever replaced
#: by another registry source.
_UPDATE = """
UPDATE public.suppliers
   SET based_in_country         = :country,
       entity_verified_source   = :source,
       entity_verified_at       = :at,
       legal_registration_number = COALESCE(:legal, legal_registration_number),
       updated_at               = now()
 WHERE id = :sid
   AND NOT (
         coalesce(entity_verified_source, '') LIKE 'registry:%'
     AND :source NOT LIKE 'registry:%'
   )
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip the FIDI page fetches (faster; those suppliers fall through "
                         "to a weaker source or to NULL)")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("✖ DATABASE_URL is not set")
        return 2

    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, future=True)

    with engine.connect() as conn:
        if not _column_exists(conn):
            print("✖ suppliers.based_in_country does not exist yet.")
            print("  Apply 20261101030000_suppliers_based_in_country.sql first — the Phase 1")
            print("  migrations are applied out-of-band by an operator, not by merging.")
            return 2
        evidence = _load_evidence(conn)

    print(f"read {len(evidence)} supplier(s)\n")
    if not args.no_fetch:
        evidence = _attach_fidi_pages(evidence)

    resolutions = [resolve(ev) for ev in evidence]
    print(summarise(resolutions, dry_run=not args.apply))

    if args.apply:
        now = datetime.now(timezone.utc)
        written = 0
        with engine.begin() as conn:
            for r in resolutions:
                if not r.writes:
                    continue
                conn.execute(text(_UPDATE), {
                    "country": r.country, "source": r.source, "at": now,
                    "legal": r.legal_registration_number, "sid": r.supplier_id,
                })
                written += 1
        print(f"\nwritten: {written} supplier(s)")
    else:
        print("\n  (preview — pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
