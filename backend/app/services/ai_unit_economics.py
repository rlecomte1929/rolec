"""
AI unit-economics rollup — Parker Step G.

Aggregates the per-call cost + carbon + token columns on ``policy_assistant_traces``
into a per-(customer, feature) rollup over an optional date range. Reads the BASE table
with portable SQL (works on both Postgres and the SQLite dev/test DB), so the admin
endpoint is testable without the Postgres-only ``mv_ai_unit_economics`` matview.

No PII: only aggregate cost / carbon / token / call-count numbers are returned.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger(__name__)


def compute_unit_economics_rollup(
    *,
    customer_id: Optional[str] = None,
    feature_key: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    session: Any = None,
) -> Dict[str, Any]:
    """Per-(customer, feature) cost/carbon rollup over ``policy_assistant_traces``.

    Filters: ``customer_id`` / ``feature_key`` (exact match, optional) and
    ``from_ts`` / ``to_ts`` (inclusive ISO-8601 strings; ``created_at`` is stored as
    ISO text so lexicographic comparison is correct). Returns per-bucket rows plus
    grand totals. Empty range → zeroed totals + empty ``rows``.
    """
    own = session is None
    s = session or SessionLocal()
    try:
        where = ["feature_key IS NOT NULL"]
        params: Dict[str, Any] = {}
        if customer_id is not None:
            where.append("customer_id = :cust")
            params["cust"] = customer_id
        if feature_key is not None:
            where.append("feature_key = :fk")
            params["fk"] = feature_key
        if from_ts:
            where.append("created_at >= :from_ts")
            params["from_ts"] = from_ts
        if to_ts:
            where.append("created_at <= :to_ts")
            params["to_ts"] = to_ts
        where_sql = " AND ".join(where)

        sql = text(
            f"""
            SELECT customer_id,
                   feature_key,
                   COUNT(*)                                    AS n_calls,
                   COALESCE(SUM(cost_usd_estimated), 0)        AS total_cost_usd,
                   COALESCE(SUM(tokens_in), 0)                 AS total_tokens_in,
                   COALESCE(SUM(tokens_out), 0)                AS total_tokens_out,
                   COALESCE(SUM(co2e_grams_estimated), 0)      AS total_co2e_grams
            FROM policy_assistant_traces
            WHERE {where_sql}
            GROUP BY customer_id, feature_key
            ORDER BY total_cost_usd DESC
            """
        )
        result = s.execute(sql, params).fetchall()
    except Exception:
        log.debug("ai_unit_economics rollup query failed", exc_info=True)
        result = []
    finally:
        if own:
            s.close()

    rows: List[Dict[str, Any]] = []
    tot_calls = tot_tin = tot_tout = 0
    tot_cost = tot_co2e = 0.0
    for r in result:
        n = int(r[2] or 0)
        cost = float(r[3] or 0.0)
        tin = int(r[4] or 0)
        tout = int(r[5] or 0)
        co2e = float(r[6] or 0.0)
        rows.append(
            {
                "customer_id": r[0],
                "feature_key": r[1],
                "n_calls": n,
                "total_cost_usd": round(cost, 6),
                "total_tokens_in": tin,
                "total_tokens_out": tout,
                "total_co2e_grams": round(co2e, 6),
            }
        )
        tot_calls += n
        tot_cost += cost
        tot_tin += tin
        tot_tout += tout
        tot_co2e += co2e

    return {
        "rows": rows,
        "totals": {
            "n_calls": tot_calls,
            "total_cost_usd": round(tot_cost, 6),
            "total_tokens_in": tot_tin,
            "total_tokens_out": tot_tout,
            "total_co2e_grams": round(tot_co2e, 6),
        },
        "filters": {
            "customer_id": customer_id,
            "feature_key": feature_key,
            "from": from_ts,
            "to": to_ts,
        },
    }
