"""
Executive "State of the Platform" dashboard — aggregation service.

Rolls existing data up into ONE leadership payload. Five panels are pure
aggregation of data we already have (growth, activation funnel, throughput, AI
cost, AI health); reliability + NPS are honest "not instrumented yet" placeholders.
Each panel is wrapped in `_safe` so a missing table/error degrades that panel to
{available: false} instead of 500-ing the dashboard. Every panel carries a
`data_source` flag (live | estimated | mock | unavailable) so leadership never
mistakes estimated/mock for live — and the platform is pre-launch (test data).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict

from sqlalchemy import text

from .ai_unit_economics import compute_unit_economics_rollup
from .rag_eval_reports import build_dashboard

log = logging.getLogger(__name__)


def _since_iso(window_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()


def _safe(fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        return fn()
    except Exception as exc:  # any panel can fail independently
        log.warning("exec-overview panel failed: %s", exc)
        return {"available": False, "data_source": "unavailable", "error": str(exc)[:200]}


def _scalar_counts(query: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from ...database import db

    with db.engine.begin() as conn:
        row = conn.execute(text(query), params).mappings().first()
    return dict(row) if row else {}


def _growth() -> Dict[str, Any]:
    # [AIQ-2326] Read the tenant/people counts from the shared admin metrics SoT so
    # "Companies" here is the SAME real-tenant number the Companies page shows (it used
    # to be a raw count(*) of ALL companies incl. test tenants — hence the 71-vs-48
    # mismatch). new_companies stays a windowed direct count (not an SoT metric).
    from .admin_metrics_service import tenants_total, hr_users, employees
    new_companies = _scalar_counts(
        "SELECT count(*) AS new_companies FROM public.companies WHERE created_at >= :since",
        {"since": _since_iso(30)},
    )
    return {
        "available": True,
        "data_source": "live",
        "companies": tenants_total().get("value"),
        "hr_users": hr_users().get("value"),
        "employees": employees().get("value"),
        "new_companies": new_companies.get("new_companies"),
    }


def _funnel(window_days: int) -> Dict[str, Any]:
    # [AIQ-2326] signups / cases counts come from the shared admin metrics SoT (same
    # real-only definitions as everywhere else). in_intake stays a direct count.
    from .admin_metrics_service import signups, cases_total, cases_closed
    in_intake = _scalar_counts(
        "SELECT count(*) AS in_intake FROM public.case_assignments "
        "WHERE status IN ('awaiting_intake', 'submitted')",
        {},
    )
    return {
        "available": True,
        "data_source": "live",
        "signups": signups().get("value"),
        "in_intake": in_intake.get("in_intake"),
        "cases": cases_total().get("value"),
        "completed": cases_closed().get("value"),
    }


def _throughput(window_days: int) -> Dict[str, Any]:
    bench = _scalar_counts(
        "SELECT median_completion_days, case_count FROM public.industry_benchmarks "
        "WHERE is_valid = true ORDER BY computed_at DESC LIMIT 1",
        {},
    )
    flow = _scalar_counts(
        """
        SELECT (SELECT count(*) FROM public.case_assignments WHERE created_at >= :since) AS created_in_window,
               (SELECT count(*) FROM public.case_assignments
                 WHERE (status = 'closed' OR archived_at IS NOT NULL)
                   AND COALESCE(archived_at, submitted_at, created_at) >= :since) AS completed_in_window
        """,
        {"since": _since_iso(window_days)},
    )
    return {
        "available": True,
        "data_source": "live",
        "median_completion_days": bench.get("median_completion_days"),
        "benchmark_case_count": bench.get("case_count"),
        **flow,
    }


def _ai_cost(window_days: int) -> Dict[str, Any]:
    rollup = compute_unit_economics_rollup(from_ts=_since_iso(window_days))
    totals = rollup.get("totals") or {}
    return {
        "available": True,
        "data_source": "estimated",  # cost_usd_estimated; policy-assistant traces only
        "total_cost_usd": totals.get("total_cost_usd"),
        "total_tokens_in": totals.get("total_tokens_in"),
        "total_tokens_out": totals.get("total_tokens_out"),
        "call_count": totals.get("n_calls") or totals.get("call_count"),
    }


def _health_score(dashboard: Dict[str, Any]) -> Dict[str, Any]:
    metrics = dashboard.get("metrics") or []
    total = len(metrics)
    healthy = sum(1 for m in metrics if not (m.get("alert") or {}).get("firing"))
    return {
        "available": True,
        "data_source": dashboard.get("source", "mock"),
        "score": round(100 * healthy / total) if total else None,
        "healthy": healthy,
        "total": total,
    }


def _ai_health() -> Dict[str, Any]:
    return _health_score(build_dashboard())


def build_exec_overview(window_days: int = 30) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "growth": _safe(_growth),
        "funnel": _safe(lambda: _funnel(window_days)),
        "throughput": _safe(lambda: _throughput(window_days)),
        "ai_cost": _safe(lambda: _ai_cost(window_days)),
        "ai_health": _safe(_ai_health),
        "reliability": {
            "available": False,
            "data_source": "unavailable",
            "note": "Error rate / latency / uptime live in Sentry (perf sampling off); not queryable in-DB. Needs Sentry API or a request-metrics table.",
        },
        "nps": {
            "available": False,
            "data_source": "unavailable",
            "note": "No NPS/CSAT survey instrumentation yet. Needs a survey table + capture UI.",
        },
    }
