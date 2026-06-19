"""
[NAV-SP-2 Tier 3] Vendor metric snapshot service.

Captures one row per (supplier × service_category × day) into
public.vendor_metric_snapshots so the Vendor Performance dashboard can draw real
cost / review-score trend lines and ▲/▼ watchlist deltas (supplier_scoring_metadata
only stores the current value).

Called daily by POST /api/crons/snapshot-vendor-metrics via the backend service
role (SessionLocal bypasses RLS). Idempotent: upserts on
(supplier_id, service_category, captured_date), so a same-day re-run updates rather
than duplicates.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger(__name__)

# Mirrors the per-vendor aggregate the dashboard already computes (one scoring
# row per supplier; DISTINCT ON keeps one row per supplier × category). Cost is
# the midpoint of the price range, matching hr_vendor_performance.py.
_SNAPSHOT_SQL = text("""
    INSERT INTO public.vendor_metric_snapshots
        (supplier_id, service_category, captured_date, avg_rating, avg_cost_eur, review_count)
    SELECT DISTINCT ON (s.id, ssc.service_category)
        s.id,
        ssc.service_category,
        CURRENT_DATE,
        ROUND(ssm.average_rating::numeric, 1),
        CASE
            WHEN ssm.price_range_min_eur IS NOT NULL AND ssm.price_range_max_eur IS NOT NULL
                THEN ((ssm.price_range_min_eur + ssm.price_range_max_eur) / 2)::int
            WHEN ssm.price_range_min_eur IS NOT NULL THEN ssm.price_range_min_eur::int
            WHEN ssm.price_range_max_eur IS NOT NULL THEN ssm.price_range_max_eur::int
        END,
        ssm.review_count
    FROM suppliers s
    JOIN supplier_service_capabilities ssc ON ssc.supplier_id = s.id
    LEFT JOIN supplier_scoring_metadata ssm ON ssm.supplier_id = s.id
    WHERE s.status = 'active'
    ORDER BY s.id, ssc.service_category, ssm.average_rating DESC NULLS LAST
    ON CONFLICT (supplier_id, service_category, captured_date)
    DO UPDATE SET
        avg_rating   = EXCLUDED.avg_rating,
        avg_cost_eur = EXCLUDED.avg_cost_eur,
        review_count = EXCLUDED.review_count
""")


def snapshot_vendor_metrics() -> Dict[str, Any]:
    """Upsert today's snapshot for every active supplier × category. Returns the
    number of rows written. Never raises to the cron caller — logs and re-raises
    only on a hard DB error so the workflow surfaces a non-zero exit."""
    with SessionLocal() as session:
        result = session.execute(_SNAPSHOT_SQL)
        session.commit()
        rows = result.rowcount if result.rowcount is not None else 0
        log.info("snapshot_vendor_metrics: upserted %s rows", rows)
        return {"rows_upserted": rows}
