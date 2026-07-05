"""Test-Drive self-serve provisioning (AIQ-1420 / TD-2).

POST /api/test-drive/provision — one call mints the two identities a relocation
needs (an HR user + an Employee user), seeds a per-session company and links both
so a corridor case is later creatable, and writes a ``test_sessions`` row that
anchors the campaign funnel.

Security posture — this is a PUBLIC (unauthenticated) surface, so it is defended
in depth:
  * Campaign gate: 404 unless ``RELOPASS_TEST_DRIVE_ENABLED`` is truthy
    (dark-shipped; ramped per environment, exactly like predictions.py).
  * Invite token: 403 unless the body's ``invite_token`` matches
    ``RELOPASS_TEST_DRIVE_INVITE_TOKEN`` (constant-time compare).
  * Rate limit: slowapi per-IP, ``RELOPASS_TEST_DRIVE_RATE_LIMIT``
    (default ``5/minute;60/hour`` — configurable because campaign testers may sit
    behind a single campus NAT).
  * Every account + company is stamped ``is_test=true`` (via the ``@probe.test``
    email domain and the "Test Drive …" company name), so nothing created here
    leaks into admin/production surfaces.

Env vars: RELOPASS_TEST_DRIVE_ENABLED, RELOPASS_TEST_DRIVE_INVITE_TOKEN,
RELOPASS_TEST_DRIVE_CAMPAIGN, RELOPASS_TEST_DRIVE_RATE_LIMIT.

NOTE: the endpoint 404s until the flag is set; enabling it in prod REQUIRES the
TD-1 migration ``20260830000000_test_drive_schema.sql`` to be applied first
(committed-not-applied). Both are gated, out-of-band steps.
"""
# NB: no `from __future__ import annotations` — the slowapi @limiter.limit wrapper
# resolves the `body: ProvisionRequest` forward-ref against its own module globals,
# so the annotation must be a real class object, not a string.
import json
import logging
import os
import re
import secrets
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from ... import db_config
from ...database import db
from ...rate_limit import limiter
from .auth import _dispatch_supabase_sync, _pwd_context

router = APIRouter(prefix="/api/test-drive", tags=["test-drive"])
logger = logging.getLogger(__name__)

# Read once at import — slowapi evaluates the decorator argument at decoration time.
_RATE_LIMIT = os.getenv("RELOPASS_TEST_DRIVE_RATE_LIMIT", "5/minute;60/hour")
_IS_SQLITE = (db_config.DATABASE_URL or "").startswith("sqlite")


def _test_drive_enabled() -> bool:
    return os.getenv("RELOPASS_TEST_DRIVE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _slugify(name: str) -> str:
    """Lowercase alphanumeric slug for usernames/emails; never empty."""
    slug = re.sub(r"[^a-z0-9]", "", (name or "").lower())[:20]
    return slug or "user"


# ── TD-8 (AIQ-1426): funnel instrumentation ───────────────────────────────────
# Free-text event_type is allow-listed so the public recorder can't write arbitrary rows.
_ALLOWED_FUNNEL_EVENTS = {
    "invite-sent", "click", "start", "hr-handoff", "intake-start", "roadmap-reached",
    "vendor-selected", "completed", "surveyed", "intro", "pilot-interested",
}


def _emit_funnel_event(
    *,
    event_type: str,
    session_id: Optional[str] = None,
    campaign: Optional[str] = None,
    corridor_id: Optional[str] = None,
    tester_segment: Optional[str] = None,
    invite_token: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Best-effort INSERT of one funnel_events row (own tx, never raises).

    Used both as a side-effect from provision/survey/complete and as the write path
    for the public POST /event recorder.
    """
    try:
        id_expr = ":id" if _IS_SQLITE else "CAST(:id AS uuid)"
        sid_expr = ":session_id" if _IS_SQLITE else "CAST(:session_id AS uuid)"
        meta_expr = ":metadata" if _IS_SQLITE else "CAST(:metadata AS jsonb)"
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO funnel_events "
                    f"(id, event_type, session_id, campaign, corridor_id, tester_segment, invite_token, metadata) "
                    f"VALUES ({id_expr}, :event_type, {sid_expr}, :campaign, :corridor_id, "
                    f":tester_segment, :invite_token, {meta_expr})"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "event_type": event_type,
                    "session_id": (session_id or None),
                    "campaign": campaign,
                    "corridor_id": corridor_id,
                    "tester_segment": tester_segment,
                    "invite_token": invite_token,
                    "metadata": json.dumps(metadata or {}),
                },
            )
        return True
    except Exception:  # noqa: BLE001 — funnel telemetry must never break the main flow
        logger.warning("funnel event %s failed (suppressed)", event_type)
        return False


class ProvisionRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=40)
    corridor_id: str = Field(..., min_length=1, max_length=64)
    invite_token: str = Field(..., min_length=1)
    tester_segment: str = Field("prospect", pattern="^(internal|prospect)$")
    campaign: Optional[str] = Field(None, max_length=64)


def _make_user(username: str, email: str, password_hash: str, role: str, name: str) -> Optional[str]:
    """Create one legacy `users` row; return its id, or None on collision."""
    uid = str(uuid.uuid4())
    created = db.create_user(
        user_id=uid,
        username=username,
        email=email,
        password_hash=password_hash,
        role=role,
        name=name,
    )
    return uid if created else None


@router.post("/provision")
@limiter.limit(_RATE_LIMIT)
def provision(body: ProvisionRequest, request: Request):
    """Provision a paired HR + Employee test identity for the self-serve flow.

    Returns both credential sets (username + email + plaintext one-time password)
    plus the ``test_sessions`` id. 404 when the campaign is off, 403 on a bad
    invite token.
    """
    # 1) Campaign gate — dark by default.
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    # 2) Invite-token gate — constant-time compare against the campaign secret.
    expected_token = os.getenv("RELOPASS_TEST_DRIVE_INVITE_TOKEN") or ""
    if not expected_token or not secrets.compare_digest(body.invite_token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid or missing invite token")

    first_name = body.first_name.strip()
    slug = _slugify(first_name)
    campaign = (body.campaign or "").strip() or os.getenv("RELOPASS_TEST_DRIVE_CAMPAIGN", "insead-2026")

    # Passwords are independent of the collision retry, so hash once (pbkdf2 is costly).
    hr_password = secrets.token_urlsafe(9)
    emp_password = secrets.token_urlsafe(9)
    hr_hash = _pwd_context.hash(hr_password)
    emp_hash = _pwd_context.hash(emp_password)

    # 3) Create the two accounts, regenerating the suffix on a username/email collision.
    hr_id = emp_id = None
    hr_username = emp_username = hr_email = emp_email = ""
    suffix = ""
    for _ in range(3):
        suffix = secrets.token_hex(2)  # 4 hex chars
        hr_username, emp_username = f"HR-{slug}-{suffix}", f"EMP-{slug}-{suffix}"
        # @probe.test → ensure_profile_record auto-stamps profiles.is_test = true.
        hr_email, emp_email = f"hr-{slug}-{suffix}@probe.test", f"emp-{slug}-{suffix}@probe.test"

        hr_id = _make_user(hr_username, hr_email, hr_hash, "HR", first_name)
        if not hr_id:
            continue
        emp_id = _make_user(emp_username, emp_email, emp_hash, "EMPLOYEE", first_name)
        if not emp_id:
            continue
        break
    if not hr_id or not emp_id:
        raise HTTPException(status_code=503, detail="Could not allocate unique test-drive identities; retry")

    # 4) Seed a per-session company ("Test Drive …" name → companies.is_test auto-set)
    #    and link the HR user so the command-center / assignment dropdowns work.
    company_id = db.find_or_create_company_by_name(f"Test Drive {first_name} {suffix}")

    db.ensure_profile_record(
        user_id=hr_id, email=hr_email, role="HR", full_name=first_name, company_id=company_id,
    )
    if company_id:
        db.set_profile_company(hr_id, company_id)
        db.ensure_hr_user_for_profile(hr_id, company_id)

    db.ensure_profile_record(
        user_id=emp_id, email=emp_email, role="EMPLOYEE", full_name=first_name, company_id=company_id,
    )
    if company_id:
        db.set_profile_company(emp_id, company_id)
        db.ensure_employee_for_profile(emp_id, company_id)

    # 5) Mirror both to Supabase Auth (fire-and-forget; never blocks or raises).
    _dispatch_supabase_sync(hr_email, hr_password, relopass_user_id=hr_id, full_name=first_name)
    _dispatch_supabase_sync(emp_email, emp_password, relopass_user_id=emp_id, full_name=first_name)

    # 6) Anchor the funnel: one test_sessions row. hr_user_id/emp_user_id (FK →
    #    auth.users) are left NULL — the Supabase-Auth uuid differs from our
    #    ReloPass uuid and is created async; the schema stores the usernames instead.
    session_id = str(uuid.uuid4())
    id_expr = ":id" if _IS_SQLITE else "CAST(:id AS uuid)"
    with db.engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO test_sessions "
                f"(id, campaign, corridor_id, tester_segment, first_name_label, hr_username, emp_username, status) "
                f"VALUES ({id_expr}, :campaign, :corridor_id, :tester_segment, :first_name_label, "
                f":hr_username, :emp_username, 'started')"
            ),
            {
                "id": session_id,
                "campaign": campaign,
                "corridor_id": body.corridor_id.strip(),
                "tester_segment": body.tester_segment,
                "first_name_label": first_name,
                "hr_username": hr_username,
                "emp_username": emp_username,
            },
        )

    # TD-8: funnel — a provisioned session is the "start" of the run.
    _emit_funnel_event(
        event_type="start", session_id=session_id, campaign=campaign,
        corridor_id=body.corridor_id.strip(), tester_segment=body.tester_segment,
    )

    logger.info(
        "test_drive_provision session=%s corridor=%s segment=%s hr=%s emp=%s",
        session_id, body.corridor_id, body.tester_segment, hr_username, emp_username,
    )
    return {
        "session_id": session_id,
        "corridor_id": body.corridor_id.strip(),
        "campaign": campaign,
        "hr": {"username": hr_username, "email": hr_email, "password": hr_password, "role": "HR"},
        "employee": {"username": emp_username, "email": emp_email, "password": emp_password, "role": "EMPLOYEE"},
    }


# ── TD-5 (AIQ-1423): completion survey ────────────────────────────────────────
# One wide survey_responses row per submission (table + RLS from TD-1). Public and
# campaign-gated like /provision, but no invite token (it's a post-test submission).
# tester_name/email + testimonial/referral are the only real PII captured — each
# carries its own consent flag and is stored only in the admin-read RLS table (never
# sent to an LLM, so no masking needed). Nothing here is logged.
_SURVEY_COLUMNS = (
    "session_id campaign corridor_id tester_segment tester_name tester_email "
    "tester_company_role tester_sector q1_overall q2_friction q3_problem_fit q3_why "
    "q4_change testimonial testimonial_consent pilot_interest pilot_note referral_name "
    "referral_company_role referral_contact referral_consent"
).split()


class SurveyRequest(BaseModel):
    session_id: Optional[str] = Field(None, max_length=64)
    campaign: Optional[str] = Field(None, max_length=64)
    corridor_id: Optional[str] = Field(None, max_length=64)
    tester_segment: Optional[str] = Field(None, pattern="^(internal|prospect)$")
    # Lead-in identity (the only real PII; consent-gated below for reuse).
    tester_name: Optional[str] = Field(None, max_length=200)
    tester_email: Optional[str] = Field(None, max_length=200)
    tester_company_role: Optional[str] = Field(None, max_length=200)
    tester_sector: Optional[str] = Field(None, max_length=200)
    # Q1–Q4
    q1_overall: Optional[int] = Field(None, ge=1, le=5)
    q2_friction: Optional[str] = None
    q3_problem_fit: Optional[str] = Field(None, pattern="^(yes|somewhat|no)$")
    q3_why: Optional[str] = None
    q4_change: Optional[str] = None
    # Q5 testimonial (+ quote consent), Q6 pilot interest, Q7 referral (+ consent)
    testimonial: Optional[str] = None
    testimonial_consent: bool = False
    pilot_interest: Optional[str] = Field(None, pattern="^(yes|maybe|no)$")
    pilot_note: Optional[str] = None
    referral_name: Optional[str] = Field(None, max_length=200)
    referral_company_role: Optional[str] = Field(None, max_length=200)
    referral_contact: Optional[str] = Field(None, max_length=300)
    referral_consent: bool = False


@router.post("/survey")
@limiter.limit(_RATE_LIMIT)
def survey(body: SurveyRequest, request: Request):
    """Persist one completion-survey submission into survey_responses.

    404 when the campaign is off. Returns {ok, response_id}. All fields optional
    (only three questions ask for typing, all optional).
    """
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    campaign = (body.campaign or "").strip() or os.getenv("RELOPASS_TEST_DRIVE_CAMPAIGN", "insead-2026")
    response_id = str(uuid.uuid4())
    id_expr = ":id" if _IS_SQLITE else "CAST(:id AS uuid)"
    session_expr = ":session_id" if _IS_SQLITE else "CAST(:session_id AS uuid)"

    params = {c: getattr(body, c) for c in _SURVEY_COLUMNS}
    params["id"] = response_id
    params["campaign"] = campaign
    params["session_id"] = (body.session_id or "").strip() or None

    col_sql = ", ".join(["id", "session_id"] + [c for c in _SURVEY_COLUMNS if c != "session_id"])
    val_sql = ", ".join(
        [id_expr, session_expr] + [f":{c}" for c in _SURVEY_COLUMNS if c != "session_id"]
    )
    with db.engine.begin() as conn:
        conn.execute(text(f"INSERT INTO survey_responses ({col_sql}) VALUES ({val_sql})"), params)

    # TD-8: funnel — this session reached the survey.
    _emit_funnel_event(
        event_type="surveyed", session_id=params["session_id"], campaign=campaign,
        corridor_id=body.corridor_id, tester_segment=body.tester_segment,
    )
    # TD-7: turn survey answers into pipeline (best-effort; never breaks the survey write).
    _process_survey_pipeline(body, campaign)
    # TODO [TD-6]: on-submit email fan-out — notify Romain + thank tester (🔴 Red; separate task).

    logger.info(
        "test_drive_survey response=%s session=%s campaign=%s pilot=%s",
        response_id, params["session_id"], campaign, body.pilot_interest,
    )
    return {"ok": True, "response_id": response_id}


# ── TD-7 (AIQ-1425): survey answers → pipeline ────────────────────────────────
def _process_survey_pipeline(body: SurveyRequest, campaign: str) -> None:
    """Q7 intro → a prospect_candidates row; Q6 pilot Yes/Maybe → a warm-lead funnel event.

    Best-effort — never raises into the survey write. Design note: prospect_candidates
    is company-centric (company_name NOT NULL) and its enrichment path sends
    raw_input_json['notes'] to an LLM unmasked, so referral PII is stashed under
    DEDICATED keys (never 'notes') and enrichment is not queued.
    """
    # Q6 — "warm pilot lead" is a funnel event keyed on the tester's session (the
    # purpose-built flag; the tester is a survey_responses/test_sessions row, not a company).
    if body.pilot_interest in ("yes", "maybe"):
        _emit_funnel_event(
            event_type="pilot-interested", session_id=(body.session_id or None), campaign=campaign,
            corridor_id=body.corridor_id, tester_segment=body.tester_segment,
            metadata={"pilot_interest": body.pilot_interest},
        )

    # Q7 — a referral becomes a prospect_candidates row.
    has_referral = bool((body.referral_name or "").strip() or (body.referral_contact or "").strip())
    if not has_referral:
        return

    _emit_funnel_event(
        event_type="intro", session_id=(body.session_id or None), campaign=campaign,
        corridor_id=body.corridor_id, tester_segment=body.tester_segment,
        metadata={"has_contact": bool((body.referral_contact or "").strip())},
    )
    try:
        from ..db import SessionLocal
        from ..models import ProspectCandidate

        referred_by = (body.tester_name or body.tester_email or "").strip() or None
        company_name = (body.referral_company_role or "").strip() or "Test-drive referral"
        raw = json.dumps(
            {
                "source": "test_drive_referral",
                "referred_by": referred_by,  # NOT 'notes' — 'notes' is fed to the enrichment LLM.
                "referral_name": (body.referral_name or "").strip() or None,
                "referral_company_role": (body.referral_company_role or "").strip() or None,
                "referral_contact": (body.referral_contact or "").strip() or None,
                "corridor_id": body.corridor_id,
                "campaign": campaign,
            },
            ensure_ascii=False,
        )
        with SessionLocal() as s:
            s.add(
                ProspectCandidate(
                    id=str(uuid.uuid4()),
                    company_name=company_name[:255],
                    raw_input_json=raw,
                    status="maybe",  # a valid triage status; enrichment is NOT queued.
                    web_search_used=False,
                )
            )
            s.commit()
    except Exception:  # noqa: BLE001
        logger.warning("test_drive referral → prospect_candidates failed (suppressed)")


# ── TD-8 (AIQ-1426): public funnel-event recorder ─────────────────────────────
class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(..., max_length=40)
    session_id: Optional[str] = Field(None, max_length=64)
    campaign: Optional[str] = Field(None, max_length=64)
    corridor_id: Optional[str] = Field(None, max_length=64)
    tester_segment: Optional[str] = Field(None, pattern="^(internal|prospect)$")
    invite_token: Optional[str] = Field(None, max_length=200)
    metadata: Optional[Dict[str, Any]] = None


@router.post("/event")
@limiter.limit(_RATE_LIMIT)
def record_event(body: EventRequest, request: Request):
    """Record one funnel event (invite/click/stage). 404 when the campaign is off,
    400 on an unknown event_type (allow-listed). Public + rate-limited."""
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    if body.event_type not in _ALLOWED_FUNNEL_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event_type")
    campaign = (body.campaign or "").strip() or os.getenv("RELOPASS_TEST_DRIVE_CAMPAIGN", "insead-2026")
    # Only scalar metadata — no free-text/PII from the public web.
    meta: Dict[str, Any] = {}
    if body.metadata:
        meta = {
            k: v for k, v in body.metadata.items()
            if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 200
        }
    _emit_funnel_event(
        event_type=body.event_type, session_id=(body.session_id or None), campaign=campaign,
        corridor_id=body.corridor_id, tester_segment=body.tester_segment,
        invite_token=body.invite_token, metadata=meta,
    )
    return {"ok": True}


# ── TD-4 (AIQ-1422): completion detection ─────────────────────────────────────
def _check_completion_reached(hr_username: Optional[str]) -> "tuple[bool, Optional[str]]":
    """SOFT guard: has the tester's seeded case reached a generated roadmap AND a
    vendor selected with an estimated cost? Returns (reached, nudge). Never raises.
    TD-2 seeds no case, so the common path is (False, nudge)."""
    nudge = (
        "Finish the case first — generate the roadmap and select a vendor with an "
        "estimated cost — then you're really done. (You can mark complete anyway.)"
    )
    try:
        if not hr_username:
            return False, nudge
        user = db.get_user_by_username(hr_username)
        if not user:
            return False, nudge
        company_id = db.get_hr_company_id(str(user.get("id")))
        if not company_id:
            return False, nudge
        true_lit = "1" if _IS_SQLITE else "true"
        with db.engine.connect() as conn:
            case_row = conn.execute(
                text("SELECT id FROM relocation_cases WHERE company_id = :cid ORDER BY created_at DESC LIMIT 1"),
                {"cid": company_id},
            ).mappings().first()
            if not case_row:
                return False, nudge
            case_id = str(case_row.get("id"))
            vendor_row = conn.execute(
                text(
                    "SELECT 1 FROM case_services "
                    "WHERE (case_id = :cid OR canonical_case_id = :cid) "
                    f"AND selected = {true_lit} AND estimated_cost IS NOT NULL LIMIT 1"
                ),
                {"cid": case_id},
            ).first()
        vendor_ok = vendor_row is not None
        case = db.get_relocation_case(case_id) or {}
        from ..services.roadmap_builder import derive_roadmap
        roadmap = derive_roadmap(case) if case else {}
        roadmap_ok = any(bool(v) for v in roadmap.values()) if isinstance(roadmap, dict) else bool(roadmap)
        reached = bool(roadmap_ok and vendor_ok)
        return reached, (None if reached else nudge)
    except Exception:  # noqa: BLE001
        logger.warning("test_drive completion check failed (suppressed)")
        return False, nudge


class CompleteRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)


@router.post("/complete")
@limiter.limit(_RATE_LIMIT)
def complete(body: CompleteRequest, request: Request):
    """Mark a test session complete (self-declared; primary trigger). Soft-checks the
    seeded case state for an honest `reached` flag + nudge, but never hard-blocks.
    404 when the campaign is off or the session is unknown."""
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    sid_expr = ":sid" if _IS_SQLITE else "CAST(:sid AS uuid)"
    with db.engine.begin() as conn:
        row = conn.execute(
            text(
                f"SELECT hr_username, campaign, corridor_id, tester_segment "
                f"FROM test_sessions WHERE id = {sid_expr}"
            ),
            {"sid": body.session_id},
        ).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        reached, nudge = _check_completion_reached(row.get("hr_username"))
        conn.execute(
            text(f"UPDATE test_sessions SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id = {sid_expr}"),
            {"sid": body.session_id},
        )
    _emit_funnel_event(
        event_type="completed", session_id=body.session_id, campaign=row.get("campaign"),
        corridor_id=row.get("corridor_id"), tester_segment=row.get("tester_segment"),
        metadata={"reached": reached},
    )
    logger.info("test_drive_complete session=%s reached=%s", body.session_id, reached)
    return {"ok": True, "reached": reached, "nudge": nudge}
