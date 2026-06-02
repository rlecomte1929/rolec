"""Refresh the supplier_cluster_cache for cluster-relative tiering (Parker-C).

Usage:
    python -m backend.scripts.refresh_supplier_clusters
    python -m backend.scripts.refresh_supplier_clusters --category banks --country BE

For each (service_category, country) cell it loads suppliers, scores them with the
category plugin, clusters them (KMeans, K by silhouette), computes per-cluster
percentile thresholds, and writes ONE new supplier_cluster_cache row. Cells with
fewer than tiering.MIN_CLUSTER_CELL clustered suppliers are skipped (the engine
falls back to absolute thresholds for those).

Suggested schedule (do NOT auto-create): daily off-peak cron, e.g.
    0 3 * * *  python -m backend.scripts.refresh_supplier_clusters
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import List, Optional

from sqlalchemy import text

from backend.app.db import SessionLocal
from backend.app.recommendations import tiering
from backend.app.recommendations.registry import list_categories
from backend.app.services.supplier_registry import list_supplier_countries

_INSERT = text(
    """
    insert into public.supplier_cluster_cache
        (service_category, country_iso2, cluster_id, cluster_size, k_selected,
         silhouette, thresholds_json, supplier_ids_json, computed_at)
    values
        (:service_category, :country_iso2, :cluster_id, :cluster_size, :k_selected,
         :silhouette, cast(:thresholds_json as jsonb), cast(:supplier_ids_json as jsonb),
         cast(:computed_at as timestamptz))
    """
)


def _write_cell(session, payload: dict) -> None:
    session.execute(
        _INSERT,
        {
            **payload,
            "thresholds_json": json.dumps(payload["thresholds_json"]),
            "supplier_ids_json": json.dumps(payload["supplier_ids_json"]),
        },
    )
    session.commit()


def refresh(category: Optional[str], country: Optional[str]) -> int:
    categories: List[str] = (
        [category] if category else [c["key"] for c in list_categories()]
    )
    with SessionLocal() as session:
        countries: List[str] = (
            [country.upper()[:2]] if country else list_supplier_countries(session)
        )

    written = 0
    for cat in categories:
        for cc in countries:
            t0 = time.time()
            try:
                payload = tiering.compute_cluster_cache(cat, cc)
            except Exception as exc:  # one bad cell must not abort the run
                print(f"  ! {cat}/{cc}: {exc}", file=sys.stderr)
                continue
            elapsed = time.time() - t0
            if payload is None:
                print(f"  - {cat}/{cc}: skipped (thin cell)  [{elapsed:.2f}s]")
                continue
            with SessionLocal() as session:
                _write_cell(session, payload)
            written += 1
            print(
                f"  + {cat}/{cc}: k={payload['k_selected']} "
                f"silhouette={payload['silhouette']:.3f} "
                f"n={payload['cluster_size']}  [{elapsed:.2f}s]"
            )
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh supplier cluster tiering cache.")
    ap.add_argument("--category", help="Single service category (e.g. banks).")
    ap.add_argument("--country", help="Single country ISO-2 (e.g. BE).")
    args = ap.parse_args()

    print(
        f"Refreshing supplier_cluster_cache "
        f"(category={args.category or 'ALL'}, country={args.country or 'ALL'})…"
    )
    written = refresh(args.category, args.country)
    print(f"Done. {written} cell(s) written. fallbacks={tiering.fallback_total()}")


if __name__ == "__main__":
    main()
