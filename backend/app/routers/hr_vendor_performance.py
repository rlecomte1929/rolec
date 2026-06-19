"""
HR Vendor Performance Dashboard — GET /api/hr/vendor-performance

Returns a company-scoped vendor performance summary for the HR "Vendor
Performance" tab (NAV-SP-2):

  summary      — platform-wide KPIs (avg rating, avg cost, vendor count,
                 avg response SLA)
  monthly_trend — cases handled per month for the last 6 months (derived
                  from provider_ratings.created_at, grouped by supplier and
                  service_category so the frontend can filter)
  categories   — per-service-category breakdown: vendor count, avg rating,
                 avg cost, health status; each category contains its full
                 vendor roster with recent company-scoped reviews

Data sources:
  suppliers × supplier_service_capabilities × supplier_scoring_metadata
  × provider_ratings
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..auth_deps import get_current_user
from ..db import SessionLocal
from ...database import db as _db
from ...schemas import UserRole

router = APIRouter(tags=["hr_vendor_performance"])
log = logging.getLogger(__name__)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _require_hr(user: Dict[str, Any]) -> str:
    role = (user.get("role") or "").upper()
    if role not in (UserRole.HR.value, UserRole.ADMIN.value) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="HR or Admin only")
    profile = _db.get_profile_record(user.get("id"))
    company_id = (profile or {}).get("company_id") or user.get("company") or ""
    return str(company_id)


# ── Vendor health classifier ──────────────────────────────────────────────────

def _health_status(vendor_count: int, avg_rating: Optional[float]) -> str:
    if vendor_count <= 1:
        return "critical"
    if vendor_count == 2:
        return "low_coverage"
    if avg_rating is not None and avg_rating < 3.8:
        return "review"
    return "healthy"


# Time-range toggle → (SQL interval for the monthly window, number of month buckets).
_RANGE_WINDOWS: Dict[str, str] = {
    "30d": "30 days",
    "90d": "90 days",
    "12mo": "12 months",
}


def _coverage_status(vendor_count: int) -> str:
    """Heatmap cell status: healthy (3+), thin (1-2), gap (0).

    Only category × country pairs with ≥1 active vendor are returned by the
    query, so 'gap' is surfaced client-side for cells the matrix never produced.
    """
    if vendor_count <= 0:
        return "gap"
    if vendor_count <= 2:
        return "thin"
    return "healthy"


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/api/hr/vendor-performance")
def get_vendor_performance(
    range_: str = Query("90d", alias="range"),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Full vendor performance snapshot for the HR dashboard tab.

    `range` (30d | 90d | 12mo, default 90d) windows the monthly case trend.
    All review data is scoped to the caller's company_id so HR never sees
    another company's employee feedback.
    """
    company_id = _require_hr(user)
    window = _RANGE_WINDOWS.get(range_, _RANGE_WINDOWS["90d"])

    with SessionLocal() as session:

        # ── 1. Summary KPIs ──────────────────────────────────────────────────
        kpi = session.execute(text("""
            SELECT
                ROUND(AVG(ssm.average_rating)::numeric, 1)::float       AS avg_rating,
                ROUND(AVG(
                    CASE
                        WHEN ssm.price_range_min_eur IS NOT NULL
                         AND ssm.price_range_max_eur IS NOT NULL
                            THEN (ssm.price_range_min_eur + ssm.price_range_max_eur) / 2.0
                        WHEN ssm.price_range_min_eur IS NOT NULL
                            THEN ssm.price_range_min_eur::float
                        WHEN ssm.price_range_max_eur IS NOT NULL
                            THEN ssm.price_range_max_eur::float
                    END
                )::numeric, 0)::int                                      AS avg_cost_eur,
                COUNT(DISTINCT s.id)::int                                AS active_vendors,
                ROUND(AVG(ssm.response_sla_hours)::numeric, 0)::int     AS avg_response_sla_hours
            FROM suppliers s
            LEFT JOIN supplier_scoring_metadata ssm ON ssm.supplier_id = s.id
            WHERE s.status = 'active'
        """)).first()

        # ── 2. Monthly case trend, windowed by `range` ───────────────────────
        # Source: provider_ratings (one row per employee+supplier+case).
        # Grouped by month × supplier × service_category so the frontend can
        # filter down to a single vendor or category. Company-scoped — skipped
        # when the caller has no resolvable company_id (a CAST("" AS uuid) would
        # otherwise 500 the whole dashboard); global vendor data still renders.
        monthly_rows = []
        if company_id:
            monthly_rows = session.execute(text("""
                SELECT
                    to_char(pr.created_at, 'YYYY-MM')             AS month,
                    pr.supplier_id,
                    ssc.service_category                           AS category,
                    COUNT(DISTINCT pr.case_id)::int                AS case_count
                FROM provider_ratings pr
                JOIN suppliers s     ON s.id = pr.supplier_id AND s.status = 'active'
                JOIN supplier_service_capabilities ssc
                                     ON ssc.supplier_id = s.id
                WHERE pr.company_id = CAST(:cid AS uuid)
                  AND pr.created_at >= now() - CAST(:window AS interval)
                GROUP BY month, pr.supplier_id, ssc.service_category
                ORDER BY month ASC
            """), {"cid": company_id, "window": window}).mappings().all()

        # ── 3. Per-category aggregate ─────────────────────────────────────────
        cat_rows = session.execute(text("""
            SELECT
                ssc.service_category                                          AS category,
                COUNT(DISTINCT s.id)::int                                     AS vendor_count,
                ROUND(AVG(ssm.average_rating)::numeric, 1)::float            AS avg_rating,
                ROUND(AVG(
                    CASE
                        WHEN ssm.price_range_min_eur IS NOT NULL
                         AND ssm.price_range_max_eur IS NOT NULL
                            THEN (ssm.price_range_min_eur + ssm.price_range_max_eur) / 2.0
                        WHEN ssm.price_range_min_eur IS NOT NULL
                            THEN ssm.price_range_min_eur::float
                        WHEN ssm.price_range_max_eur IS NOT NULL
                            THEN ssm.price_range_max_eur::float
                    END
                )::numeric, 0)::int                                           AS avg_cost_eur
            FROM suppliers s
            JOIN supplier_service_capabilities ssc ON ssc.supplier_id = s.id
            LEFT JOIN supplier_scoring_metadata ssm ON ssm.supplier_id = s.id
            WHERE s.status = 'active'
            GROUP BY ssc.service_category
            ORDER BY vendor_count DESC, ssc.service_category
        """)).mappings().all()

        # ── 3b. Coverage matrix — active vendors per (category × country) ─────
        # Powers the direction-B coverage heatmap: where are we thin / where do
        # we need to qualify more vendors. country_code is the destination the
        # capability serves (corridor is a Tier-2 follow-up; suppliers carry no
        # origin→dest corridor yet).
        coverage_rows = session.execute(text("""
            SELECT
                ssc.service_category              AS category,
                ssc.country_code                  AS country,
                COUNT(DISTINCT s.id)::int         AS vendor_count
            FROM suppliers s
            JOIN supplier_service_capabilities ssc ON ssc.supplier_id = s.id
            WHERE s.status = 'active'
              AND ssc.country_code IS NOT NULL
            GROUP BY ssc.service_category, ssc.country_code
            ORDER BY ssc.service_category, ssc.country_code
        """)).mappings().all()

        # ── 4. All active vendors with their first capability + scoring ───────
        vendor_rows = session.execute(text("""
            SELECT DISTINCT ON (s.id, ssc.service_category)
                s.id                              AS id,
                s.name                            AS name,
                ssc.service_category              AS category,
                ssc.city_name,
                ssc.country_code,
                ssm.average_rating,
                ssm.review_count,
                ssm.response_sla_hours,
                ssm.price_range_min_eur,
                ssm.price_range_max_eur
            FROM suppliers s
            JOIN supplier_service_capabilities ssc ON ssc.supplier_id = s.id
            LEFT JOIN supplier_scoring_metadata ssm ON ssm.supplier_id = s.id
            WHERE s.status = 'active'
            ORDER BY s.id, ssc.service_category, ssm.average_rating DESC NULLS LAST
        """)).mappings().all()

        # ── 5. Recent reviews scoped to this company (max 5 per supplier) ────
        # Same no-company guard as the monthly trend above.
        review_rows = []
        if company_id:
            review_rows = session.execute(text("""
                SELECT
                    pr.supplier_id,
                    pr.score,
                    pr.comment,
                    pr.created_at::date AS review_date
                FROM provider_ratings pr
                WHERE pr.company_id = CAST(:cid AS uuid)
                ORDER BY pr.created_at DESC
            """), {"cid": company_id}).mappings().all()

    # ── Assemble response ─────────────────────────────────────────────────────

    # Index reviews by supplier_id (keep max 5 per supplier)
    reviews_by_supplier: Dict[str, List[Dict]] = {}
    for r in review_rows:
        sid = str(r["supplier_id"])
        bucket = reviews_by_supplier.setdefault(sid, [])
        if len(bucket) >= 5:
            continue
        d = r["review_date"]
        bucket.append({
            "score": int(r["score"]),
            "comment": r["comment"] or "",
            "date": d.strftime("%b %-d") if hasattr(d, "strftime") else str(d),
        })

    # Build monthly trend list (each entry includes supplier_id + category)
    monthly_trend = [
        {
            "month": str(r["month"]),
            "supplier_id": str(r["supplier_id"]),
            "category": r["category"] or "other",
            "case_count": int(r["case_count"]),
        }
        for r in monthly_rows
    ]

    # Build per-category vendor lists
    vendors_by_cat: Dict[str, List[Dict]] = {}
    for v in vendor_rows:
        cat = v["category"] or "other"
        sid = str(v["id"])
        loc_parts = [v["city_name"], v["country_code"]]
        location = " · ".join(p for p in loc_parts if p) or "Global"
        avg_r = float(v["average_rating"]) if v["average_rating"] is not None else None
        cost_min = v["price_range_min_eur"]
        cost_max = v["price_range_max_eur"]
        avg_cost: Optional[int] = None
        if cost_min is not None and cost_max is not None:
            avg_cost = int((cost_min + cost_max) // 2)
        elif cost_min is not None:
            avg_cost = int(cost_min)
        elif cost_max is not None:
            avg_cost = int(cost_max)
        vendors_by_cat.setdefault(cat, []).append({
            "id": sid,
            "name": str(v["name"]),
            "location": location,
            "rating": round(avg_r, 1) if avg_r is not None else None,
            "review_count": int(v["review_count"] or 0),
            "response_sla_hours": int(v["response_sla_hours"]) if v["response_sla_hours"] else None,
            "cost_eur": avg_cost,
            "cost_min_eur": int(cost_min) if cost_min is not None else None,
            "cost_max_eur": int(cost_max) if cost_max is not None else None,
            "recent_reviews": reviews_by_supplier.get(sid, []),
        })

    # Sort vendors within each category by rating desc
    for cat_vendors in vendors_by_cat.values():
        cat_vendors.sort(key=lambda v: v["rating"] or 0.0, reverse=True)

    categories = [
        {
            "category": str(r["category"] or "other"),
            "vendor_count": int(r["vendor_count"] or 0),
            "avg_rating": float(r["avg_rating"]) if r["avg_rating"] is not None else None,
            "avg_cost_eur": int(r["avg_cost_eur"]) if r["avg_cost_eur"] is not None else None,
            "status": _health_status(
                int(r["vendor_count"] or 0),
                float(r["avg_rating"]) if r["avg_rating"] is not None else None,
            ),
            "vendors": vendors_by_cat.get(str(r["category"] or "other"), []),
        }
        for r in cat_rows
    ]

    coverage = [
        {
            "category": str(r["category"] or "other"),
            "country": str(r["country"]),
            "vendor_count": int(r["vendor_count"] or 0),
            "status": _coverage_status(int(r["vendor_count"] or 0)),
        }
        for r in coverage_rows
    ]

    # ── Trend lines from the nightly snapshot table (Tier 3) ──────────────────
    # Runs in its own session so a missing table (migration not yet applied) or
    # any error degrades to empty arrays — the dashboard shows an honest
    # "collecting data" state instead of 500-ing the whole page.
    cost_trend: List[Dict[str, Any]] = []
    rating_trend: List[Dict[str, Any]] = []
    try:
        with SessionLocal() as snap_session:
            trend_rows = snap_session.execute(text("""
                SELECT
                    captured_date::text                          AS date,
                    ROUND(AVG(avg_rating)::numeric, 1)::float    AS avg_rating,
                    ROUND(AVG(avg_cost_eur)::numeric, 0)::int    AS avg_cost_eur
                FROM public.vendor_metric_snapshots
                WHERE captured_date >= CURRENT_DATE - CAST(:window AS interval)
                GROUP BY captured_date
                ORDER BY captured_date ASC
            """), {"window": window}).mappings().all()
        for r in trend_rows:
            if r["avg_cost_eur"] is not None:
                cost_trend.append({"date": str(r["date"]), "avg_cost_eur": int(r["avg_cost_eur"])})
            if r["avg_rating"] is not None:
                rating_trend.append({"date": str(r["date"]), "avg_rating": float(r["avg_rating"])})
    except Exception:
        log.warning("vendor_metric_snapshots unavailable; trend lines empty", exc_info=True)

    return {
        "summary": {
            "avg_rating": float(kpi.avg_rating) if kpi and kpi.avg_rating is not None else None,
            "avg_cost_eur": int(kpi.avg_cost_eur) if kpi and kpi.avg_cost_eur is not None else None,
            "active_vendors": int(kpi.active_vendors) if kpi and kpi.active_vendors else 0,
            "avg_response_sla_hours": int(kpi.avg_response_sla_hours) if kpi and kpi.avg_response_sla_hours else None,
        },
        "monthly_trend": monthly_trend,
        "categories": categories,
        "coverage": coverage,
        "cost_trend": cost_trend,
        "rating_trend": rating_trend,
    }
