#!/usr/bin/env python3
"""[AIQ-2195] Promote multi-country same-name catalog masters to country-agnostic.

ADR-002 Option B: one ``service_catalog_items`` master per (category, name), with
``country = NULL`` when the linked supplier has more than one distinct approved
capability country in that category. Per-country coverage stays on
``supplier_service_capabilities``.

This is a data-only write — no DDL. It matches the ADR backfill verbatim and is
safe to re-run: already-NULL rows and non-``registry_promoted`` rows are skipped,
and no other column is touched.

Do NOT apply this against production until the reader change in
``employee_recommendations_filter._serves_destination`` is deployed. Nulling
country without that gate would over-surface these masters for destinations they
do not cover.

Usage (from repo root):
    python backend/scripts/backfill_country_agnostic_catalog_masters.py
    python backend/scripts/backfill_country_agnostic_catalog_masters.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from sqlalchemy import text

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.database import db  # noqa: E402

# ADR-002 remediation plan step 3. Correlated on category so a movers master is
# not nulled because the same supplier also has an approved tax capability.
BACKFILL_SQL = """
UPDATE public.service_catalog_items sci
   SET country = NULL, updated_at = now()
 WHERE sci.source = 'registry_promoted'
   AND sci.country IS NOT NULL
   AND sci.supplier_id IN (
     SELECT ssc.supplier_id
     FROM supplier_service_capabilities ssc
     WHERE ssc.platform_vetting_status = 'approved'
       AND ssc.country_code IS NOT NULL AND btrim(ssc.country_code) <> ''
       AND lower(btrim(ssc.service_category)) = lower(btrim(sci.category))
     GROUP BY ssc.supplier_id
     HAVING count(DISTINCT ssc.country_code) > 1
   )
"""

PREVIEW_SQL = """
SELECT sci.id, sci.name, sci.category, sci.country, sci.supplier_id, sci.source
  FROM public.service_catalog_items sci
 WHERE sci.source = 'registry_promoted'
   AND sci.country IS NOT NULL
   AND sci.supplier_id IN (
     SELECT ssc.supplier_id
     FROM supplier_service_capabilities ssc
     WHERE ssc.platform_vetting_status = 'approved'
       AND ssc.country_code IS NOT NULL AND btrim(ssc.country_code) <> ''
       AND lower(btrim(ssc.service_category)) = lower(btrim(sci.category))
     GROUP BY ssc.supplier_id
     HAVING count(DISTINCT ssc.country_code) > 1
   )
 ORDER BY sci.name
"""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write country=NULL. Default is a dry-run preview.",
    )
    args = parser.parse_args(argv)

    with db.engine.begin() as conn:
        rows = conn.execute(text(PREVIEW_SQL)).mappings().all()
        print(f"candidates: {len(rows)}")
        for r in rows:
            print(
                f"  {r['name']!s}  category={r['category']}  "
                f"country={r['country']}  id={r['id']}"
            )
        if not args.apply:
            print("dry-run; pass --apply to write")
            return 0
        result = conn.execute(text(BACKFILL_SQL))
        print(f"updated: {result.rowcount}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
