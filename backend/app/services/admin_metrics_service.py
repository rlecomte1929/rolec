"""
Admin KPI source-of-truth (AIQ-2326 / ADMIN-IA-0a).

One function per admin metric, each with an explicit, documented DEFINITION. Every
admin surface (Today, Companies, Executive, Coverage, Country requirements) reads its
numbers from here instead of computing its own SQL, so a "tenant" means the same thing
on every page and can never drift again (the AIQ-885 / AIQ-988 / AIQ-1765 regression).

Each metric function returns a small envelope::

    {"value": <int | None>, "definition": <str>, "source": <str>, "as_of": <iso8601>}

``value`` is ``None`` when the metric cannot be computed (missing table, DB error).
Summary payloads omit that key entirely — never null, never "Unavailable".

Consistency is by construction: the tenant / people counts reuse the SAME
``get_admin_company_index`` / ``get_admin_people_index`` the Companies and People lists
use (identical is_test + synthetic-name filtering), and ``destinations_with_data`` reuses
``coverage_service``. Only cases and the content-review backlog use direct SQL here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import text

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(value: Optional[int], definition: str, source: str) -> Dict[str, Any]:
    return {"value": value, "definition": definition, "source": source, "as_of": _now_iso()}


def _include(payload: Dict[str, Any], key: str, metric: Dict[str, Any]) -> None:
    """Drop metrics that could not be computed. Never serialise null / Unavailable."""
    if metric.get("value") is None:
        return
    payload[key] = metric


def _safe_int(fn: Callable[[], int]) -> Optional[int]:
    """Run a count, degrading any failure to ``None`` (tile is then omitted)."""
    try:
        return int(fn())
    except Exception as exc:  # any single metric may fail independently
        log.warning("admin_metrics: metric failed: %s", exc)
        return None


# ── Tenants / people (reuse the canonical list queries) ─────────────────────────

def tenants_total() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        return len(db.get_admin_company_index(include_test=False))

    return _metric(
        _safe_int(_count),
        "Companies on the platform, excluding test tenants.",
        "companies via get_admin_company_index(include_test=false)",
    )


def tenants_active() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        rows = db.get_admin_company_index(include_test=False)
        return sum(1 for r in rows if int(r.get("assignments_count") or 0) > 0)

    return _metric(
        _safe_int(_count),
        "Real tenants with at least one open case assignment (assigned, submitted or awaiting intake).",
        "companies via get_admin_company_index(include_test=false) where assignments_count>0",
    )


def hr_users() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        people, _ = db.get_admin_people_index(role="HR", include_test=False)
        return len(people)

    return _metric(
        _safe_int(_count),
        "HR logins across real tenants.",
        "profiles via get_admin_people_index(role=HR, include_test=false)",
    )


def employees() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        people, _ = db.get_admin_people_index(role="EMPLOYEE", include_test=False)
        return len(people)

    return _metric(
        _safe_int(_count),
        "Employee logins across real tenants.",
        "profiles via get_admin_people_index(role=EMPLOYEE, include_test=false)",
    )


def signups() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        people, _ = db.get_admin_people_index(include_test=False)
        return len(people)

    return _metric(
        _safe_int(_count),
        "Everyone with a login on a real tenant, any role.",
        "profiles via get_admin_people_index(include_test=false)",
    )


# ── Cases (direct SQL — status lives on case_assignments) ───────────────────────

_OPEN_STATUSES = ("assigned", "submitted", "awaiting_intake")


def _scalar(query: str) -> int:
    from ...database import db
    with db.engine.connect() as conn:
        row = conn.execute(text(query)).first()
    return int(row[0]) if row and row[0] is not None else 0


def cases_total() -> Dict[str, Any]:
    return _metric(
        _safe_int(lambda: _scalar("SELECT count(*) FROM case_assignments")),
        "Every relocation case assignment, open or closed.",
        "count(*) from case_assignments",
    )


def cases_open() -> Dict[str, Any]:
    statuses = ", ".join("'" + s + "'" for s in _OPEN_STATUSES)
    return _metric(
        _safe_int(lambda: _scalar(
            f"SELECT count(*) FROM case_assignments WHERE status IN ({statuses})"
        )),
        "Cases whose assignment is assigned, submitted or awaiting intake.",
        "count(*) from case_assignments where status in (assigned, submitted, awaiting_intake)",
    )


def cases_closed() -> Dict[str, Any]:
    return _metric(
        _safe_int(lambda: _scalar(
            "SELECT count(*) FROM case_assignments WHERE status = 'closed' OR archived_at IS NOT NULL"
        )),
        "Cases whose assignment status is closed.",
        "count(*) from case_assignments where status='closed' or archived_at is not null",
    )


# ── Coverage / catalog ──────────────────────────────────────────────────────────

def destinations_with_data() -> Dict[str, Any]:
    def _count() -> int:
        from .coverage_service import get_coverage_summary
        totals = (get_coverage_summary() or {}).get("totals") or {}
        return int(totals.get("destinations") or 0)

    return _metric(
        _safe_int(_count),
        "Destinations with at least one requirement fact or vetted provider in the catalog.",
        "coverage_service.get_coverage_summary().totals.destinations",
    )


def destinations_curated() -> Dict[str, Any]:
    def _count() -> int:
        from ..db import SessionLocal
        from .. import crud
        with SessionLocal() as session:
            return len(crud.list_country_profiles(session))

    return _metric(
        _safe_int(_count),
        "Countries with a curated requirements catalog.",
        "count of country_profiles via crud.list_country_profiles",
    )


def content_review_pending() -> Dict[str, Any]:
    return _metric(
        _safe_int(lambda: _scalar(
            "SELECT count(*) FROM requirement_facts WHERE status = 'pending'"
        )),
        "Requirement facts waiting for a human to review before they are shown.",
        "count(*) from requirement_facts where status='pending'",
    )


def prospects_waiting() -> Dict[str, Any]:
    def _count() -> int:
        return _scalar("SELECT count(*) FROM prospect_candidates")

    return _metric(
        _safe_int(_count),
        "People in the outreach pipeline who have not become tenants yet.",
        "count(*) from prospect_candidates",
    )


# ── Aggregates ───────────────────────────────────────────────────────────────────

def build_companies_overview() -> Dict[str, Any]:
    """Counts for the Companies page KPI strip — reads the shared metric functions
    (no duplicated SQL). This is what GET /api/admin/companies/overview returns."""
    payload: Dict[str, Any] = {"as_of": _now_iso()}
    _include(payload, "tenants_total", tenants_total())
    _include(payload, "tenants_active", tenants_active())
    _include(payload, "hr_users", hr_users())
    _include(payload, "employees", employees())
    return payload


def build_metrics_summary() -> Dict[str, Any]:
    """The whole admin KPI payload — GET /api/admin/metrics/summary. Every consumer
    surface reads from here so the same number appears everywhere."""
    payload: Dict[str, Any] = {"as_of": _now_iso()}
    _include(payload, "tenants_total", tenants_total())
    _include(payload, "tenants_active", tenants_active())
    _include(payload, "hr_users", hr_users())
    _include(payload, "employees", employees())
    _include(payload, "signups", signups())
    _include(payload, "cases_total", cases_total())
    _include(payload, "cases_open", cases_open())
    _include(payload, "cases_closed", cases_closed())
    _include(payload, "destinations_with_data", destinations_with_data())
    _include(payload, "destinations_curated", destinations_curated())
    _include(payload, "content_review_pending", content_review_pending())
    _include(payload, "prospects_waiting", prospects_waiting())
    return payload
