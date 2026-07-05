"""Admin Test-Drive dashboard — aggregation + contact CSV (AIQ-1428 / TD-10).

GET /api/admin/test-drive/overview — scorecard + funnel + pilot leads + testimonials,
sliceable by ?corridor= & ?segment=. Reads the TD-1 campaign tables (test_sessions,
survey_responses, funnel_events) via the service-role db.engine (bypasses the admin-read
RLS — the intended backend path). Each panel soft-fails so the dashboard never 500s.

GET /api/admin/test-drive/contacts.csv — consented contact list for pipeline work.

Admin-gated (require_admin) — read-only.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from ..auth_deps import require_admin
from ...database import db

router = APIRouter(prefix="/api/admin", tags=["admin-test-drive"])
logger = logging.getLogger(__name__)

# SQL clause fragments (kept as module constants so they never sit inside an f-string
# expression — Python 3.11 forbids backslashes/quotes there).
_PILOT_CLAUSE = "pilot_interest IN ('yes', 'maybe')"
_TESTIMONIAL_CLAUSE = "testimonial IS NOT NULL AND testimonial <> '' AND testimonial_consent = :consent"
_REFERRAL_PRESENT = (
    "((referral_name IS NOT NULL AND referral_name <> '') "
    "OR (referral_contact IS NOT NULL AND referral_contact <> ''))"
)


def _safe(fn: Callable[[], Any], default: Any) -> Any:
    """Run one panel; degrade to `default` on any error (never 500 the dashboard)."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("test-drive dashboard panel failed: %s", exc)
        return default


def _slice(corridor: Optional[str], segment: Optional[str]) -> Tuple[List[str], Dict[str, Any]]:
    clauses: List[str] = []
    params: Dict[str, Any] = {}
    if corridor:
        clauses.append("corridor_id = :corridor")
        params["corridor"] = corridor
    if segment:
        clauses.append("tester_segment = :segment")
        params["segment"] = segment
    return clauses, params


def _where(clauses: List[str], extra: str = "") -> str:
    all_clauses = list(clauses) + ([extra] if extra else [])
    return (" WHERE " + " AND ".join(all_clauses)) if all_clauses else ""


def _scalar(sql: str, params: Dict[str, Any]) -> Any:
    with db.engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def _rows(sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    with db.engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


@router.get("/test-drive/overview")
def test_drive_overview(
    corridor: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    clauses, params = _slice(corridor, segment)

    def count(table: str, extra: str = "", extra_params: Optional[Dict[str, Any]] = None) -> int:
        val = _scalar("SELECT count(*) FROM " + table + _where(clauses, extra), {**params, **(extra_params or {})})
        return int(val or 0)

    def funnel() -> Dict[str, int]:
        return {
            "invited": count("funnel_events", "event_type = :et", {"et": "invite-sent"}),
            "clicked": count("funnel_events", "event_type = :et", {"et": "click"}),
            "provisioned": count("test_sessions"),
            "completed": count("test_sessions", "status = 'completed'"),
            "surveyed": count("survey_responses"),
            "pilot": count("survey_responses", _PILOT_CLAUSE),
            "intro": count("survey_responses", _REFERRAL_PRESENT),
        }

    def scorecard() -> Dict[str, Any]:
        avg_q1 = _scalar("SELECT avg(q1_overall) FROM survey_responses" + _where(clauses), params)
        fit_rows = _rows(
            "SELECT q3_problem_fit AS fit, count(*) AS n FROM survey_responses"
            + _where(clauses, "q3_problem_fit IS NOT NULL")
            + " GROUP BY q3_problem_fit",
            params,
        )
        return {
            "avg_overall": round(float(avg_q1), 2) if avg_q1 is not None else None,
            "problem_fit": {r["fit"]: int(r["n"]) for r in fit_rows},
        }

    def pilot_leads() -> List[Dict[str, Any]]:
        return _rows(
            "SELECT tester_name, tester_email, tester_company_role, tester_sector, pilot_interest, "
            "pilot_note, corridor_id, tester_segment, created_at FROM survey_responses"
            + _where(clauses, _PILOT_CLAUSE)
            + " ORDER BY created_at DESC LIMIT 200",
            params,
        )

    def testimonials() -> List[Dict[str, Any]]:
        return _rows(
            "SELECT testimonial, tester_name, tester_company_role, corridor_id, created_at FROM survey_responses"
            + _where(clauses, _TESTIMONIAL_CLAUSE)
            + " ORDER BY created_at DESC LIMIT 200",
            {**params, "consent": True},
        )

    fn = _safe(funnel, {})
    return {
        "funnel": fn,
        "scorecard": {**_safe(scorecard, {}), "totals": fn},
        "pilot_leads": _safe(pilot_leads, []),
        "testimonials": _safe(testimonials, []),
        "corridor": corridor,
        "segment": segment,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/test-drive/contacts.csv")
def test_drive_contacts_csv(
    corridor: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> StreamingResponse:
    """Consented contact list: pilot leads + consented referrals + consented testimonial authors."""
    clauses, params = _slice(corridor, segment)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["type", "name", "email_or_contact", "company_role", "sector", "corridor", "interest", "note"])

    def s(v: Any) -> str:
        return "" if v is None else str(v)

    pilot = _safe(lambda: _rows(
        "SELECT tester_name, tester_email, tester_company_role, tester_sector, pilot_interest, "
        "pilot_note, corridor_id FROM survey_responses"
        + _where(clauses, _PILOT_CLAUSE) + " ORDER BY created_at DESC", params), [])
    for r in pilot:
        writer.writerow(["pilot", s(r["tester_name"]), s(r["tester_email"]), s(r["tester_company_role"]),
                         s(r["tester_sector"]), s(r["corridor_id"]), s(r["pilot_interest"]), s(r["pilot_note"])])

    referrals = _safe(lambda: _rows(
        "SELECT referral_name, referral_contact, referral_company_role, corridor_id FROM survey_responses"
        + _where(clauses, "referral_consent = :consent AND " + _REFERRAL_PRESENT)
        + " ORDER BY created_at DESC", {**params, "consent": True}), [])
    for r in referrals:
        writer.writerow(["referral", s(r["referral_name"]), s(r["referral_contact"]),
                         s(r["referral_company_role"]), "", s(r["corridor_id"]), "", ""])

    testis = _safe(lambda: _rows(
        "SELECT tester_name, tester_email, tester_company_role, corridor_id, testimonial FROM survey_responses"
        + _where(clauses, _TESTIMONIAL_CLAUSE) + " ORDER BY created_at DESC", {**params, "consent": True}), [])
    for r in testis:
        writer.writerow(["testimonial", s(r["tester_name"]), s(r["tester_email"]), s(r["tester_company_role"]),
                         "", s(r["corridor_id"]), "", s(r["testimonial"])])

    buffer.seek(0)
    filename = f"test_drive_contacts_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
