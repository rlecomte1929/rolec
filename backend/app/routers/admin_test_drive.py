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
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from ..auth_deps import require_admin
from ... import db_config
from ...database import db

router = APIRouter(prefix="/api/admin", tags=["admin-test-drive"])
logger = logging.getLogger(__name__)

_IS_SQLITE = (db_config.DATABASE_URL or "").startswith("sqlite")

# SQL clause fragments (kept as module constants so they never sit inside an f-string
# expression — Python 3.11 forbids backslashes/quotes there).
_PILOT_CLAUSE = "pilot_interest IN ('yes', 'maybe')"
_TESTIMONIAL_CLAUSE = "testimonial IS NOT NULL AND testimonial <> '' AND testimonial_consent = :consent"
_REFERRAL_PRESENT = (
    "((referral_name IS NOT NULL AND referral_name <> '') "
    "OR (referral_contact IS NOT NULL AND referral_contact <> ''))"
)


# TD-M3 (AIQ-1558): ordered mid-journey stages (all already emitted as funnel_events).
# Time-on-stage + drop-off between consecutive stages is derived from these — no new capture.
_TIMING_STAGES = ["start", "hr-handoff", "intake-start", "intake-completed", "roadmap-reached", "vendor-selected"]


def _parse_ts(v: Any) -> Optional[datetime]:
    """Coerce a funnel_events.created_at to datetime (PG returns datetime, SQLite text)."""
    if v is None:
        return None
    if hasattr(v, "timestamp"):
        return v  # already a datetime
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _safe(fn: Callable[[], Any], default: Any) -> Any:
    """Run one panel; degrade to `default` on any error (never 500 the dashboard)."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("test-drive dashboard panel failed: %s", exc)
        return default


def _resolve_campaign(campaign: Optional[str]) -> str:
    """AIQ-1537: the campaign every dashboard panel is scoped to. Defaults to the live
    campaign (RELOPASS_TEST_DRIVE_CAMPAIGN, else 'insead-2026') so the wiped real campaign
    reads zero until real testers arrive — QA/debug campaigns no longer bleed into it."""
    return (campaign or "").strip() or os.getenv("RELOPASS_TEST_DRIVE_CAMPAIGN", "insead-2026")


def _slice(corridor: Optional[str], segment: Optional[str], campaign: str) -> Tuple[List[str], Dict[str, Any]]:
    # AIQ-1537: always scope to ONE campaign. The TD tables (test_sessions, funnel_events,
    # survey_responses) each carry a `campaign` column; without this clause every panel
    # aggregates all campaigns (real + QA + prior debug runs) into one misleading set.
    clauses: List[str] = ["campaign = :campaign"]
    params: Dict[str, Any] = {"campaign": campaign}
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
    campaign: Optional[str] = Query(None),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    campaign_id = _resolve_campaign(campaign)
    clauses, params = _slice(corridor, segment, campaign_id)

    def count(table: str, extra: str = "", extra_params: Optional[Dict[str, Any]] = None) -> int:
        val = _scalar("SELECT count(*) FROM " + table + _where(clauses, extra), {**params, **(extra_params or {})})
        return int(val or 0)

    def stage(event_type: str) -> int:
        # TD-FIX-4 (AIQ-1505): mid-journey drop-off = DISTINCT sessions that reached a
        # stage (a page can re-emit, so raw row counts would over-report).
        val = _scalar(
            "SELECT count(DISTINCT session_id) FROM funnel_events" + _where(clauses, "event_type = :et"),
            {**params, "et": event_type},
        )
        return int(val or 0)

    def invited_total() -> int:
        # TD-FIX-3 (AIQ-1504): invites are recorded as 'invite-sent' rows carrying a
        # metadata `count`, so the denominator is the SUM of those counts (not a row
        # count). A legacy row without a count is worth 1. Summed in Python to stay
        # dialect-agnostic (metadata is jsonb on PG, a JSON string on SQLite).
        rows = _rows(
            "SELECT metadata FROM funnel_events" + _where(clauses, "event_type = :et"),
            {**params, "et": "invite-sent"},
        )
        total = 0
        for r in rows:
            md = r.get("metadata")
            if isinstance(md, str):
                try:
                    md = json.loads(md)
                except (ValueError, TypeError):
                    md = {}
            c = md.get("count") if isinstance(md, dict) else None
            try:
                total += int(c) if c is not None else 1
            except (ValueError, TypeError):
                total += 1
        return total

    def funnel() -> Dict[str, int]:
        return {
            "invited": invited_total(),
            "clicked": count("funnel_events", "event_type = :et", {"et": "click"}),
            "provisioned": count("test_sessions"),
            # TD-FIX-4: intermediate journey stages, so drop-off between provisioned and
            # completed is visible.
            "hr_handoff": stage("hr-handoff"),
            "intake_start": stage("intake-start"),
            "intake_completed": stage("intake-completed"),
            "roadmap_reached": stage("roadmap-reached"),
            "vendor_selected": stage("vendor-selected"),
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

    def completions() -> List[Dict[str, Any]]:
        # TD-12: every surveyed tester (not just pilot leads) — so the dashboard can offer a
        # one-click thank-you mailto per completed response. Only rows that left a contact
        # email are actionable, so scope to those.
        return _rows(
            "SELECT tester_name, tester_email, tester_company_role, tester_sector, "
            "q1_overall, pilot_interest, corridor_id, tester_segment, created_at FROM survey_responses"
            + _where(clauses, "tester_email IS NOT NULL AND tester_email <> ''")
            + " ORDER BY created_at DESC LIMIT 200",
            params,
        )

    def stage_timing() -> List[Dict[str, Any]]:
        # TD-M3 (AIQ-1558): median time-on-stage + per-stage drop-off %, scoped by the same
        # slice (so it's per-corridor + per-segment). Stage names are module constants, not
        # user input, so inlining them in the IN() is safe. Median is computed in Python to
        # stay dialect-agnostic (SQLite has no percentile_cont).
        in_list = ", ".join("'" + s + "'" for s in _TIMING_STAGES)
        rows = _rows(
            "SELECT session_id, event_type, MIN(created_at) AS ts FROM funnel_events"
            + _where(clauses, "event_type IN (" + in_list + ") AND session_id IS NOT NULL")
            + " GROUP BY session_id, event_type",
            params,
        )
        by_session: Dict[str, Dict[str, datetime]] = {}
        for r in rows:
            ts = _parse_ts(r.get("ts"))
            if ts is None:
                continue
            by_session.setdefault(str(r["session_id"]), {})[str(r["event_type"])] = ts
        reached = {st: sum(1 for s in by_session.values() if st in s) for st in _TIMING_STAGES}
        out: List[Dict[str, Any]] = []
        for a, b in zip(_TIMING_STAGES, _TIMING_STAGES[1:]):
            durations = [
                (s[b] - s[a]).total_seconds()
                for s in by_session.values()
                if a in s and b in s and (s[b] - s[a]).total_seconds() >= 0
            ]
            med = _median(durations)
            ra = reached[a]
            out.append({
                "from_stage": a,
                "to_stage": b,
                "reached_from": ra,
                "reached_to": reached[b],
                "drop_off_pct": round((ra - reached[b]) / ra * 100, 1) if ra else None,
                "median_seconds": round(med, 1) if med is not None else None,
            })
        return out

    fn = _safe(funnel, {})
    return {
        "funnel": fn,
        "scorecard": {**_safe(scorecard, {}), "totals": fn},
        "stage_timing": _safe(stage_timing, []),
        "pilot_leads": _safe(pilot_leads, []),
        "completions": _safe(completions, []),
        "testimonials": _safe(testimonials, []),
        "corridor": corridor,
        "segment": segment,
        "campaign": campaign_id,
        "generated_at": datetime.utcnow().isoformat(),
    }


class RecordInvitesRequest(BaseModel):
    """TD-FIX-3 (AIQ-1504): one 'Record invites sent' action. Reuses funnel_events."""
    count: int = Field(..., ge=1, le=100000)
    segment: Optional[str] = Field(None, pattern="^(internal|prospect)$")
    channel: str = Field("other", pattern="^(whatsapp|email|other)$")
    campaign: Optional[str] = Field(None, max_length=64)


@router.post("/test-drive/invites")
def record_invites_sent(
    body: RecordInvitesRequest,
    _admin: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Record a batch of invites sent so the funnel has a denominator (click-through).

    Persists ONE funnel_events row (event_type='invite-sent') carrying count + channel in
    metadata, tagged with campaign and optional tester_segment. The overview's 'Invited'
    tile sums these counts. Admin-gated; reuses funnel_events (no new table)."""
    campaign = (body.campaign or "").strip() or os.getenv("RELOPASS_TEST_DRIVE_CAMPAIGN", "insead-2026")
    row_id = str(uuid.uuid4())
    id_expr = ":id" if _IS_SQLITE else "CAST(:id AS uuid)"
    meta_expr = ":metadata" if _IS_SQLITE else "CAST(:metadata AS jsonb)"
    with db.engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO funnel_events (id, event_type, campaign, tester_segment, metadata) "
                f"VALUES ({id_expr}, 'invite-sent', :campaign, :tester_segment, {meta_expr})"
            ),
            {
                "id": row_id,
                "campaign": campaign,
                "tester_segment": body.segment,
                "metadata": json.dumps({"count": body.count, "channel": body.channel}),
            },
        )
    logger.info(
        "test_drive_invites_recorded count=%s segment=%s channel=%s campaign=%s",
        body.count, body.segment, body.channel, campaign,
    )
    return {"ok": True, "recorded": body.count, "channel": body.channel, "segment": body.segment}


@router.get("/test-drive/contacts.csv")
def test_drive_contacts_csv(
    corridor: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    campaign: Optional[str] = Query(None),
    _admin: Dict[str, Any] = Depends(require_admin),
) -> StreamingResponse:
    """Consented contact list: pilot leads + consented referrals + consented testimonial authors."""
    clauses, params = _slice(corridor, segment, _resolve_campaign(campaign))
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
