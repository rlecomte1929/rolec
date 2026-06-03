#!/usr/bin/env python3
"""
Storage bucket visibility check — SEC-006 / AIQ-478.

Sibling of scripts/check_rls_coverage.py. Connects to the live/staging Supabase
Postgres and asserts that no storage bucket holding case / HR / employee
documents is marked ``public = true``. A public bucket exposes every object by
URL to unauthenticated visitors (the anon key ships in the frontend bundle), so
this is a hard CI gate against regression.

Buckets are matched by name against DOCUMENT_BUCKET_PREFIXES; anything that
looks like a document store must be private. A bucket that is intentionally
public (e.g. ``company-logos`` branding assets) can be added to
PUBLIC_BUCKET_ALLOWLIST with a reason.

Exit codes:
  0 — every document bucket is private (or there are none)
  1 — at least one document bucket is public (CI should fail)
  2 — could not connect to DB or query failed (investigate)

Usage:
  DATABASE_URL=postgresql://... python scripts/storage_bucket_check.py
  DATABASE_URL=postgresql://... python scripts/storage_bucket_check.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Buckets whose names contain any of these substrings are treated as holding
# regulated documents and MUST be private.
DOCUMENT_BUCKET_PREFIXES = (
    "case",
    "hr-",
    "policy",
    "policies",
    "employee",
    "immigration",
    "form-templates",
    "document",
)

# Buckets that are intentionally public. Each entry needs a human-reviewed
# reason. Empty by design — SEC-006 found no public buckets.
PUBLIC_BUCKET_ALLOWLIST: dict[str, str] = {
    # "company-logos": "Branding assets, no PII — intentionally public.",
}

BUCKET_SQL = "SELECT id, name, public FROM storage.buckets ORDER BY name;"


def _looks_like_document_bucket(name: str) -> bool:
    low = (name or "").lower()
    return any(p in low for p in DOCUMENT_BUCKET_PREFIXES)


def query_buckets(db_url: str) -> list[tuple[str, str, bool]]:
    try:
        import psycopg2
    except ImportError:
        print(
            "psycopg2 not installed — `pip install psycopg2-binary` or run from backend venv",
            file=sys.stderr,
        )
        sys.exit(2)

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        print(f"could not connect to DATABASE_URL: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        with conn.cursor() as cur:
            cur.execute(BUCKET_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [(r[0], r[1], bool(r[2])) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail if any document bucket is public.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2

    buckets = query_buckets(db_url)

    offenders = [
        {"id": bid, "name": name}
        for (bid, name, is_public) in buckets
        if is_public
        and _looks_like_document_bucket(name)
        and name not in PUBLIC_BUCKET_ALLOWLIST
    ]

    if args.json:
        print(
            json.dumps(
                {
                    "buckets_total": len(buckets),
                    "public_document_buckets": offenders,
                    "pass": len(offenders) == 0,
                },
                indent=2,
            )
        )
    else:
        print(f"[storage-bucket-check] buckets scanned: {len(buckets)}")
        for bid, name, is_public in buckets:
            vis = "PUBLIC" if is_public else "private"
            print(f"  - {name}: {vis}")
        if offenders:
            print(
                f"\n[storage-bucket-check] FAIL — {len(offenders)} document "
                "bucket(s) are PUBLIC:"
            )
            for o in offenders:
                print(f"  - {o['name']}")
            print(
                "\nFix path:\n"
                "  1. Set public=false via a supabase migration "
                "(UPDATE storage.buckets ...), OR\n"
                "  2. If the bucket is intentionally public and holds no PII, add\n"
                "     it to PUBLIC_BUCKET_ALLOWLIST in this script with a reason.\n"
            )
        else:
            print("\n[storage-bucket-check] PASS — no document bucket is public.")

    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
