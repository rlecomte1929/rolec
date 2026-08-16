"""Test-Drive self-serve provisioning (AIQ-1420 / TD-2).

POST /api/test-drive/provision — one call mints the two identities a relocation
needs (an HR user + an Employee user), seeds a per-session company and links both
so a corridor case is later creatable, and writes a ``test_sessions`` row that
anchors the campaign funnel.

Security posture — this is a PUBLIC (unauthenticated) surface. Provisioning is
OPEN BY DESIGN (a marketing test-drive anyone with the link can start); abuse is
*bounded*, not gated (AIQ-1592, Option A):
  * Campaign gate: 404 unless ``RELOPASS_TEST_DRIVE_ENABLED`` is truthy
    (dark-shipped; ramped per environment, exactly like predictions.py).
  * Invite token: OPTIONAL. A missing token is allowed — public self-serve. If
    ``RELOPASS_TEST_DRIVE_INVITE_TOKEN`` is configured AND the caller supplies a
    token, it must match (constant-time): a dormant lever to reject a specific or
    leaked link, NOT a hard gate. (Left unset in prod, so the check is inert.)
    See the ``provision()`` docstring + ``test_test_drive_provision.py``.
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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from ... import db_config
from ...database import db
from ...db.test_data_filter import looks_like_test_company
from ...rate_limit import limiter
from ..services.test_drive_corridor import LOCKED_CORRIDORS, TEST_DRIVE_CORRIDOR_ROUTES
from .auth import _dispatch_supabase_sync, _pwd_context

router = APIRouter(prefix="/api/test-drive", tags=["test-drive"])
logger = logging.getLogger(__name__)

# Read once at import — slowapi evaluates the decorator argument at decoration time.
_RATE_LIMIT = os.getenv("RELOPASS_TEST_DRIVE_RATE_LIMIT", "5/minute;60/hour")
_IS_SQLITE = (db_config.DATABASE_URL or "").startswith("sqlite")

# TD-FIX-7 (AIQ-1510): the locked set is defined once, alongside the concrete route each
# id pins a case to, so the provisioner's whitelist and the corridor guard cannot drift.
_LOCKED_CORRIDORS = LOCKED_CORRIDORS
_CORRIDOR_WEIGHTS = {"FR_NO": 0.30, "IN_DE": 0.30, "GB_US": 0.10, "NL_SG": 0.10, "ES_AE": 0.10, "ES_IE": 0.10}


def _test_drive_enabled() -> bool:
    return os.getenv("RELOPASS_TEST_DRIVE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _slugify(name: str) -> str:
    """Lowercase alphanumeric slug for usernames/emails; never empty."""
    slug = re.sub(r"[^a-z0-9]", "", (name or "").lower())[:20]
    return slug or "user"


# ── TD-8 (AIQ-1426): funnel instrumentation ───────────────────────────────────
# Free-text event_type is allow-listed so the public recorder can't write arbitrary rows.
_ALLOWED_FUNNEL_EVENTS = {
    "invite-sent", "click", "start", "hr-handoff", "intake-start", "intake-completed",
    "roadmap-reached", "vendor-selected", "completed", "surveyed", "intro", "pilot-interested",
    # TD-M1 (AIQ-1557): friction captured when a tester stalls or leaves without advancing.
    # metadata = {stage, reason, text} (all short scalar strings — filtered by record_event).
    "friction",
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


def _assign_corridor(campaign: str) -> str:
    """Pick the corridor furthest below its target share (from test_sessions counts)."""
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT corridor_id, COUNT(*) AS cnt FROM test_sessions "
                    "WHERE campaign = :campaign GROUP BY corridor_id"
                ),
                {"campaign": campaign},
            ).fetchall()
    except Exception:
        return _LOCKED_CORRIDORS[0]

    counts = {c: 0 for c in _LOCKED_CORRIDORS}
    for row in rows:
        if row[0] in counts:
            counts[row[0]] = int(row[1])

    total = sum(counts.values())
    if total == 0:
        return _LOCKED_CORRIDORS[0]

    best, best_deficit = _LOCKED_CORRIDORS[0], float("-inf")
    for cid in _LOCKED_CORRIDORS:
        deficit = _CORRIDOR_WEIGHTS[cid] - counts[cid] / total
        if deficit > best_deficit:
            best_deficit, best = deficit, cid
    return best


class ProvisionRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=40)
    # TD-M0 (AIQ-1556, corrected): the tester's REAL contact, captured at the start so a
    # tester who CONSENTS is reachable even if they drop out. OPTIONAL by design — the
    # relocation data is synthetic, so nothing here forces real PII; leaving it blank is a
    # valid choice and the full test still runs (the logins render on screen; nothing is
    # ever emailed to the tester). This is real PII — stored only on the admin-read
    # test_sessions row, never logged, never sent to an LLM. tester_name reuses first_name.
    tester_email: Optional[str] = Field(None, max_length=254)
    corridor_id: Optional[str] = Field(None, max_length=64)

    @field_validator("tester_email")
    @classmethod
    def _validate_tester_email(cls, v: Optional[str]) -> Optional[str]:
        # Same contract the survey already uses (AIQ-1543): omitted/blank is fine, but a
        # non-empty value must look like an address. Normalising blank -> None here keeps
        # the INSERT storing a true NULL rather than an empty string, which is what the
        # follow-up queue filters on.
        if v is None:
            return v
        s = v.strip()
        if not s:
            return None
        if not _EMAIL_RE.match(s):
            raise ValueError("Enter a valid email address.")
        return s
    invite_token: Optional[str] = Field(None, max_length=200)
    # TD-FIX-2 (AIQ-1503): single-link model can't tag the segment at provision, so
    # default to NULL (not 'prospect') — the survey one-tap is the source of truth.
    # A silent 'prospect' default made the admin 'Internal' filter always empty.
    tester_segment: Optional[str] = Field(None, pattern="^(internal|prospect)$")
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


def _seed_default_published_policy(company_id: str, created_by: Optional[str]) -> None:
    """[AIQ-1621] Publish a default benefits policy for a freshly provisioned test-drive
    company, so the employee benefit-comparison / over-cap flow is active without the tester
    having to build one.

    `ensure_draft` auto-seeds the canonical default benefit matrix when the company has no
    published baseline; `publish_draft` flips it to `status='published'`, which is exactly
    what `GET /api/hr/policy-config/published` reads. Test-drive-only by construction — this
    runs only inside `provision()`, which only ever creates `is_test` "Test Drive …"
    companies; real accounts never reach it. Best-effort: a seed failure must never break
    provisioning.
    """
    try:
        from ..services.policy_config_matrix_service import PolicyConfigMatrixService

        svc = PolicyConfigMatrixService(db)
        svc.ensure_draft(company_id, created_by=created_by)
        svc.publish_draft(company_id, policy_version_id=None, created_by=created_by)
        logger.info("test-drive: seeded published default policy for company %s", company_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "test-drive: default policy seed failed for company %s", company_id, exc_info=True
        )


# [AIQ-1651] Seed one CVS row per catalog item that serves the destination.
#
# Originally this INNER JOINed suppliers + supplier_service_capabilities, which silently
# required every catalog item to carry a `supplier_id` pointing at an approved supplier.
# Measured 2026-08-16: all 29 active Ireland catalog rows have `supplier_id IS NULL`, so the
# join dropped every one of them and the seed produced exactly 3 rows — SIRVA, Santa Fe and
# Déménagements Delahaye, whose capability is `coverage_scope_type='global'` and therefore
# matches *any* destination. That looked like a hardcoded three-mover default; it was the
# join. A newly catalogued destination vendor could never become selectable.
#
# Both sources now qualify (LEFT JOIN + an OR):
#   - a catalog row whose own `country` IS the destination, linked to a supplier or not, and
#   - a globally-covering approved supplier's item, which is what kept the 3 movers working.
#
# The supplier registry stays the *vetting* signal, not the *existence* signal:
# `employee_recommendations_filter` remains the security control that keeps unvetted suppliers
# out of what an employee sees. This only populates the curation HR then decides on.
#
# destination_city is left NULL (matches every city); idempotent via NOT EXISTS (the NULL city
# defeats the unique index).
_COMPLIANCE_CATEGORIES = ("legal_admin", "tax_finance")

_SEED_VENDOR_SELECTIONS_SQL = """
INSERT INTO company_vendor_selections
    (company_id, category, master_item_id, selected, display_order, country, created_by_user_id)
SELECT :company_id, sci.category, sci.id,
       -- Compliance-critical categories are never auto-approved on an unverified vendor: a
       -- solicitor or tax adviser we have not accreditation-checked must be HR's explicit
       -- decision, not a seed's. Other categories keep the pre-existing selected=true.
       CASE WHEN sci.category IN ('legal_admin', 'tax_finance')
            THEN COALESCE((sci.attributes_json ->> 'verified')::boolean, false)
            ELSE true
       END,
       row_number() OVER (PARTITION BY sci.category ORDER BY sci.name) - 1,
       :dest_country, :created_by
FROM service_catalog_items sci
LEFT JOIN suppliers s
       ON s.id = sci.supplier_id
      AND s.status = 'active'
LEFT JOIN supplier_service_capabilities ssc
       ON ssc.supplier_id = sci.supplier_id
      AND ssc.service_category = sci.category
      AND ssc.platform_vetting_status = 'approved'
      AND (ssc.coverage_scope_type = 'global' OR ssc.country_code = :dest_country)
WHERE sci.active = true
  AND (
        sci.country = :dest_country
     OR (s.id IS NOT NULL AND ssc.supplier_id IS NOT NULL)
      )
  AND NOT EXISTS (
      SELECT 1 FROM company_vendor_selections cvs
      WHERE cvs.company_id = :company_id AND cvs.master_item_id = sci.id
  )
"""


def _seed_default_vendor_selections(
    company_id: str, dest_country: Optional[str], created_by: Optional[str],
    corridor: Optional[str] = None,
) -> None:
    """[AIQ-1651] Seed ``company_vendor_selections`` for a freshly provisioned test-drive company so
    an employee reaching Services → Recommendations sees a selectable supplier shortlist instead of
    an empty "Movers (0)" category with the "HR is finalizing providers" banner.

    Mirrors ``_seed_default_published_policy``: additive, is_test-only (only ``provision()`` calls it),
    best-effort — a seed failure must never break provisioning. BUT loudly logged: a silent
    exception swallow on this codepath has caused a P0 before, so a failure emits a structured ERROR
    with the full stack (never a silent pass).

    [AIQ-1652] "Loud" also covers the ZERO-rows case: a seed that inserts 0 selections leaves the
    tester with an empty marketplace — the exact symptom this exists to prevent — so it is logged at
    ERROR (not a quiet INFO), naming the company, corridor and destination, so an empty marketplace
    is visible in the logs before it shows up in a tester's survey. (Only ``provision()`` calls this,
    and every locked corridor has approved suppliers, so in practice this stays green.)

    Writes one ``selected=true`` row per approved supplier serving the corridor's destination country
    (see ``_SEED_VENDOR_SELECTIONS_SQL``). It does NOT touch the recommendations filter — the filter
    is the security control that keeps unvetted suppliers out; this only populates the curation it
    reads. Runs via the service-role ``db.engine`` so the HR-only CVS RLS insert policy is bypassed,
    exactly like the other seeds.
    """
    if not dest_country:
        logger.warning(
            "test-drive: no destination country for company %s — skipping vendor-selection seed",
            company_id,
        )
        return
    try:
        with db.engine.begin() as conn:
            result = conn.execute(
                text(_SEED_VENDOR_SELECTIONS_SQL),
                {"company_id": company_id, "dest_country": dest_country, "created_by": created_by},
            )
        seeded = getattr(result, "rowcount", None)
        if seeded == 0:
            # 0 selections → the tester sees an empty marketplace. Surface it LOUDLY + structured
            # (never a quiet INFO): a corridor whose destination has no approved suppliers with a
            # catalog master would otherwise fail silently and be reported as a product verdict.
            logger.error(
                "test-drive: vendor-selection seed produced 0 selections for company %s "
                "(corridor %s, destination %s) — tester will see an EMPTY marketplace; check "
                "approved supplier coverage for this destination",
                company_id, corridor, dest_country,
            )
        else:
            logger.info(
                "test-drive: seeded %s vendor selection(s) for company %s (corridor %s, destination %s)",
                seeded, company_id, corridor, dest_country,
            )
    except Exception:  # noqa: BLE001 — best-effort, but NEVER silent (see docstring)
        logger.error(
            "test-drive: vendor-selection seed FAILED for company %s (corridor %s, destination %s)",
            company_id, corridor, dest_country, exc_info=True,
        )


def _mint_test_drive_identities(
    body: ProvisionRequest,
    first_name: str,
    slug: str,
    campaign: str,
    resolved_corridor: str,
) -> Dict[str, Any]:
    """Shared credential-minting core for ``/provision`` and ``/provision-staged``.

    Creates the paired HR + Employee identities, a per-session ``is_test`` company,
    seeds the published default policy + vendor selections, mirrors both to Supabase
    Auth, writes the ``test_sessions`` anchor row and emits the ``start`` funnel event.

    Returns the full session context: the public credential sets PLUS the internal
    ids (hr_id / emp_id / company_id) the staged provisioner needs to drive the real
    HR + employee flow. Callers own the campaign gate and campaign/corridor resolution
    (they differ between the public self-serve path and the QA staged path).
    """
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
    company_name = f"Test Drive {first_name} {suffix}"
    company_id = db.find_or_create_company_by_name(company_name)

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

    # 4b) [AIQ-1621] Seed a PUBLISHED default benefits policy for this test-drive company so
    #     the employee benefit-comparison / over-cap path is live without the tester building
    #     one. Best-effort — never breaks provisioning.
    if company_id:
        _seed_default_published_policy(company_id, hr_id)

    # 4c) [AIQ-1651] Seed vendor selections (company_vendor_selections) for the corridor's
    #     destination country so Services → Recommendations shows a selectable supplier shortlist
    #     instead of an empty "Movers (0)". Best-effort — never breaks provisioning.
    if company_id:
        _dest_country = TEST_DRIVE_CORRIDOR_ROUTES.get(resolved_corridor, {}).get("host_country")
        _seed_default_vendor_selections(company_id, _dest_country, hr_id, corridor=resolved_corridor)

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
                f"(id, campaign, corridor_id, tester_segment, first_name_label, "
                f"tester_name, tester_email, hr_username, emp_username, status) "
                f"VALUES ({id_expr}, :campaign, :corridor_id, :tester_segment, :first_name_label, "
                f":tester_name, :tester_email, :hr_username, :emp_username, 'started')"
            ),
            {
                "id": session_id,
                "campaign": campaign,
                "corridor_id": resolved_corridor,
                "tester_segment": body.tester_segment,
                "first_name_label": first_name,
                # TD-M0: tester_name reuses the real first name; tester_email is the new field.
                "tester_name": first_name,
                # Already stripped and blank-normalised to None by the validator, so this
                # binds a true NULL when the tester declined to leave contact details.
                "tester_email": body.tester_email,
                "hr_username": hr_username,
                "emp_username": emp_username,
            },
        )

    # TD-8: funnel — a provisioned session is the "start" of the run.
    _emit_funnel_event(
        event_type="start", session_id=session_id, campaign=campaign,
        corridor_id=resolved_corridor, tester_segment=body.tester_segment,
    )

    logger.info(
        "test_drive_provision session=%s corridor=%s segment=%s hr=%s emp=%s",
        session_id, resolved_corridor, body.tester_segment, hr_username, emp_username,
    )
    return {
        "session_id": session_id,
        "corridor_id": resolved_corridor,
        "campaign": campaign,
        "hr": {"username": hr_username, "email": hr_email, "password": hr_password, "role": "HR"},
        "employee": {"username": emp_username, "email": emp_email, "password": emp_password, "role": "EMPLOYEE"},
        # Internal context for the staged provisioner (NOT returned to the public client).
        "hr_id": hr_id,
        "emp_id": emp_id,
        "company_id": company_id,
        "company_name": company_name,
        "hr_username": hr_username,
        "emp_username": emp_username,
        "hr_email": hr_email,
        "emp_email": emp_email,
        "first_name": first_name,
    }


@router.post("/provision")
@limiter.limit(_RATE_LIMIT)
def provision(body: ProvisionRequest, request: Request):
    """Provision a paired HR + Employee test identity for the self-serve flow.

    Returns both credential sets (username + email + plaintext one-time password)
    plus the ``test_sessions`` id. 404 when the campaign is off; 403 only when a
    token is supplied that doesn't match the configured campaign secret (a missing
    token is allowed — public self-serve).
    """
    # 1) Campaign gate — dark by default.
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    # 2) Invite token is now optional (public self-serve). If the campaign has a token
    #    configured AND the caller supplies one, it must still match — keeps existing
    #    invite links meaningful and rejects a wrong/stale token. A missing token is OK.
    expected_token = os.getenv("RELOPASS_TEST_DRIVE_INVITE_TOKEN") or ""
    supplied_token = (body.invite_token or "").strip()
    if supplied_token and expected_token and not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid or missing invite token")

    first_name = body.first_name.strip()
    slug = _slugify(first_name)
    # [campaign attribution] Absent campaign → 'unattributed', NEVER the live 'insead-2026' cohort:
    # silently defaulting there contaminated the cohort's headline metrics and forced three manual
    # purges. Only an explicit ?campaign= attributes a session (the real cohort link passes it).
    # Mirrors the AIQ-1639 survey fix; test_sessions.campaign is NOT NULL so we use an explicit
    # sentinel rather than the survey's NULL.
    campaign = (body.campaign or "").strip() or "unattributed"
    # Whitelist the corridor: honour an explicit valid one, otherwise auto-assign. This
    # blocks free-text corridor_id injection now that the endpoint is public.
    requested_corridor = (body.corridor_id or "").strip()
    resolved_corridor = requested_corridor if requested_corridor in _LOCKED_CORRIDORS else _assign_corridor(campaign)

    ctx = _mint_test_drive_identities(body, first_name, slug, campaign, resolved_corridor)
    return {
        "session_id": ctx["session_id"],
        "corridor_id": ctx["corridor_id"],
        "campaign": ctx["campaign"],
        "hr": ctx["hr"],
        "employee": ctx["employee"],
    }


# ── Staged provisioning (P0, QA-only) ─────────────────────────────────────────
# The full cohort path (provision → HR case → assign → employee sign-in → Services →
# recommendations → shortlist → Request quotes) costs ~40-45 browser actions against a
# ~50 ceiling, so QA could never reach the RFQ-submit step. This fixture returns a
# session already advanced to a named stage — by driving the SAME handlers an ordinary
# session calls (no direct row inserts), so a seeded session and a hand-walked one
# produce equivalent DB rows.
_STAGE_ORDER = ("credentials", "case_created", "intake_complete", "roadmap_ready", "shortlist_ready")


class ProvisionStagedRequest(ProvisionRequest):
    # QA-only: how far to drive the session before returning. Cumulative — each stage
    # runs every earlier one. Defaults to the priority `shortlist_ready` (the tester
    # signs in and can click "Request quotes" in under 5 actions).
    stage: Optional[str] = Field("shortlist_ready", max_length=32)

    @field_validator("stage")
    @classmethod
    def _validate_stage(cls, v: Optional[str]) -> str:
        if v is None:
            return "shortlist_ready"
        s = v.strip()
        if s not in _STAGE_ORDER:
            raise ValueError(f"stage must be one of {list(_STAGE_ORDER)}")
        return s


def _staged_intake_draft(corridor: str, emp_email: str, first_name: str) -> Dict[str, Any]:
    """A complete CaseDraftDTO payload that clears submit_assignment's ≥90% gate
    (all six step-1 basics present → `missing_intake_basics` empty). Origin/destination
    mirror the locked corridor — patch_case also overrides them server-side via
    resolve_test_drive_route, so they are consistent either way."""
    route = TEST_DRIVE_CORRIDOR_ROUTES.get(corridor, TEST_DRIVE_CORRIDOR_ROUTES[_LOCKED_CORRIDORS[0]])
    return {
        "relocationBasics": {
            "originCountry": route["home_country"], "originCity": route["home_city"],
            "destCountry": route["host_country"], "destCity": route["host_city"],
            "purpose": "work", "targetMoveDate": "2026-12-01",
            "durationMonths": 24, "hasDependents": False,
        },
        "employeeProfile": {
            "fullName": first_name or "Test Drive Tester", "nationality": route["home_country"],
            "passportCountry": route["home_country"], "passportExpiry": "2030-01-01",
            "residenceCountry": route["home_country"], "email": emp_email,
        },
        "familyMembers": {"maritalStatus": "single", "children": []},
        "assignmentContext": {
            "employerName": "Test Drive Employer", "employerCountry": route["host_country"],
            "workLocation": route["host_city"], "contractStartDate": "2026-12-15",
            "contractType": "permanent", "salaryBand": "L4", "jobTitle": "Engineer",
            "seniorityBand": "senior",
        },
        "services": ["housing", "movers", "schools"],
    }


def _wait_for_roadmap(case_id: str, timeout_s: float = 45.0, interval_s: float = 2.0) -> int:
    """Block until the async plan build (enqueued by submit_assignment) has written
    case_milestones, so a tester signing in lands on a populated roadmap / a reachable
    Services page. The deterministic milestone seed lands in ~8s (the AI enrich replaces
    it later, in the background), so this typically returns well under the timeout.
    Returns the milestone count (0 if it never materialised — logged, non-fatal)."""
    import time as _time

    deadline = _time.time() + timeout_s
    while _time.time() < deadline:
        try:
            milestones = db.list_case_milestones(case_id)
        except Exception:  # noqa: BLE001 — a transient read failure just means "poll again"
            milestones = None
        if milestones:
            return len(milestones)
        _time.sleep(interval_s)
    logger.error(
        "test-drive staged: roadmap did not materialise for case %s within %ss — the "
        "Services page may still be building when the tester signs in",
        case_id, timeout_s,
    )
    return 0


def _build_shortlist_state(case_id: str, emp_user: Dict[str, Any], corridor: str) -> Dict[str, Any]:
    """Run the REAL recommendations batch for the working city-scoped categories
    (movers + schools — living_areas/housing is handled separately) and persist the
    exact services-state blob the frontend reads: `recommendations` (non-null) plus a
    non-empty `shortlist`, which together satisfy the `hasShortlist` gate on the
    Review & budget page. Reuses post_recommendations_batch + put_services_state so the
    shortlist carries real service_catalog_items.external_id item_ids the RFQ endpoint
    can resolve to suppliers.

    NOTE (AIQ-1689): satisfying `hasShortlist` is necessary but NOT sufficient for the
    "Request quotations" button to appear. That button is additionally wrapped in
    `isRfqEnabled()` (`VITE_ENABLE_RFQ`, a Vite build-time flag) which is not set on the
    deployed static site, so it renders for nobody — staged or hand-walked. QA reaches the
    step directly at `/employee/case/{caseId}/services/rfq/new` (the route is not gated).
    Do not "fix" this function for a missing button: verify the services_state row first."""
    from types import SimpleNamespace

    from ..recommendations.router import post_recommendations_batch as _post_batch
    from ..services import fx_service as _fx
    from .services_state import ServicesStatePut as _ServicesStatePut
    from .services_state import put_services_state as _put_services_state

    categories = ["movers", "schools"]
    stub = SimpleNamespace(state=SimpleNamespace(request_id=None))
    batch = _post_batch(
        request=stub, user=emp_user,
        body={"case_id": case_id, "selected_services": categories},
    ) or {}
    results = batch.get("results", {}) if isinstance(batch, dict) else {}

    recommendations_blob: Dict[str, Any] = {}
    shortlist_pairs: list = []
    for cat in categories:
        resp = results.get(cat)
        if resp is None:
            continue
        resp_dict = resp.model_dump(mode="json") if hasattr(resp, "model_dump") else dict(resp)
        items = resp_dict.get("recommendations") or []
        if not items:
            continue
        recommendations_blob[cat] = resp_dict
        top_ids = [it.get("item_id") for it in items[:3] if it.get("item_id")]
        if top_ids:
            shortlist_pairs.append([cat, top_ids])

    if not shortlist_pairs:
        # No movers/schools recs → the "Request quotes" button stays disabled. Loud +
        # structured (mirrors the vendor-seed 0-row logging): a silent empty shortlist is
        # the exact failure this fixture exists to prevent.
        logger.error(
            "test-drive staged: shortlist EMPTY for case %s — no movers/schools "
            "recommendations; 'Request quotes' will be disabled for the tester",
            case_id,
        )

    # The frontend serialises the shortlist Map as Array.from(map.entries()) — i.e. a list
    # of [category, item_id[]] pairs — and reads `recommendations` back untouched, so the
    # item_ids in `shortlist` MUST also appear in `recommendations[cat].recommendations`.
    # Derive display currency from the corridor's destination country (same source as
    # the vendor seed, ~line 397) so a seeded session matches a hand-walked one instead
    # of always showing EUR. Falls back to USD for uncovered corridors (fx_service default).
    _dest_country = TEST_DRIVE_CORRIDOR_ROUTES.get(corridor, {}).get("host_country")
    state = {
        "selectedServices": categories,
        "answers": {},
        "recommendations": recommendations_blob or None,
        "shortlist": shortlist_pairs,
        "displayCurrency": _fx.default_currency_for_country(_dest_country),
    }
    _put_services_state(case_id=case_id, body=_ServicesStatePut(state=state), user=emp_user)
    return {
        "categories": [p[0] for p in shortlist_pairs],
        "item_count": sum(len(p[1]) for p in shortlist_pairs),
    }


def _advance_to_stage(stage: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Drive a freshly provisioned session up to `stage` by invoking the SAME handlers
    an ordinary HR/employee session calls — no direct row inserts, so a seeded session
    and a hand-walked one produce equivalent DB rows. Cumulative: each stage runs every
    step below it. Synchronous by design (the QA fixture trades one backend call for the
    ~45 browser actions QA can't afford)."""
    outcome: Dict[str, Any] = {"stage": stage}
    if stage == "credentials":
        return outcome

    from types import SimpleNamespace

    from fastapi import BackgroundTasks

    from ... import main as _main
    from ...schemas import AssignCaseRequest
    from ..schemas import CaseDraftDTO
    from .cases_write import patch_case as _patch_case

    hr_user = {"id": ctx["hr_id"], "role": "HR", "email": ctx["hr_email"], "username": ctx["hr_username"]}
    emp_user = {"id": ctx["emp_id"], "role": "EMPLOYEE", "email": ctx["emp_email"], "username": ctx["emp_username"]}
    corridor = ctx["corridor_id"]

    # ── case_created: HR creates the relocation case + assigns the employee ──
    # (the real POST /api/hr/cases and .../assign handlers; assign_case stamps the
    #  corridor dest onto relocation_cases AND wizard_cases, which is what makes the
    #  city-scoped recommendations populate.)
    created = _main.create_case(user=hr_user)
    case_id = created.caseId
    stub = SimpleNamespace(state=SimpleNamespace(request_id=None))
    assign_body = AssignCaseRequest(
        employeeIdentifier=ctx["emp_email"],
        employeeFirstName=ctx["first_name"],
        employeeLastName="Tester",
    )
    assigned = _main.assign_case(case_id=case_id, request=assign_body, request_obj=stub, user=hr_user)
    assignment_id = assigned.assignmentId
    outcome["case_id"] = case_id
    outcome["assignment_id"] = assignment_id
    if stage == "case_created":
        return outcome

    # ── intake_complete: employee submits a complete intake draft (clears the ≥90% gate) ──
    draft = CaseDraftDTO(**_staged_intake_draft(corridor, ctx["emp_email"], ctx["first_name"]))
    _patch_case(case_id=case_id, patch=draft, background_tasks=BackgroundTasks(), user=emp_user)
    if stage == "intake_complete":
        return outcome

    # ── roadmap_ready: submit → the real async plan build → block until milestones land ──
    _main.submit_assignment(assignment_id=assignment_id, user=emp_user)
    outcome["milestones"] = _wait_for_roadmap(case_id)
    if stage == "roadmap_ready":
        return outcome

    # ── shortlist_ready: real recs → persist a non-empty services-state shortlist ──
    outcome["shortlist"] = _build_shortlist_state(case_id, emp_user, corridor)
    return outcome


@router.post("/provision-staged")
@limiter.limit(_RATE_LIMIT)
def provision_staged(body: ProvisionStagedRequest, request: Request):
    """QA-only staged provisioning: mint a test-drive session AND drive it up to a named
    `stage` using the real HR/employee handlers, so QA can reach the RFQ-submit step
    (which costs ~45 browser actions via the full flow) in a single call.

    Gated HARD — it drives the real case/intake/roadmap/recommendations pipeline, so it
    is reachable ONLY when the test-drive flag is on AND the campaign is a `qa-*` campaign
    (never the live `insead-2026` cohort), and only ever advances an `is_test` company.
    Reuses the same credential-minting core as /provision.
    """
    # 1) Dark-gate: the whole test-drive surface is off by default.
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    # 2) Optional invite token (same contract as /provision).
    expected_token = os.getenv("RELOPASS_TEST_DRIVE_INVITE_TOKEN") or ""
    supplied_token = (body.invite_token or "").strip()
    if supplied_token and expected_token and not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid or missing invite token")

    # 3) HARD campaign gate — QA only. Reject the live cohort and anything that isn't a
    #    `qa-*` campaign (dark-gated 404 so the surface isn't casually discoverable).
    campaign = (body.campaign or "").strip()
    if campaign == "insead-2026" or not campaign.startswith("qa-"):
        raise HTTPException(status_code=404, detail="Not found")

    stage = body.stage or "shortlist_ready"
    first_name = body.first_name.strip()
    slug = _slugify(first_name)
    requested_corridor = (body.corridor_id or "").strip()
    resolved_corridor = requested_corridor if requested_corridor in _LOCKED_CORRIDORS else _assign_corridor(campaign)

    ctx = _mint_test_drive_identities(body, first_name, slug, campaign, resolved_corridor)

    # 4) is_test assertion (defense in depth): staged provisioning only ever advances a
    #    test company. The minted "Test Drive …" company always qualifies; refuse otherwise.
    if not looks_like_test_company(ctx.get("company_name")):
        raise HTTPException(status_code=403, detail="Staged provisioning requires an is_test company")

    ctx["corridor_id"] = resolved_corridor
    advanced = _advance_to_stage(stage, ctx)

    return {
        "session_id": ctx["session_id"],
        "corridor_id": ctx["corridor_id"],
        "campaign": ctx["campaign"],
        "stage": advanced.get("stage", stage),
        "case_id": advanced.get("case_id"),
        "assignment_id": advanced.get("assignment_id"),
        "milestones": advanced.get("milestones"),
        "shortlist": advanced.get("shortlist"),
        "hr": ctx["hr"],
        "employee": ctx["employee"],
    }


# ── TD-5 (AIQ-1423): completion survey ────────────────────────────────────────
# One wide survey_responses row per submission (table + RLS from TD-1). Public and
# campaign-gated like /provision, but no invite token (it's a post-test submission).
# tester_name/email + testimonial/referral are the only real PII captured — each
# carries its own consent flag and is stored only in the admin-read RLS table (never
# sent to an LLM, so no masking needed). Nothing here is logged.
#
# NOTE: `referrals` (jsonb, the multi-referral list) is NOT in this tuple — it needs a
# ``CAST(:referrals AS jsonb)`` on Postgres, so survey() binds it explicitly. The legacy
# scalar referral_* columns stay here and keep receiving referrals[0] (see _mirror_*).
_SURVEY_COLUMNS = (
    "session_id campaign corridor_id tester_segment tester_name tester_email "
    "tester_company_role tester_sector q1_overall q2_friction q3_problem_fit q3_why "
    "q4_change trust_intent trust_intent_why "  # TD-M4 (AIQ-1559)
    "testimonial testimonial_consent pilot_interest pilot_note referral_name "
    "referral_company_role referral_contact referral_consent"
).split()


# AIQ-1543: a pragmatic address shape (local@domain.tld). Deliberately not RFC-strict —
# it rejects the obvious garbage the lead-in used to accept while never blocking a real
# address. Mirrors the client-side check in TestDriveSurveyPage.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_optional_uuid(v: Optional[str]) -> Optional[str]:
    """AIQ-1540: a blank/absent session_id is fine, but a present one must be a real
    UUID. The survey/event/complete SQL casts session_id with ``CAST(:id AS uuid)`` on
    Postgres, so a non-UUID string used to raise an unhandled 500 — reject it as a 422
    (validation error) instead. SQLite (tests) has no cast, but we validate uniformly."""
    if v is None:
        return v
    s = v.strip()
    if not s:
        return None
    try:
        uuid.UUID(s)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("session_id must be a valid UUID.")
    return s


# Multi-referral: a respondent can leave 1..N warm intros. The form caps at 5; the API
# accepts a few more and TRUNCATES rather than 422s — a survey must never fail on an
# optional field, and losing referral #11 beats losing the whole submission.
_MAX_REFERRALS = 10


class ReferralItem(BaseModel):
    """One warm intro. Every field is optional; entries with neither a name nor a contact
    are dropped by _normalize_referrals (a company/role alone isn't a reachable person, and
    the admin 'intro' count keys on name-or-contact — see admin_test_drive._REFERRAL_PRESENT)."""
    name: Optional[str] = Field(None, max_length=200)
    company_role: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=300)
    consent: bool = False


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
    # TD-M4 (AIQ-1559): trust / intent-to-use — the predictive signal. One tap + optional why.
    trust_intent: Optional[str] = Field(None, pattern="^(yes|maybe|no)$")
    trust_intent_why: Optional[str] = None
    # Q5 testimonial (+ quote consent), Q6 pilot interest, Q7 referral (+ consent)
    testimonial: Optional[str] = None
    testimonial_consent: bool = False
    pilot_interest: Optional[str] = Field(None, pattern="^(yes|maybe|no)$")
    pilot_note: Optional[str] = None
    # Legacy single-referral fields. KEPT — they are the mirror of referrals[0] and two live
    # readers still consume them (the admin 'intro' count + the daily Cowork warm-lead alert).
    referral_name: Optional[str] = Field(None, max_length=200)
    referral_company_role: Optional[str] = Field(None, max_length=200)
    referral_contact: Optional[str] = Field(None, max_length=300)
    referral_consent: bool = False
    # The multi-referral list. Absent on old clients — _normalize_referrals then wraps the
    # legacy scalars above into a 1-element list, so both shapes land in `referrals`.
    referrals: Optional[List[ReferralItem]] = None

    @field_validator("referrals")
    @classmethod
    def _cap_referrals(cls, v: Optional[List[ReferralItem]]) -> Optional[List[ReferralItem]]:
        # Truncate, never reject: an over-long list is a UI bug or a bored tester, not a
        # reason to lose the survey.
        return v[:_MAX_REFERRALS] if v else v

    @field_validator("tester_email")
    @classmethod
    def _validate_tester_email(cls, v: Optional[str]) -> Optional[str]:
        # AIQ-1543: the email stays optional — an omitted/blank value is fine — but a
        # non-empty one must look like an address, so the lead-in no longer accepts
        # (and the admin thank-you mailto no longer breaks on) garbage like "notanemail".
        if v is None:
            return v
        s = v.strip()
        if not s:
            return None
        if not _EMAIL_RE.match(s):
            raise ValueError("Enter a valid email address.")
        return s

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_uuid(v)


def _normalize_referrals(body: SurveyRequest) -> List[Dict[str, Any]]:
    """The survey's referrals as one canonical list, whichever shape the client sent.

    New clients post ``referrals: [{name, company_role, contact, consent}, ...]``; old ones
    post only the legacy scalars, which are wrapped into a 1-element list. Entries with
    neither a name nor a contact are dropped — a company/role alone is not a reachable
    person, and dropping them keeps `referrals` consistent with the admin panel's
    "intro" predicate (referral_name OR referral_contact present).

    Blank strings are normalised to None so the mirrored legacy columns store a true NULL,
    which is what the admin count and the daily warm-lead alert filter on.
    """
    def _entry(name: Any, role: Any, contact: Any, consent: Any) -> Optional[Dict[str, Any]]:
        n, r, c = (str(name or "").strip(), str(role or "").strip(), str(contact or "").strip())
        if not (n or c):
            return None
        return {
            "name": n or None,
            "company_role": r or None,
            "contact": c or None,
            "consent": bool(consent),
        }

    items = [
        e for e in (
            _entry(r.name, r.company_role, r.contact, r.consent) for r in (body.referrals or [])
        ) if e is not None
    ]
    if items:
        return items
    legacy = _entry(
        body.referral_name, body.referral_company_role, body.referral_contact, body.referral_consent,
    )
    return [legacy] if legacy else []


def _propagate_tester_segment(session_id: Optional[str], tester_segment: Optional[str]) -> None:
    """TD-FIX-2 (AIQ-1503): the survey's one-tap self-ID is the source of truth for the
    tester segment (the single-link model can't tag it at provision). Write it back onto
    the linked test_sessions row so the admin segment slices are correct. Best-effort —
    never raises into the survey write; a NULL/absent answer is left untouched (honest)."""
    if not session_id or not tester_segment:
        return
    try:
        sid_expr = ":sid" if _IS_SQLITE else "CAST(:sid AS uuid)"
        with db.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE test_sessions SET tester_segment = :seg WHERE id = {sid_expr}"),
                {"seg": tester_segment, "sid": session_id},
            )
    except Exception:  # noqa: BLE001 — segment propagation must never break the survey write
        logger.warning("test_drive segment propagation failed (suppressed)")


def _session_context(session_id: Optional[str]) -> "tuple[Optional[str], Optional[str]]":
    """AIQ-1546: the survey link carries no reliable campaign/corridor (the survey page
    defaults campaign and reads corridor from a ?corridor= param that is usually absent),
    so derive both from the linked test_sessions row — the session is the source of truth
    for which campaign + corridor this tester actually ran. Returns (campaign, corridor_id);
    each is None when there's no session or the lookup fails (caller falls back to
    body/default). Best-effort — never raises into the survey write."""
    if not session_id:
        return None, None
    try:
        sid_expr = ":sid" if _IS_SQLITE else "CAST(:sid AS uuid)"
        with db.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT campaign, corridor_id FROM test_sessions WHERE id = {sid_expr}"),
                {"sid": session_id},
            ).mappings().first()
        if row:
            return row.get("campaign"), row.get("corridor_id")
    except Exception:  # noqa: BLE001 — a lookup failure must never break the survey write
        logger.warning("test_drive session context lookup failed (suppressed)")
    return None, None


def _mark_session_completed_if_needed(
    session_id: Optional[str],
    *,
    campaign: Optional[str],
    corridor_id: Optional[str],
    tester_segment: Optional[str],
) -> None:
    """TD-FIX-1 (AIQ-1502) belt-and-braces: the survey page is reachable directly
    (its copy explicitly invites testers who "had to stop early"), so a tester can
    submit it without the /complete CTA ever firing. If the linked session has no
    completed_at yet, mark it completed and emit a distinct 'completed' funnel event.

    Idempotent via ``completed_at IS NULL`` so a session already completed by the CTA
    is left untouched and the 'completed' event fires at most once. Best-effort —
    never raises into the survey write."""
    if not session_id:
        return
    try:
        sid_expr = ":sid" if _IS_SQLITE else "CAST(:sid AS uuid)"
        with db.engine.begin() as conn:
            result = conn.execute(
                text(
                    f"UPDATE test_sessions SET status='completed', completed_at=CURRENT_TIMESTAMP "
                    f"WHERE id = {sid_expr} AND completed_at IS NULL"
                ),
                {"sid": session_id},
            )
        # Only emit on the started→completed transition — keeps the completed count
        # honest when the /complete CTA already fired for this session.
        if getattr(result, "rowcount", 0):
            _emit_funnel_event(
                event_type="completed", session_id=session_id, campaign=campaign,
                corridor_id=corridor_id, tester_segment=tester_segment,
                metadata={"via": "survey"},
            )
    except Exception:  # noqa: BLE001 — belt-and-braces must never break the survey write
        logger.warning("test_drive survey→complete backfill failed (suppressed)")


@router.post("/survey")
@limiter.limit(_RATE_LIMIT)
def survey(body: SurveyRequest, request: Request):
    """Persist one completion-survey submission into survey_responses.

    404 when the campaign is off. Returns {ok, response_id}. All fields optional
    (only three questions ask for typing, all optional).
    """
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    sid = (body.session_id or "").strip() or None
    # AIQ-1546: derive campaign + corridor from the linked session (the source of truth),
    # falling back to the body/env default only when there's no session. Fixes rows that
    # were saved with corridor_id=NULL and a hardcoded campaign.
    sess_campaign, sess_corridor = _session_context(sid)
    # AIQ-1639: with no session (source of truth) AND no explicitly-supplied campaign we do
    # NOT know which cohort this survey belongs to — leave it NULL (unattributed) rather than
    # silently filing it into the live 'insead-2026' cohort, which would contaminate every
    # headline number (problem-fit %, pilot interest, testimonials). Unlike /provision, a
    # session-less survey has no legitimate default cohort — the env fallback is removed here.
    campaign = sess_campaign or (body.campaign or "").strip() or None
    corridor_id = sess_corridor or body.corridor_id
    response_id = str(uuid.uuid4())
    id_expr = ":id" if _IS_SQLITE else "CAST(:id AS uuid)"
    session_expr = ":session_id" if _IS_SQLITE else "CAST(:session_id AS uuid)"

    referrals_expr = ":referrals" if _IS_SQLITE else "CAST(:referrals AS jsonb)"

    params = {c: getattr(body, c) for c in _SURVEY_COLUMNS}
    params["id"] = response_id
    params["campaign"] = campaign
    params["corridor_id"] = corridor_id
    params["session_id"] = sid

    # Multi-referral: the full list goes to the `referrals` jsonb column, and referrals[0] is
    # MIRRORED back onto the legacy scalar columns. The mirror is load-bearing, not vestigial —
    # the admin panel's "intro" count and the daily Cowork warm-lead alert both read the scalars.
    referrals = _normalize_referrals(body)
    first = referrals[0] if referrals else None
    params["referrals"] = json.dumps(referrals)
    params["referral_name"] = first["name"] if first else None
    params["referral_company_role"] = first["company_role"] if first else None
    params["referral_contact"] = first["contact"] if first else None
    params["referral_consent"] = bool(first["consent"]) if first else False

    col_sql = ", ".join(
        ["id", "session_id", "referrals"] + [c for c in _SURVEY_COLUMNS if c != "session_id"]
    )
    val_sql = ", ".join(
        [id_expr, session_expr, referrals_expr]
        + [f":{c}" for c in _SURVEY_COLUMNS if c != "session_id"]
    )
    with db.engine.begin() as conn:
        # AIQ-1542: one survey per session (latest wins). survey_responses had only a
        # non-unique index on session_id, so a re-submit piled up duplicate rows and
        # inflated the surveyed count. Replace any prior row for this session; a
        # NULL-session survey is anonymous and never deduped against others.
        is_resubmit = False
        if sid is not None:
            is_resubmit = conn.execute(
                text(f"SELECT 1 FROM survey_responses WHERE session_id = {session_expr}"),
                {"session_id": sid},
            ).first() is not None
            if is_resubmit:
                conn.execute(
                    text(f"DELETE FROM survey_responses WHERE session_id = {session_expr}"),
                    {"session_id": sid},
                )
        conn.execute(text(f"INSERT INTO survey_responses ({col_sql}) VALUES ({val_sql})"), params)

    # TD-FIX-2 (AIQ-1503): stamp the self-declared segment back onto the session row.
    _propagate_tester_segment(params["session_id"], body.tester_segment)

    # TD-FIX-1 (AIQ-1502): belt-and-braces — a direct survey submit also completes the
    # session if the /complete CTA never fired. 'completed' stays distinct from 'surveyed'.
    _mark_session_completed_if_needed(
        params["session_id"], campaign=campaign,
        corridor_id=corridor_id, tester_segment=body.tester_segment,
    )
    # AIQ-1542: the one-time side effects (funnel 'surveyed', pipeline, email fan-out) fire
    # only on the FIRST submission for a session — a correction re-submit replaces the row
    # without re-counting the tester or re-notifying.
    if not is_resubmit:
        # TD-8: funnel — this session reached the survey.
        _emit_funnel_event(
            event_type="surveyed", session_id=params["session_id"], campaign=campaign,
            corridor_id=corridor_id, tester_segment=body.tester_segment,
        )
        # TD-7: turn survey answers into pipeline (best-effort; never breaks the survey write).
        _process_survey_pipeline(body, campaign, corridor_id, referrals)
        # AIQ-1547: notify the admin of the completion IN-APP (admin Inbox / NotificationsBell)
        # by default — a Resend email per completion won't survive a cohort on the free tier.
        # Channel is gated by RELOPASS_TEST_DRIVE_NOTIFY_CHANNEL (default 'inapp' → zero email).
        # Best-effort; never breaks the survey write.
        try:
            from ..services.test_drive_notifications import notify_test_drive_completion
            notify_test_drive_completion(
                tester_name=body.tester_name, tester_email=body.tester_email, campaign=campaign,
                corridor_id=corridor_id, tester_segment=body.tester_segment,
                company_role=body.tester_company_role, sector=body.tester_sector,
                q1_overall=body.q1_overall, q2_friction=body.q2_friction, q3_problem_fit=body.q3_problem_fit,
                q4_change=body.q4_change, pilot_interest=body.pilot_interest, pilot_note=body.pilot_note,
                testimonial=body.testimonial,
                # The mirrored first referral, NOT the raw body fields — a client that posts
                # only the `referrals` array would otherwise notify with an empty referral.
                referral_name=params["referral_name"],
                referral_company_role=params["referral_company_role"],
                referral_contact=params["referral_contact"],
                referral_consent=params["referral_consent"],
                # The FULL list, so the notification names everyone the tester referred —
                # the legacy scalars above are only referrals[0].
                referrals=referrals,
            )
        except Exception:  # noqa: BLE001
            logger.warning("test_drive completion notify failed (suppressed)")

    logger.info(
        "test_drive_survey response=%s session=%s campaign=%s pilot=%s",
        response_id, params["session_id"], campaign, body.pilot_interest,
    )
    return {"ok": True, "response_id": response_id}


# ── TD-7 (AIQ-1425): survey answers → pipeline ────────────────────────────────
def _process_survey_pipeline(
    body: SurveyRequest,
    campaign: str,
    corridor_id: Optional[str],
    referrals: List[Dict[str, Any]],
) -> None:
    """Q7 intros → one prospect_candidates row EACH; Q6 pilot Yes/Maybe → a warm-lead funnel event.

    ``referrals`` is the normalised list from _normalize_referrals — already covering both the
    array shape and the legacy single-referral shape, so this function no longer reads the
    scalar referral_* fields itself.

    Best-effort — never raises into the survey write. Design note: prospect_candidates
    is company-centric (company_name NOT NULL) and its enrichment path sends
    raw_input_json['notes'] to an LLM unmasked, so referral PII is stashed under
    DEDICATED keys (never 'notes') and enrichment is not queued.

    AIQ-1546: ``corridor_id`` is the session-derived corridor, so the intro/pilot funnel
    events (and the stashed referral corridor) carry the real corridor, not a NULL.
    """
    # Q6 — "warm pilot lead" is a funnel event keyed on the tester's session (the
    # purpose-built flag; the tester is a survey_responses/test_sessions row, not a company).
    if body.pilot_interest in ("yes", "maybe"):
        _emit_funnel_event(
            event_type="pilot-interested", session_id=(body.session_id or None), campaign=campaign,
            corridor_id=corridor_id, tester_segment=body.tester_segment,
            metadata={"pilot_interest": body.pilot_interest},
        )

    # Q7 — every referral becomes its own prospect_candidates row.
    if not referrals:
        return

    # ONE 'intro' event per survey (not per referral): the admin panel counts intros as
    # survey rows carrying a referral, so a per-referral event would desync the two views.
    # `count` carries the real number for anyone who wants it.
    _emit_funnel_event(
        event_type="intro", session_id=(body.session_id or None), campaign=campaign,
        corridor_id=corridor_id, tester_segment=body.tester_segment,
        metadata={
            "has_contact": bool(referrals[0].get("contact")),
            "count": len(referrals),
        },
    )
    try:
        from ..db import SessionLocal
        from ..models import ProspectCandidate

        referred_by = (body.tester_name or body.tester_email or "").strip() or None
        with SessionLocal() as s:
            for ref in referrals:
                company_name = ref.get("company_role") or "Test-drive referral"
                raw = json.dumps(
                    {
                        "source": "test_drive_referral",
                        # NOT 'notes' — 'notes' is fed to the enrichment LLM.
                        "referred_by": referred_by,
                        "referral_name": ref.get("name"),
                        "referral_company_role": ref.get("company_role"),
                        "referral_contact": ref.get("contact"),
                        "referral_consent": bool(ref.get("consent")),
                        "corridor_id": corridor_id,
                        "campaign": campaign,
                    },
                    ensure_ascii=False,
                )
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

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_uuid(v)


@router.post("/event")
@limiter.limit(_RATE_LIMIT)
def record_event(body: EventRequest, request: Request):
    """Record one funnel event (invite/click/stage). 404 when the campaign is off,
    400 on an unknown event_type (allow-listed). Public + rate-limited."""
    if not _test_drive_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    if body.event_type not in _ALLOWED_FUNNEL_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event_type")
    # [campaign attribution] Absent campaign → 'unattributed', NEVER the live 'insead-2026' cohort:
    # silently defaulting there contaminated the cohort's headline metrics and forced three manual
    # purges. Only an explicit ?campaign= attributes a session (the real cohort link passes it).
    # Mirrors the AIQ-1639 survey fix; test_sessions.campaign is NOT NULL so we use an explicit
    # sentinel rather than the survey's NULL.
    campaign = (body.campaign or "").strip() or "unattributed"
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

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, v: str) -> str:
        # AIQ-1540: required, and must be a UUID — guards the CAST(:sid AS uuid) in complete().
        s = (v or "").strip()
        if not s:
            raise ValueError("session_id is required.")
        try:
            uuid.UUID(s)
        except (ValueError, AttributeError, TypeError):
            raise ValueError("session_id must be a valid UUID.")
        return s


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
        result = conn.execute(
            text(
                f"UPDATE test_sessions SET status='completed', completed_at=CURRENT_TIMESTAMP "
                f"WHERE id = {sid_expr} AND completed_at IS NULL"
            ),
            {"sid": body.session_id},
        )
    # AIQ-1536: emit the 'completed' funnel event only on the started→completed transition.
    # A double-click (or the survey backfill having already completed the session) leaves
    # completed_at set, so rowcount is 0 and we don't double-count the headline metric.
    # The response stays 200 + honest either way (idempotent).
    if getattr(result, "rowcount", 0):
        _emit_funnel_event(
            event_type="completed", session_id=body.session_id, campaign=row.get("campaign"),
            corridor_id=row.get("corridor_id"), tester_segment=row.get("tester_segment"),
            metadata={"reached": reached},
        )
    logger.info("test_drive_complete session=%s reached=%s", body.session_id, reached)
    return {"ok": True, "reached": reached, "nudge": nudge}
