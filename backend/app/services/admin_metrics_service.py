"""
Admin KPI source-of-truth (AIQ-2326 / ADMIN-IA-0a).

One function per admin metric, each with an explicit, documented DEFINITION. Every
admin surface (Today, Companies, Executive, Coverage, Country requirements) reads its
numbers from here instead of computing its own SQL, so a "tenant" means the same thing
on every page and can never drift again (the AIQ-885 / AIQ-988 / AIQ-1765 regression).

Each metric returns a small envelope::

    {"value": <int | None>, "definition": <str>, "source": <str>, "as_of": <iso8601>}

``value`` is ``None`` when the metric cannot be computed (missing table, DB error). The
definition/source/as_of are ALWAYS present so the UI can render the tooltip and decide
to omit the tile (the UX rule: a metric that cannot be computed shows nothing, never
"Unavailable").

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
        "Companies excluding synthetic QA/test tenants (is_test=false and not a "
        "known seed name). The same list shown on Companies.",
        "companies via get_admin_company_index(include_test=false)",
    )


def tenants_active() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        rows = db.get_admin_company_index(include_test=False)
        return sum(1 for r in rows if int(r.get("assignments_count") or 0) > 0)

    return _metric(
        _safe_int(_count),
        "Real tenants with at least one relocation case assignment. Companies has no "
        "status column, so 'active' means 'has activity', not a manual flag.",
        "companies via get_admin_company_index(include_test=false) where assignments_count>0",
    )


def hr_users() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        people, _ = db.get_admin_people_index(role="HR", include_test=False)
        return len(people)

    return _metric(
        _safe_int(_count),
        "People with the HR role (or an hr_users link), excluding test accounts.",
        "profiles via get_admin_people_index(role=HR, include_test=false)",
    )


def employees() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        people, _ = db.get_admin_people_index(role="EMPLOYEE", include_test=False)
        return len(people)

    return _metric(
        _safe_int(_count),
        "People with the EMPLOYEE role (or an employees link), excluding test accounts.",
        "profiles via get_admin_people_index(role=EMPLOYEE, include_test=false)",
    )


def signups() -> Dict[str, Any]:
    def _count() -> int:
        from ...database import db
        people, _ = db.get_admin_people_index(include_test=False)
        return len(people)

    return _metric(
        _safe_int(_count),
        "All real people profiles (any role), excluding test accounts.",
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
        "All case assignments ever created.",
        "count(*) from case_assignments",
    )


def cases_open() -> Dict[str, Any]:
    statuses = ", ".join("'" + s + "'" for s in _OPEN_STATUSES)
    return _metric(
        _safe_int(lambda: _scalar(
            f"SELECT count(*) FROM case_assignments WHERE status IN ({statuses})"
        )),
        "Case assignments not yet closed (assigned, submitted or awaiting intake).",
        "count(*) from case_assignments where status in (assigned, submitted, awaiting_intake)",
    )


def cases_closed() -> Dict[str, Any]:
    return _metric(
        _safe_int(lambda: _scalar(
            "SELECT count(*) FROM case_assignments WHERE status = 'closed' OR archived_at IS NOT NULL"
        )),
        "Case assignments that are closed or archived.",
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
        "Destinations that have at least some immigration facts or provider data "
        "(the Coverage catalog definition).",
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
        "Countries with a curated requirement profile shown on Country requirements "
        "(a stricter bar than 'has any data').",
        "count of country_profiles via crud.list_country_profiles",
    )


def content_review_pending() -> Dict[str, Any]:
    return _metric(
        _safe_int(lambda: _scalar(
            "SELECT count(*) FROM requirement_facts WHERE status = 'pending'"
        )),
        "Requirement facts awaiting human review before they can be served.",
        "count(*) from requirement_facts where status='pending'",
    )


def prospects_waiting() -> Dict[str, Any]:
    def _count() -> int:
        return _scalar("SELECT count(*) FROM prospect_candidates")

    return _metric(
        _safe_int(_count),
        "Prospect candidates in the outreach pipeline.",
        "count(*) from prospect_candidates",
    )


# ── Aggregates ───────────────────────────────────────────────────────────────────

def build_companies_overview() -> Dict[str, Any]:
    """Counts for the Companies page KPI strip — reads the shared metric functions
    (no duplicated SQL). This is what GET /api/admin/companies/overview returns."""
    return {
        "tenants_total": tenants_total(),
        "tenants_active": tenants_active(),
        "hr_users": hr_users(),
        "employees": employees(),
        "as_of": _now_iso(),
    }


def build_metrics_summary() -> Dict[str, Any]:
    """The whole admin KPI payload — GET /api/admin/metrics/summary. Every consumer
    surface reads from here so the same number appears everywhere."""
    return {
        "tenants_total": tenants_total(),
        "tenants_active": tenants_active(),
        "hr_users": hr_users(),
        "employees": employees(),
        "signups": signups(),
        "cases_total": cases_total(),
        "cases_open": cases_open(),
        "cases_closed": cases_closed(),
        "destinations_with_data": destinations_with_data(),
        "destinations_curated": destinations_curated(),
        "content_review_pending": content_review_pending(),
        "prospects_waiting": prospects_waiting(),
        "as_of": _now_iso(),
    }
