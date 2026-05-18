"""
Analytics router — AIQ-39-B

Endpoints:
  HR-facing:
    GET  /api/hr/analytics   — workspace benchmarking stats + industry comparison
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..auth_deps import get_org_id_for_hr_user
from ...database import db

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/hr/analytics")
def get_hr_analytics(
    org_id: str = Depends(get_org_id_for_hr_user),
) -> Dict[str, Any]:
    """
    Return pre-computed benchmarking stats for the HR org.

    Response shape:
    {
      "workspace": {
        "avg_completion_days": float | null,
        "compliance_incident_rate": float | null,
        "total_cases_in_window": int,
        "closed_cases_in_window": int,
        "top_delay_causes": [{"cause": str, "count": int}, ...],
        "corridor_breakdown": [{"corridor": str, "avg_days": float, "case_count": int}, ...],
        "computed_at": str | null
      },
      "industry": {
        "median_completion_days": float | null,
        "median_compliance_rate": float | null,
        "case_count": int,
        "workspace_count": int,
        "is_valid": bool,
        "computed_at": str | null
      } | null,
      "trend": [
        {"month": "YYYY-MM", "avg_completion_days": float | null}, ...
      ]
    }
    """
    with db.engine.begin() as conn:
        # Latest workspace stats for this org
        ws_row = conn.execute(
            text("""
                SELECT avg_completion_days, compliance_incident_rate,
                       total_cases_in_window, closed_cases_in_window,
                       top_delay_causes, corridor_breakdown,
                       computed_at
                FROM public.workspace_stats
                WHERE org_id = :org_id
                ORDER BY computed_at DESC
                LIMIT 1
            """),
            {"org_id": org_id},
        ).mappings().first()

        # Last 12 months of workspace stats for trend (one row per night —
        # we pick the most recent entry per calendar month)
        trend_rows = conn.execute(
            text("""
                SELECT DISTINCT ON (date_trunc('month', computed_at))
                    to_char(date_trunc('month', computed_at), 'YYYY-MM') AS month,
                    avg_completion_days
                FROM public.workspace_stats
                WHERE org_id = :org_id
                  AND computed_at >= NOW() - INTERVAL '12 months'
                ORDER BY date_trunc('month', computed_at) DESC, computed_at DESC
            """),
            {"org_id": org_id},
        ).mappings().all()

        # Most recent valid industry benchmark
        ib_row = conn.execute(
            text("""
                SELECT median_completion_days, median_compliance_rate,
                       case_count, workspace_count, is_valid, computed_at
                FROM public.industry_benchmarks
                WHERE is_valid = true
                ORDER BY computed_at DESC
                LIMIT 1
            """),
        ).mappings().first()

    # Build workspace payload
    if ws_row:
        top_delay_raw = ws_row["top_delay_causes"] or []
        corridor_raw = ws_row["corridor_breakdown"] or []

        # Normalise top_delay_causes: support both list-of-dicts and dict formats
        top_delay: List[Dict[str, Any]] = []
        if isinstance(top_delay_raw, list):
            for item in top_delay_raw:
                if isinstance(item, dict):
                    top_delay.append({
                        "cause": item.get("cause") or item.get("delay_reason") or "Unknown",
                        "count": int(item.get("count") or item.get("frequency") or 0),
                    })
        elif isinstance(top_delay_raw, dict):
            for cause, count in top_delay_raw.items():
                top_delay.append({"cause": cause, "count": int(count)})

        # Normalise corridor_breakdown
        corridors: List[Dict[str, Any]] = []
        if isinstance(corridor_raw, list):
            for item in corridor_raw:
                if isinstance(item, dict):
                    corridors.append({
                        "corridor": item.get("corridor") or f"{item.get('origin','?')}→{item.get('destination','?')}",
                        "avg_days": float(item.get("avg_days") or item.get("avg_completion_days") or 0),
                        "case_count": int(item.get("case_count") or item.get("count") or 0),
                    })
        elif isinstance(corridor_raw, dict):
            for corridor, stats in corridor_raw.items():
                if isinstance(stats, dict):
                    corridors.append({
                        "corridor": corridor,
                        "avg_days": float(stats.get("avg_days") or 0),
                        "case_count": int(stats.get("case_count") or 0),
                    })

        workspace = {
            "avg_completion_days": float(ws_row["avg_completion_days"]) if ws_row["avg_completion_days"] is not None else None,
            "compliance_incident_rate": float(ws_row["compliance_incident_rate"]) if ws_row["compliance_incident_rate"] is not None else None,
            "total_cases_in_window": int(ws_row["total_cases_in_window"] or 0),
            "closed_cases_in_window": int(ws_row["closed_cases_in_window"] or 0),
            "top_delay_causes": sorted(top_delay, key=lambda x: x["count"], reverse=True)[:5],
            "corridor_breakdown": sorted(corridors, key=lambda x: x["case_count"], reverse=True),
            "computed_at": ws_row["computed_at"].isoformat() if ws_row["computed_at"] else None,
        }
    else:
        workspace = {
            "avg_completion_days": None,
            "compliance_incident_rate": None,
            "total_cases_in_window": 0,
            "closed_cases_in_window": 0,
            "top_delay_causes": [],
            "corridor_breakdown": [],
            "computed_at": None,
        }

    # Build industry payload (None if no valid benchmark)
    industry: Optional[Dict[str, Any]] = None
    if ib_row and ib_row["is_valid"]:
        industry = {
            "median_completion_days": float(ib_row["median_completion_days"]) if ib_row["median_completion_days"] is not None else None,
            "median_compliance_rate": float(ib_row["median_compliance_rate"]) if ib_row["median_compliance_rate"] is not None else None,
            "case_count": int(ib_row["case_count"] or 0),
            "workspace_count": int(ib_row["workspace_count"] or 0),
            "is_valid": True,
            "computed_at": ib_row["computed_at"].isoformat() if ib_row["computed_at"] else None,
        }

    # Build trend (sorted oldest → newest for the chart)
    trend = [
        {
            "month": r["month"],
            "avg_completion_days": float(r["avg_completion_days"]) if r["avg_completion_days"] is not None else None,
        }
        for r in sorted(trend_rows, key=lambda x: x["month"])
    ]

    return {
        "workspace": workspace,
        "industry": industry,
        "trend": trend,
    }
