"""
FastAPI main application for ReloPass backend.
"""
import logging
import time
import os
import json as _json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Header, Depends, Query, UploadFile, File, Request, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import uuid
from datetime import datetime, date
import re
import json
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .schemas import (
    RegisterRequest, LoginRequest, LoginResponse, AnswerRequest, NextQuestionResponse,
    RelocationProfile, DashboardResponse, HousingRecommendation,
    SchoolRecommendation, MoverRecommendation, TimelinePhase, TimelineTask,
    OverallStatus, UserResponse, UserRole, AssignmentStatus, AssignCaseRequest,
    AssignCaseResponse, CreateCaseResponse, AssignmentSummary, AssignmentDetail, AssignmentsListResponse,
    PostSignupReconciliation,
    IntakeChecklistItem, CaseReadinessUi,
    EmployeeJourneyRequest, EmployeeJourneyNextQuestion, HRAssignmentDecision,
    UpdateAssignmentIdentifierRequest, ClaimAssignmentRequest,
    UpdateProfilePhotoRequest, PolicyExceptionRequest, ComplianceActionRequest,
    AddEvidenceRequest, AddEvidenceResponse,
)
from .services.dossier import evaluate_applies_if, validate_answer, fetch_search_results, build_suggested_questions
from .services.guidance_pack_service import generate_guidance_pack
from .services.policy_adapter import normalize_policy_caps
from .services.policy_extractor import extract_policy_from_bytes
from .app.services.timeline_service import compute_default_milestones, compute_timeline_summary
from .hr_case_readiness_view import build_intake_checklist_items, build_hr_case_readiness_ui
from .services.country_resources import (
    build_profile_context,
    get_personalization_hints,
    get_default_section_content,
    RESOURCE_SECTIONS,
    SECTION_LABELS,
)
from .services.rkg_resources import (
    get_resource_context,
    get_country_resources as rkg_get_country_resources,
    get_country_events as rkg_get_country_events,
    get_recommended_resources,
    resources_to_sections,
)
from .services.supabase_client import get_supabase_admin_client
from .app.services.requirements_sufficiency import compute_requirements_sufficiency
# Import db_config first and log before any DB connection attempt
# TODO: Remove masked DB log after confirming production connectivity
from .db_config import DATABASE_URL as _db_url, get_masked_db_log_line
log.info("Startup DB config (user/host only, no password): %s", get_masked_db_log_line())
from .database import db, Database
from .services.unified_assignment_creation import create_assignment_with_contact_and_invites
from .identity_errors import IdentityErrorCode, err_detail
from .identity_observability import (
    identity_event,
    principal_fingerprint,
    principal_fingerprint_from_login_identifier,
)
from .services.assignment_claim_link_service import reconcile_pending_assignment_claims
from .services.employee_assignment_overview import build_employee_assignment_overview
from .services.explicit_pending_link_service import (
    execute_pending_explicit_link,
    finalize_assignment_claim_attach,
    PENDING_LINK_COMPANY_MISMATCH,
    PENDING_LINK_CONTACT_NOT_LINKED,
    PENDING_LINK_EXTRA_VERIFICATION,
    PENDING_LINK_IDENTITY_MISMATCH,
    PENDING_LINK_INVITE_REVOKED,
    PENDING_LINK_NO_CONTACT,
    PENDING_LINK_NOT_FOUND,
    PENDING_LINK_NOT_PENDING,
    PENDING_LINK_OTHER_OWNER,
)
from .dev_seed_auth import ensure_dev_seed_auth_user
from .agents.orchestrator import IntakeOrchestrator
from .agents.compliance_engine import ComplianceEngine
from .policy_engine import PolicyEngine
from .app.db import init_db, SessionLocal
from .app import crud as app_crud
from .app.seed import seed_demo_cases
from .app.seed_suppliers import seed_suppliers_from_recommendation_datasets
from .app.routers import cases as cases_router
from .app.routers import admin as admin_router
from .app.routers import admin_resources as admin_resources_router
from .app.routers import admin_staging as admin_staging_router
from .app.routers import admin_freshness as admin_freshness_router
from .app.routers import admin_review_queue as admin_review_queue_router
from .app.routers import admin_notifications as admin_notifications_router
from .app.routers import admin_ops_analytics as admin_ops_analytics_router
from .app.routers import admin_workflow_analytics as admin_workflow_analytics_router
from .app.routers import admin_collaboration as admin_collaboration_router
from .app.routers import mobility_context as mobility_context_router
from .app.routers import admin_mobility as admin_mobility_router
from .routes import relocation as relocation_router
from .routes import compat as compat_router
from .routes import relocation_classify as relocation_classify_router
from .routes import resources as resources_router
from .app.recommendations.router import router as recommendations_router
from .app.recommendations.admin_debug import router as admin_recommendations_debug_router
from .app.routers import suppliers as suppliers_router
from .app.services.question_engine import generate_questions
from pydantic import BaseModel as _BaseModel
from contextlib import contextmanager
from .services.supabase_client import get_supabase_admin_client

# ---------------------------------------------------------------------------
# Startup: validate DATABASE_URL and log DB type
# ---------------------------------------------------------------------------
_db_info = Database.get_db_info()
_db_scheme = _db_info["db_url_scheme"]
_db_host = _db_info["db_host"] or "(local file)"

# Legacy demo seed flags (used in startup logs and runtime diagnostics)
ALLOW_LEGACY_DEMO_SEED = os.getenv("ALLOW_LEGACY_DEMO_SEED", "").lower() in ("1", "true", "yes")
DISABLE_DEMO_RESEED = os.getenv("DISABLE_DEMO_RESEED", "").lower() in ("1", "true", "yes")

log.info("DB engine: %s | host: %s", _db_scheme, _db_host)

if any(p in _db_url for p in ["YOUR_PASSWORD", "YOUR_HOST", "<password>", "placeholder"]):
    log.error("DATABASE_URL contains placeholder text! Fix it in Render env vars.")
    raise RuntimeError("DATABASE_URL contains placeholder text — refusing to start.")

if _db_scheme == "sqlite":
    log.warning("Running with SQLite — data will NOT persist across Render redeploys!")
else:
    log.info("Running with PostgreSQL — data persists across redeploys.")

app = FastAPI(title="ReloPass API", version="1.0.0")
admin_graph_build_marker = os.getenv("ADMIN_GRAPH_BUILD_MARKER", "local-dev")
log.info(
    "ADMIN_GRAPH_BUILD_MARKER=%s db_scheme=%s seed_guard_active=%s DISABLE_DEMO_RESEED=%s ALLOW_LEGACY_DEMO_SEED=%s",
    admin_graph_build_marker,
    _db_scheme,
    (_db_scheme == "sqlite" and DISABLE_DEMO_RESEED),
    DISABLE_DEMO_RESEED,
    ALLOW_LEGACY_DEMO_SEED,
)
log.info("Initializing database schemas...")
init_db()
db.log_expected_tables_status()
try:
    from .services.policy_storage_health import log_startup_storage_diagnostic
    log_startup_storage_diagnostic(db)
except Exception as e:
    log.warning("policy_storage startup diagnostic skipped: %s", e)
log.info("Seeding demo cases...")
seed_demo_cases()
try:
    n = seed_suppliers_from_recommendation_datasets()
    if n:
        log.info("Seeded %d suppliers from recommendation datasets (living_areas, schools, movers).", n)
except Exception as e:
    log.warning("Supplier seed skipped or failed: %s", e)
log.info("Startup complete.")

# CORS middleware (include Vite fallback ports 3002–3005 for local dev)
default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:3005",
    "http://localhost:5173",
    "https://relopass.com",
    "https://www.relopass.com",
]
env_origins = os.getenv("CORS_ORIGINS")
if env_origins:
    extra = [o.strip() for o in env_origins.split(",") if o.strip()]
    default_origins = list(dict.fromkeys(default_origins + extra))
origin_regex = os.getenv("CORS_ORIGIN_REGEX") or r"https://.*\.relopass\.com"

# NOTE: Register HTTP middleware before CORSMiddleware. Starlette prepends each
# add_middleware / @app.middleware at index 0, so registering CORS *after* the
# request-id middleware yields stack ServerError → CORS → RequestID → routes.
# If CORS is inner (RequestID outer), some cross-origin responses can miss ACAO
# headers and Chrome reports a generic "CORS error" (often on XHR with Auth).


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure 500 responses include JSON body and go through normal response path (CORS)."""
    from fastapi import HTTPException as _HTTPEx
    if isinstance(exc, _HTTPEx):
        raise exc
    req_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    log.error(
        "request_id=%s method=%s path=%s unhandled_exception=%s",
        req_id, request.method, request.url.path, repr(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id},
    )


@app.middleware("http")
async def request_id_and_timing_middleware(request: Request, call_next):
    """
    Attach a request_id to each request/response and log overall handler duration.
    Correlates with frontend X-Request-ID and DB/query spans.
    """
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # pragma: no cover - defensive logging
        dur_ms = (time.perf_counter() - start) * 1000
        log.error(
            "request_id=%s method=%s path=%s error=%s dur_ms=%.2f",
            req_id,
            request.method,
            request.url.path,
            repr(exc),
            dur_ms,
            exc_info=True,
        )
        raise
    dur_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = req_id
    user_id = getattr(request.state, "user_id", None)
    log.info(
        "request_id=%s method=%s path=%s status=%s dur_ms=%.2f user_id=%s",
        req_id,
        request.method,
        request.url.path,
        response.status_code,
        dur_ms,
        user_id,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    # Fewer preflight round-trips on repeat requests (helps perceived lag on slow networks).
    max_age=86400,
)

app.include_router(compat_router.router)
app.include_router(cases_router.router)
app.include_router(mobility_context_router.router)
app.include_router(admin_mobility_router.router)
app.include_router(admin_router.router)
app.include_router(admin_resources_router.router, prefix="/api/admin")
app.include_router(admin_staging_router.router, prefix="/api/admin")
app.include_router(admin_freshness_router.router, prefix="/api/admin")
app.include_router(admin_freshness_router.crawl_router, prefix="/api/admin")
app.include_router(admin_freshness_router.changes_router, prefix="/api/admin")
app.include_router(admin_review_queue_router.router, prefix="/api/admin")
app.include_router(admin_notifications_router.router, prefix="/api/admin")
app.include_router(admin_ops_analytics_router.router, prefix="/api/admin")
app.include_router(admin_workflow_analytics_router.router, prefix="/api/admin")
app.include_router(admin_collaboration_router.router, prefix="/api/admin")
app.include_router(admin_recommendations_debug_router, prefix="/api/admin")
app.include_router(suppliers_router.router)
app.include_router(resources_router.router)
app.include_router(recommendations_router)
app.include_router(relocation_router.router)
app.include_router(relocation_router.api_router)
app.include_router(relocation_classify_router.router)

# ---------------------------------------------------------------------------
# Global exception handler: log unhandled errors
# ---------------------------------------------------------------------------
import traceback

@app.exception_handler(Exception)
def _log_unhandled_exception(request, exc: Exception):
    from fastapi import HTTPException as _HTTP
    if isinstance(exc, _HTTP):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    tb = traceback.format_exc()
    log.error("Unhandled exception: %s\n%s", exc, tb)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@contextmanager
def timed(span: str, request_id: Optional[str] = None):
  """
  Lightweight span timing helper for endpoint internals.

  Usage:
      with timed("db.get_assignment_by_id", request.state.request_id):
          ...
  """
  start = time.perf_counter()
  try:
      yield
  finally:
      dur_ms = (time.perf_counter() - start) * 1000
      if request_id:
          log.info("request_id=%s span=%s dur_ms=%.2f", request_id, span, dur_ms)
      else:
          log.info("span=%s dur_ms=%.2f", span, dur_ms)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ReloPass API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Debug / diagnostics endpoints
# ---------------------------------------------------------------------------
@app.get("/debug/db")
def debug_db():
    """Return non-secret database connectivity info."""
    return Database.get_db_info()


class _DebugKVBody(_BaseModel):
    key: str
    value: str


@app.post("/debug/kv")
def debug_kv_set(body: _DebugKVBody):
    db.debug_kv_set(body.key, body.value)
    return {"ok": True, "key": body.key}


@app.get("/debug/kv/{key}")
def debug_kv_get(key: str):
    result = db.debug_kv_get(key)
    if not result:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return result


# Global orchestrator
orchestrator = IntakeOrchestrator()
compliance_engine = ComplianceEngine()
policy_engine = PolicyEngine()


def _seed_demo_cases() -> None:
    """Seed deterministic demo cases for HR workflows."""
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    demo_password = pwd_context.hash("Passw0rd!")

    def ensure_user(user_id: str, email: str, role: str, name: str) -> str:
        return ensure_dev_seed_auth_user(
            db,
            user_id=user_id,
            email=email,
            password_hash=demo_password,
            role=role,
            name=name,
        )

    hr_user_id = ensure_user(
        user_id="demo-hr-001",
        email="hr.demo@relopass.local",
        role="HR",
        name="HR Demo",
    )
    hr_user_id_2 = ensure_user(
        user_id="demo-hr-002",
        email="hr@relopass.com",
        role="HR",
        name="HR Manager",
    )

    employees = [
        ("demo-emp-001", "sarah.jenkins@relopass.local", "Sarah Jenkins"),
        ("demo-emp-002", "mark.thompson@relopass.local", "Mark Thompson"),
        ("demo-emp-003", "demo@relopass.com", "Demo Employee"),
        ("test-emp-test", "testEMPtest@relopass.com", "Test Employee"),
    ]
    for emp_id, emp_email, emp_name in employees:
        ensure_user(emp_id, emp_email, "EMPLOYEE", emp_name)

    # Admin seed + allowlist
    admin_user_id = ensure_user(
        user_id="demo-admin-001",
        email="admin@relopass.com",
        role="ADMIN",
        name="ReloPass Admin",
    )
    db.add_admin_allowlist("admin@relopass.com", admin_user_id)

    # Seed admin console entities
    company_id = "demo-company-001"
    db.create_company(company_id, "Acme Corp", "Singapore", "200-500", "1 Raffles Place, Singapore", "+65 6123 4567", "hr@acme.com")
    test_company_id = "test-company-001"
    db.create_company(test_company_id, "test", "Singapore", "1-50", "", "", "")
    db.ensure_profile_record(hr_user_id, "hr.demo@relopass.local", "HR", "HR Demo", company_id)
    db.ensure_profile_record(hr_user_id_2, "hr@relopass.com", "HR", "HR Manager", company_id)
    db.ensure_profile_record(admin_user_id, "admin@relopass.com", "ADMIN", "ReloPass Admin", None)
    for emp_id, emp_email, emp_name in employees:
        # testEMPtest belongs to company "test" for policy visibility testing
        profile_company = test_company_id if emp_id == "test-emp-test" else company_id
        db.ensure_profile_record(emp_id, emp_email, "EMPLOYEE", emp_name, profile_company)

    db.create_hr_user("hr-001", company_id, hr_user_id, {"can_manage_policy": True})
    db.create_hr_user("hr-002", company_id, hr_user_id_2, {"can_manage_policy": True})
    db.create_hr_user("hr-003", test_company_id, hr_user_id_2, {"can_manage_policy": True})
    db.create_employee("emp-001", company_id, "demo-emp-001", "Band2", "Long-Term", "demo-case-oslo-sg-family", "active")
    db.create_employee("emp-002", company_id, "demo-emp-003", "Band1", "Long-Term", "demo-case-demo-emp", "active")

    db.upsert_relocation_case(
        case_id="demo-case-oslo-sg-family",
        company_id=company_id,
        employee_id="emp-001",
        status="in_progress",
        stage="docs",
        host_country="Singapore",
        home_country="Norway",
    )
    db.upsert_relocation_case(
        case_id="demo-case-demo-emp",
        company_id=company_id,
        employee_id="emp-002",
        status="blocked",
        stage="policy",
        host_country="Singapore",
        home_country="United States",
    )

    db.create_support_case(
        support_case_id="support-001",
        company_id=company_id,
        created_by_profile_id=hr_user_id,
        category="policy",
        severity="high",
        status="open",
        summary="Policy caps not matching assignment band",
        employee_id="emp-002",
        hr_profile_id=hr_user_id,
        last_error_code="POLICY_CAP_MISMATCH",
        last_error_context={"band": "Band1", "assignmentType": "Long-Term"},
    )

    scenarios = [
        {
            "case_id": "demo-case-oslo-sg-family",
            "assignment_id": "demo-assignment-oslo-sg-family",
            "employee_identifier": "sarah.jenkins@relopass.local",
            "status": AssignmentStatus.SUBMITTED.value,
            "profile": RelocationProfile(
                userId="demo-assignment-oslo-sg-family",
                familySize=4,
                spouse={"fullName": "Daniel Jenkins", "wantsToWork": True},
                dependents=[
                    {"firstName": "Ava", "dateOfBirth": "2016-05-02"},
                    {"firstName": "Noah", "dateOfBirth": "2019-08-19"},
                ],
                primaryApplicant={
                    "fullName": "Sarah Jenkins",
                    "nationality": "Norwegian",
                    "employer": {
                        "name": "Nordic Investments",
                        "roleTitle": "Project Manager",
                        "jobLevel": "L2",
                        "salaryBand": "120k - 150k",
                    },
                    "assignment": {"startDate": "2024-11-15"},
                },
                movePlan={
                    "origin": "Oslo, Norway",
                    "destination": "Singapore",
                    "targetArrivalDate": "2024-12-01",
                    "housing": {"budgetMonthlySGD": "7000-9000"},
                    "schooling": {"budgetAnnualSGD": "30000-40000", "curriculumPreference": "IB"},
                    "movers": {"inventoryRough": "large"},
                },
                complianceDocs={
                    "hasPassportScans": False,
                    "hasEmploymentLetter": True,
                    "hasMarriageCertificate": True,
                    "hasBirthCertificates": False,
                },
            ).model_dump(mode="json"),
        },
        {
            "case_id": "demo-case-demo-emp",
            "assignment_id": "demo-assignment-demo-emp",
            "employee_identifier": "demo@relopass.com",
            "status": AssignmentStatus.ASSIGNED.value,
            "profile": RelocationProfile(
                userId="demo-assignment-demo-emp",
                familySize=2,
                spouse={"fullName": "Alex Demo", "wantsToWork": True},
                dependents=[],
                primaryApplicant={
                    "fullName": "Demo Employee",
                    "nationality": "American",
                    "employer": {"name": "Acme Corp", "roleTitle": "Engineer", "jobLevel": "L1", "salaryBand": "80k - 100k"},
                    "assignment": {"startDate": "2024-12-01"},
                },
                movePlan={
                    "origin": "San Francisco, USA",
                    "destination": "Singapore",
                    "targetArrivalDate": "2024-12-15",
                    "housing": {"budgetMonthlySGD": "5000-7000"},
                    "schooling": {"budgetAnnualSGD": "0"},
                    "movers": {"inventoryRough": "medium"},
                },
                complianceDocs={"hasPassportScans": True, "hasEmploymentLetter": False, "hasMarriageCertificate": False, "hasBirthCertificates": False},
            ).model_dump(mode="json"),
        },
        {
            "case_id": "demo-case-sg-ny-single",
            "assignment_id": "demo-assignment-sg-ny-single",
            "employee_identifier": "mark.thompson@relopass.local",
            "status": AssignmentStatus.ASSIGNED.value,
            "profile": RelocationProfile(
                userId="demo-assignment-sg-ny-single",
                familySize=1,
                spouse={"fullName": None, "wantsToWork": False},
                dependents=[],
                primaryApplicant={
                    "fullName": "Mark Thompson",
                    "nationality": "Singaporean",
                    "employer": {
                        "name": "Global Tech",
                        "roleTitle": "Senior Engineer",
                        "jobLevel": "L1",
                        "salaryBand": "90k - 110k",
                    },
                    "assignment": {"startDate": "2024-10-20"},
                },
                movePlan={
                    "origin": "Singapore",
                    "destination": "New York, USA",
                    "targetArrivalDate": "2024-11-05",
                    "housing": {"budgetMonthlySGD": "4000-6000"},
                    "schooling": {"budgetAnnualSGD": "0"},
                    "movers": {"inventoryRough": "medium"},
                },
                complianceDocs={
                    "hasPassportScans": True,
                    "hasEmploymentLetter": False,
                    "hasMarriageCertificate": False,
                    "hasBirthCertificates": False,
                },
            ).model_dump(mode="json"),
        },
    ]

    hr_profile = db.get_profile_record(hr_user_id)
    hr_company_id = hr_profile.get("company_id") if hr_profile else None
    # Legacy SQLite demo rows only: direct create_assignment without unified contact/invites.
    # Production HR/Admin APIs use create_assignment_with_contact_and_invites (see identity_canonical).
    for scenario in scenarios:
        if not db.get_assignment_by_id(scenario["assignment_id"]):
            case_profile = {
                "origin": scenario["profile"]["movePlan"]["origin"],
                "destination": scenario["profile"]["movePlan"]["destination"],
            }
            if not db.get_case_by_id(scenario["case_id"]):
                db.create_case(scenario["case_id"], hr_user_id, case_profile, company_id=hr_company_id)
            db.create_assignment(
                assignment_id=scenario["assignment_id"],
                case_id=scenario["case_id"],
                hr_user_id=hr_user_id,
                employee_user_id=None,
                employee_identifier=scenario["employee_identifier"],
                status=scenario["status"],
            )
            db.save_employee_profile(scenario["assignment_id"], scenario["profile"])

    # Seed default published HR policy for wizard auto-fill
    _seed_default_hr_policy()


def _seed_default_hr_policy() -> None:
    """Seed a default published HR policy so employees get wizard criteria auto-fill."""
    policy_id = "demo-hr-policy-001"
    if db.get_hr_policy(policy_id):
        return
    policy = {
        "policyId": policy_id,
        "policyName": "Global Relocation Policy (Demo)",
        "companyEntity": "NOR-INV-001",
        "effectiveDate": "2024-01-01",
        "expiryDate": None,
        "status": "published",
        "version": 1,
        "employeeBands": ["Band1", "Band2", "Band3", "Band4"],
        "assignmentTypes": ["Permanent", "Long-Term", "Short-Term"],
        "benefitCategories": {
            "temporaryHousing": {
                "allowed": True,
                "maxAllowed": {"min": 2000, "medium": 4000, "extensive": 6000, "premium": 9000},
                "unit": "currency",
                "currency": "USD",
                "documentationRequired": ["Lease agreement", "Receipts"],
                "preApprovalRequired": True,
            },
            "educationSupport": {
                "allowed": True,
                "maxAllowed": {"min": 10000, "medium": 20000, "extensive": 35000, "premium": 45000},
                "unit": "currency",
                "currency": "USD",
                "documentationRequired": ["School invoice", "Enrollment confirmation"],
                "preApprovalRequired": False,
            },
            "shipment": {
                "allowed": True,
                "maxAllowed": {"min": 5000, "medium": 10000, "extensive": 15000, "premium": 25000},
                "unit": "currency",
                "currency": "USD",
                "documentationRequired": ["Vendor quote", "Inventory list"],
                "preApprovalRequired": True,
            },
        },
    }
    db.create_hr_policy(policy_id, policy, created_by=None)


# Only run legacy demo seed (relocation_cases with string IDs) on SQLite, and only when explicitly allowed.
# Production Supabase uses UUID for relocation_cases.id; seeding would crash.
if _db_scheme == "sqlite" and ALLOW_LEGACY_DEMO_SEED and not DISABLE_DEMO_RESEED:
    try:
        _seed_demo_cases()
    except Exception as e:
        log.warning("Demo seed skipped or failed: %s", e)


_CANONICAL_STATUS_VALUES = {s.value for s in AssignmentStatus}


def normalize_status(status: Optional[str]) -> str:
    """
    Normalize legacy / mixed-case status values to canonical Postgres values.

    Canonical statuses (and ONLY these) are:
      created | assigned | awaiting_intake | submitted | approved | rejected | closed

    - Accepts Optional[str] and returns one of the canonical strings.
    - Case-insensitive, trims whitespace.
    - Maps legacy values like DRAFT / IN_PROGRESS / EMPLOYEE_SUBMITTED / HR_APPROVED, etc.
    - Unknown or empty values fall back to 'created' (and are logged once).
    """
    if not status:
        return AssignmentStatus.CREATED.value

    raw = str(status).strip()
    if not raw:
        return AssignmentStatus.CREATED.value

    lower = raw.lower()
    upper = raw.upper()

    # Already canonical
    if lower in _CANONICAL_STATUS_VALUES:
        return lower

    legacy_map = {
        # Old uppercase workflow statuses
        "DRAFT": AssignmentStatus.AWAITING_INTAKE.value,
        "IN_PROGRESS": AssignmentStatus.ASSIGNED.value,
        "EMPLOYEE_SUBMITTED": AssignmentStatus.SUBMITTED.value,
        "PENDING_EMPLOYEE": AssignmentStatus.AWAITING_INTAKE.value,
        "SUBMITTED_TO_HR": AssignmentStatus.SUBMITTED.value,
        "HR_APPROVED": AssignmentStatus.APPROVED.value,
        "APPROVED": AssignmentStatus.APPROVED.value,
        "HR_REJECTED": AssignmentStatus.REJECTED.value,
        "REJECTED": AssignmentStatus.REJECTED.value,
        "DONE": AssignmentStatus.CLOSED.value,
        "CLOSED": AssignmentStatus.CLOSED.value,
        # Transitional / review states get folded into submitted
        "HR_REVIEW": AssignmentStatus.SUBMITTED.value,
        "CHANGES_REQUESTED": AssignmentStatus.AWAITING_INTAKE.value,
    }

    mapped = legacy_map.get(upper)
    if mapped:
        return mapped

    # Fallback: log once per distinct unknown value and return 'created'
    log.warning("Unknown assignment status '%s', normalizing to 'created'", raw)
    return AssignmentStatus.CREATED.value


def assert_canonical_status(status: str) -> None:
    """
    Guard to ensure we only ever write canonical assignment statuses to the DB.
    Raises a 400 if a non-canonical value is about to be persisted.
    """
    if status not in _CANONICAL_STATUS_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid assignment status '{status}'. Must be one of: {sorted(_CANONICAL_STATUS_VALUES)}",
        )


# Auth dependency
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Extract user from authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Remove "Bearer " prefix if present
    token = authorization.replace("Bearer ", "")

    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Ensure admin profile record exists
    db.ensure_profile_record(
        user_id=user["id"],
        email=user.get("email"),
        role=user.get("role", UserRole.EMPLOYEE.value),
        full_name=user.get("name"),
        company_id=user.get("company"),
    )

    # Admin detection (role in profiles OR allowlisted @relopass.com)
    if _is_admin_user(user):
        user["role"] = UserRole.ADMIN.value
        user["is_admin"] = True
    else:
        user["is_admin"] = False

    # Attach user id for middleware logging (if Request is available).
    if request is not None:
        try:
            request.state.user_id = user.get("id")
        except Exception:
            # request may be a test stub; ignore
            pass

    # Admin impersonation context (server-side)
    session = db.get_admin_session(token)
    if session and session.get("target_user_id"):
        user["impersonation"] = {
            "target_user_id": session.get("target_user_id"),
            "mode": session.get("mode"),
        }

    return user


def _is_admin_user(user: Dict[str, Any]) -> bool:
    role = (user.get("role") or "").upper()
    if role == UserRole.ADMIN.value:
        return True
    profile = db.get_profile_record(user.get("id"))
    if profile and (profile.get("role") or "").upper() == UserRole.ADMIN.value:
        return True
    email = (user.get("email") or "").strip().lower()
    if email.endswith("@relopass.com") and db.is_admin_allowlisted(email):
        return True
    return False


def require_role(role: UserRole):
    """Require a specific role. ADMIN users pass all role checks."""
    def dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = user.get("role")
        if user_role == UserRole.ADMIN.value:
            return user
        if user_role != role.value:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_hr_or_employee(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Allow HR or Employee. Admin passes as HR."""
    r = user.get("role")
    if r == UserRole.ADMIN.value:
        return user
    if r in (UserRole.HR.value, UserRole.EMPLOYEE.value):
        return user
    raise HTTPException(status_code=403, detail="HR or Employee only")


def require_vendor(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require user to be a vendor. Returns user dict with vendor_id added. 403 if not a vendor."""
    vendor_id = db.get_vendor_for_user(user.get("id"))
    if not vendor_id:
        raise HTTPException(status_code=403, detail="Vendor access only")
    user = dict(user)
    user["vendor_id"] = vendor_id
    return user


class AdminImpersonateRequest(BaseModel):
    targetUserId: str
    mode: str
    reason: Optional[str] = None


class AdminReasonRequest(BaseModel):
    reason: str
    breakGlass: Optional[bool] = False
    payload: Optional[Dict[str, Any]] = None


class AdminSupportNoteRequest(BaseModel):
    note: str
    reason: str


class AdminSupportCasePatchRequest(BaseModel):
    priority: Optional[str] = None  # low | medium | high | urgent
    status: Optional[str] = None   # open | investigating | blocked | resolved
    assignee_id: Optional[str] = None
    category: Optional[str] = None  # bug | feature request | onboarding | policy question | supplier issue | other


class CompanyProfileRequest(BaseModel):
    name: str
    country: Optional[str] = None
    size_band: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    hr_contact: Optional[str] = None
    legal_name: Optional[str] = None
    website: Optional[str] = None
    hq_city: Optional[str] = None
    industry: Optional[str] = None
    default_destination_country: Optional[str] = None
    support_email: Optional[str] = None
    default_working_location: Optional[str] = None


class DossierQuestionDTO(BaseModel):
    id: str
    question_text: str
    answer_type: str
    options: Optional[List[str]] = None
    is_mandatory: bool
    domain: str
    question_key: Optional[str] = None
    source: str = "library"


class DossierQuestionsResponse(BaseModel):
    destination_country: Optional[str]
    questions: List[DossierQuestionDTO]
    answers: Dict[str, Any]
    mandatory_unanswered_count: int
    is_step5_complete: bool
    sources_used: List[Dict[str, Any]] = []


class DossierAnswerItem(BaseModel):
    question_id: Optional[str] = None
    case_question_id: Optional[str] = None
    answer: Any


class DossierAnswersRequest(BaseModel):
    case_id: str
    answers: List[DossierAnswerItem]


class DossierSearchSuggestionsRequest(BaseModel):
    case_id: str


class DossierSuggestionDTO(BaseModel):
    question_text: str
    answer_type: str
    sources: List[Dict[str, Any]]


class DossierSearchSuggestionsResponse(BaseModel):
    destination_country: Optional[str]
    sources: List[Dict[str, Any]]
    suggestions: List[DossierSuggestionDTO]


class DossierCaseQuestionRequest(BaseModel):
    case_id: str
    question_text: str
    answer_type: str
    options: Optional[List[str]] = None
    is_mandatory: bool = False
    sources: Optional[List[Dict[str, Any]]] = None


class GuidanceGenerateRequest(BaseModel):
    case_id: str
    mode: Optional[str] = None



class HrFeedbackRequest(BaseModel):
    message: str


class ReadinessChecklistPatchRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class ReadinessMilestonePatchRequest(BaseModel):
    completed: bool
    notes: Optional[str] = None


def _require_reason(reason: Optional[str]) -> None:
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required for admin actions")


def _deny_if_impersonating(user: Dict[str, Any]) -> None:
    if user.get("impersonation"):
        raise HTTPException(status_code=403, detail="View-as mode is read-only. Use admin actions instead.")


def _effective_user(user: Dict[str, Any], expected_role: Optional[UserRole] = None) -> Dict[str, Any]:
    imp = user.get("impersonation")
    if not imp:
        return user
    target = db.get_user_by_id(imp.get("target_user_id"))
    if not target:
        return user
    if expected_role and target.get("role") != expected_role.value:
        return user
    return target


def _normalize_destination_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().upper()
    if normalized in ("SG", "SINGAPORE"):
        return "SG"
    if normalized in ("US", "USA", "UNITED STATES"):
        return "US"
    return None


def _build_profile_snapshot(draft: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "relocationBasics": draft.get("relocationBasics") or {},
        "employeeProfile": draft.get("employeeProfile") or {},
        "familyMembers": draft.get("familyMembers") or {},
        "assignmentContext": draft.get("assignmentContext") or {},
    }


def _require_case_access(case_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    assignment = db.get_assignment_by_case_id(case_id) or db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found or not visible under RLS")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    eid = effective.get("id")
    visible = False
    if is_employee and eid is not None and emp_id == eid:
        visible = True
    if is_hr and (effective.get("is_admin") or (eid is not None and hr_id == eid)):
        visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Assignment not found or not visible under RLS")
    return {"assignment": assignment, "effective_user": effective}


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ReloPass API"}


def _best_effort_reconcile_employee_assignments(
    *,
    context: str,
    user_id: str,
    email: Optional[str],
    username: Optional[str],
    role: str,
    request_id: Optional[str],
) -> None:
    """Run canonical claim/link reconcile; must not break dashboard or employee routes."""
    try:
        reconcile_pending_assignment_claims(
            db,
            user_id=user_id,
            email=email,
            username=username,
            role=role,
            request_id=request_id,
            emit_side_effects=True,
        )
    except Exception as exc:
        log.warning("%s claim_reconcile skipped error=%s", context, exc)


@app.post("/api/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest):
    """Register a new user with username or email and role."""
    try:
        username = request.username.strip() if request.username else None
        email_raw = request.email.strip() if request.email else None
        email = email_raw.lower() if email_raw else None

        if not username and not email:
            raise HTTPException(
                status_code=400,
                detail=err_detail(IdentityErrorCode.AUTH_IDENTIFIER_REQUIRED, "Provide a username or email"),
            )

        if username:
            if not re.match(r"^[A-Za-z0-9_]{3,30}$", username):
                identity_event("identity.auth.signup.failed", reason="AUTH_USERNAME_INVALID_FORMAT")
                raise HTTPException(status_code=400, detail="Username must be 3-30 chars, alphanumeric or underscore")
            if db.get_user_by_username(username):
                identity_event(
                    "identity.auth.signup.failed",
                    reason="AUTH_USERNAME_TAKEN",
                    principal_fingerprint=principal_fingerprint(None, username),
                )
                raise HTTPException(
                    status_code=400,
                    detail=err_detail(
                        IdentityErrorCode.AUTH_USERNAME_TAKEN,
                        "This username is already taken. Choose another or sign in.",
                    ),
                )

        if email:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                identity_event("identity.auth.signup.failed", reason="AUTH_EMAIL_INVALID_FORMAT")
                raise HTTPException(status_code=400, detail="Invalid email format")
            # Only real auth accounts (public.users) block signup — not employee_contacts / assignments / invites.
            if db.get_user_by_email(email):
                identity_event(
                    "identity.auth.signup.failed",
                    reason="AUTH_EMAIL_TAKEN",
                    principal_fingerprint=principal_fingerprint(email, None),
                )
                raise HTTPException(
                    status_code=400,
                    detail=err_detail(
                        IdentityErrorCode.AUTH_EMAIL_TAKEN,
                        "An account with this email already exists. Try logging in instead.",
                    ),
                )

        if not request.password:
            raise HTTPException(status_code=400, detail="Password required")

        # Password hashing (placeholder for stronger policy/verification)
        from passlib.context import CryptContext
        # Use PBKDF2 to avoid bcrypt backend issues on Windows.
        pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        password_hash = pwd_context.hash(request.password)

        role = request.role
        if role == UserRole.ADMIN and (not email or not email.endswith("@relopass.com") or not db.is_admin_allowlisted(email)):
            role = UserRole.EMPLOYEE

        user_id = str(uuid.uuid4())
        created = db.create_user(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            role=role.value,
            name=request.name,
        )
        if not created:
            identity_event(
                "identity.auth.signup.failed",
                reason="AUTH_USER_CREATE_FAILED",
                principal_fingerprint=principal_fingerprint(email, username),
            )
            raise HTTPException(
                status_code=400,
                detail=err_detail(
                    IdentityErrorCode.AUTH_USER_CREATE_FAILED,
                    "Could not create this account. The email or username may already be registered.",
                ),
            )

        token = str(uuid.uuid4())
        db.create_session(token, user_id)
        db.ensure_profile_record(
            user_id=user_id,
            email=email,
            role=role.value,
            full_name=request.name,
            company_id=None,
        )

        reconciliation_payload = None
        if role == UserRole.EMPLOYEE and (email or username):
            try:
                claim_res = reconcile_pending_assignment_claims(
                    db,
                    user_id=user_id,
                    email=email,
                    username=username,
                    role=role.value,
                    request_id=None,
                    emit_side_effects=True,
                )
                identity_event(
                    "identity.auth.signup.reconcile",
                    auth_user_id=user_id,
                    principal_fingerprint=principal_fingerprint(email, username),
                    linked_contacts=len(claim_res.linked_contact_ids),
                    new_attachments=len(claim_res.newly_attached_assignment_ids),
                    skipped_revoked_invites=claim_res.skipped_revoked_invites,
                    skipped_contacts_linked_to_other_user=claim_res.skipped_contacts_linked_to_other_user,
                    skipped_assignments_linked_to_other_user=claim_res.skipped_assignments_linked_to_other_user,
                    skipped_already_linked_same_user=claim_res.skipped_already_linked_same_user,
                )
                rec = claim_res.to_api_dict()
                if rec.get("linkedContactIds") or rec.get("attachedAssignmentIds") or rec.get("message"):
                    reconciliation_payload = PostSignupReconciliation(
                        linkedContactIds=rec.get("linkedContactIds") or [],
                        attachedAssignmentIds=rec.get("attachedAssignmentIds") or [],
                        skippedContactsLinkedToOtherUser=int(rec.get("skippedContactsLinkedToOtherUser") or 0),
                        skippedAssignmentsLinkedToOtherUser=int(
                            rec.get("skippedAssignmentsLinkedToOtherUser") or 0
                        ),
                        skippedRevokedInvites=int(rec.get("skippedRevokedInvites") or 0),
                        skippedAlreadyLinkedSameUser=int(rec.get("skippedAlreadyLinkedSameUser") or 0),
                        headline=rec.get("headline"),
                        message=rec.get("message"),
                    )
            except Exception as rec_exc:
                log.warning("signup_reconciliation skipped user_id=%s error=%s", user_id[:8], rec_exc)
                identity_event(
                    "identity.auth.signup.reconcile",
                    auth_user_id=user_id,
                    outcome="error",
                    error_type=type(rec_exc).__name__,
                )

        identity_event(
            "identity.auth.signup.ok",
            auth_user_id=user_id,
            role=role.value,
            principal_fingerprint=principal_fingerprint(email, username),
        )
        log.info("auth_register success user_id=%s username=%s", user_id[:8], username)
        if email:
            from .services.supabase_auth_sync import sync_relopass_user_to_supabase_auth

            sync_relopass_user_to_supabase_auth(
                email,
                request.password,
                relopass_user_id=user_id,
                full_name=request.name,
            )
        return LoginResponse(
            token=token,
            user=UserResponse(
                id=user_id,
                username=username,
                email=email,
                role=role,
                name=request.name,
                company=None,
            ),
            reconciliation=reconciliation_payload,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("auth_register unexpected error email=%s", getattr(request, "email", ""))
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    """Invalidate the current session. Client should also clear localStorage."""
    if not authorization:
        return {"success": True}
    token = authorization.replace("Bearer ", "").strip()
    if token:
        db.delete_session_by_token(token)
        log.info("auth_logout token_invalidated")
    return {"success": True}


AUTH_PERF_DEBUG = os.getenv("AUTH_PERF_DEBUG", "").lower() in ("1", "true", "yes")
PERF_DEBUG = os.getenv("PERF_DEBUG", "").lower() in ("1", "true", "yes")


def _log_auth_perf(endpoint: str, request_id: Optional[str], user_id: Optional[str], total_duration_ms: float, status_code: int):
    """Structured JSON log for auth perf (when AUTH_PERF_DEBUG=1)."""
    if not AUTH_PERF_DEBUG:
        return
    log.info(
        "[auth-perf] %s",
        _json.dumps({
            "endpoint": endpoint,
            "request_id": request_id or "",
            "user_id": (user_id or "")[:8] if user_id else "",
            "total_duration_ms": round(total_duration_ms, 2),
            "status_code": status_code,
        }),
    )


@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, req: Request):
    """Login with username or email + password."""
    t0 = time.perf_counter()
    request_id = getattr(req.state, "request_id", None) or ""
    identifier = (request.identifier or "").strip()
    if not identifier:
        log.warning("auth_login fail identifier_empty")
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_IDENTIFIER_REQUIRED",
            request_id=request_id or None,
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(IdentityErrorCode.AUTH_IDENTIFIER_REQUIRED, "Enter your username or email"),
        )
    user = db.get_user_by_identifier(identifier)
    if not user:
        log.warning("auth_login fail user_not_found identifier=%s", identifier[:3] + "***")
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_USER_NOT_FOUND",
            request_id=request_id or None,
            principal_fingerprint=principal_fingerprint_from_login_identifier(identifier),
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(
                IdentityErrorCode.AUTH_USER_NOT_FOUND,
                "Invalid username or email. Check spelling or create an account.",
            ),
        )

    if not user.get("password_hash"):
        log.warning("auth_login fail no_password user_id=%s", user.get("id", "")[:8])
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_NO_PASSWORD",
            request_id=request_id or None,
            auth_user_id=user.get("id"),
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(IdentityErrorCode.AUTH_NO_PASSWORD, "Invalid credentials"),
        )

    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    if not pwd_context.verify(request.password, user["password_hash"]):
        log.warning("auth_login fail wrong_password user_id=%s", user.get("id", "")[:8])
        identity_event(
            "identity.auth.signin.failed",
            reason="AUTH_WRONG_PASSWORD",
            request_id=request_id or None,
            auth_user_id=user.get("id"),
        )
        raise HTTPException(
            status_code=401,
            detail=err_detail(IdentityErrorCode.AUTH_WRONG_PASSWORD, "Incorrect password. Try again or reset."),
        )

    token = str(uuid.uuid4())
    db.create_session(token, user["id"])

    # Ensure profile record is synced
    db.ensure_profile_record(
        user_id=user["id"],
        email=user.get("email"),
        role=user.get("role", UserRole.EMPLOYEE.value),
        full_name=user.get("name"),
        company_id=user.get("company"),
    )
    profile = db.get_profile_record(user["id"])

    # Admin override if allowlisted
    effective_role = UserRole(user["role"])
    if _is_admin_user(user):
        effective_role = UserRole.ADMIN

    reconciliation_payload = None
    if effective_role == UserRole.EMPLOYEE:
        try:
            claim_res = reconcile_pending_assignment_claims(
                db,
                user_id=user["id"],
                email=user.get("email"),
                username=user.get("username"),
                role=user.get("role") or UserRole.EMPLOYEE.value,
                request_id=request_id or None,
                emit_side_effects=True,
            )
            identity_event(
                "identity.auth.signin.reconcile",
                request_id=request_id or None,
                auth_user_id=user["id"],
                principal_fingerprint=principal_fingerprint(user.get("email"), user.get("username")),
                linked_contacts=len(claim_res.linked_contact_ids),
                new_attachments=len(claim_res.newly_attached_assignment_ids),
                skipped_revoked_invites=claim_res.skipped_revoked_invites,
                skipped_contacts_linked_to_other_user=claim_res.skipped_contacts_linked_to_other_user,
                skipped_assignments_linked_to_other_user=claim_res.skipped_assignments_linked_to_other_user,
                skipped_already_linked_same_user=claim_res.skipped_already_linked_same_user,
            )
            # Only surface UX payload when we newly attached assignments (avoid repeat banners).
            if claim_res.newly_attached_assignment_ids:
                rec = claim_res.to_api_dict()
                reconciliation_payload = PostSignupReconciliation(
                    linkedContactIds=rec.get("linkedContactIds") or [],
                    attachedAssignmentIds=rec.get("attachedAssignmentIds") or [],
                    skippedContactsLinkedToOtherUser=int(rec.get("skippedContactsLinkedToOtherUser") or 0),
                    skippedAssignmentsLinkedToOtherUser=int(
                        rec.get("skippedAssignmentsLinkedToOtherUser") or 0
                    ),
                    skippedRevokedInvites=int(rec.get("skippedRevokedInvites") or 0),
                    skippedAlreadyLinkedSameUser=int(rec.get("skippedAlreadyLinkedSameUser") or 0),
                    headline=rec.get("headline"),
                    message=rec.get("message"),
                )
        except Exception as rec_exc:
            log.warning("login claim_link skipped user_id=%s error=%s", user["id"][:8], rec_exc)
            identity_event(
                "identity.auth.signin.reconcile",
                request_id=request_id or None,
                auth_user_id=user["id"],
                outcome="error",
                error_type=type(rec_exc).__name__,
            )

    identity_event(
        "identity.auth.signin.ok",
        request_id=request_id or None,
        auth_user_id=user["id"],
        role=effective_role.value,
        principal_fingerprint=principal_fingerprint(user.get("email"), user.get("username")),
    )
    log.info("auth_login success user_id=%s", user["id"][:8])
    if user.get("email"):
        from .services.supabase_auth_sync import sync_relopass_user_to_supabase_auth

        sync_relopass_user_to_supabase_auth(
            user["email"],
            request.password,
            relopass_user_id=user["id"],
            full_name=user.get("name"),
        )
    _log_auth_perf(
        "/api/auth/login",
        request_id,
        user["id"],
        (time.perf_counter() - t0) * 1000,
        200,
    )
    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            username=user.get("username"),
            email=user.get("email"),
            role=effective_role,
            name=user.get("name"),
            company=profile.get("company_id") if profile else user.get("company"),
        ),
        reconciliation=reconciliation_payload,
    )


def _log_endpoint_perf(endpoint: str, request_id: Optional[str], user_id: Optional[str], total_duration_ms: float, status_code: int, db_duration_ms: Optional[float] = None):
    """Structured JSON log for endpoint perf (when PERF_DEBUG=1)."""
    if not PERF_DEBUG:
        return
    payload = {
        "endpoint": endpoint,
        "request_id": request_id or "",
        "user_id": (user_id or "")[:8] if user_id else "",
        "total_duration_ms": round(total_duration_ms, 2),
        "status_code": status_code,
    }
    if db_duration_ms is not None:
        payload["db_duration_ms"] = round(db_duration_ms, 2)
    log.info("[endpoint-perf] %s", _json.dumps(payload))


# ---------------------------------------------------------------------------
# Admin console endpoints
# ---------------------------------------------------------------------------
@app.get("/api/admin/context")
def get_admin_context(user: Dict[str, Any] = Depends(require_admin)):
    return {
        "isAdmin": True,
        "impersonation": user.get("impersonation"),
    }


@app.post("/api/admin/impersonate/start")
def start_impersonation(
    request: AdminImpersonateRequest,
    user: Dict[str, Any] = Depends(require_admin),
    authorization: Optional[str] = Header(None),
):
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    mode = request.mode.lower()
    if mode not in ("hr", "employee"):
        raise HTTPException(status_code=400, detail="Invalid impersonation mode")
    db.set_admin_session(token, user["id"], request.targetUserId, mode)
    db.log_audit(
        actor_user_id=user["id"],
        action_type="VIEW_AS",
        target_type="profile",
        target_id=request.targetUserId,
        reason=request.reason,
        metadata={"mode": mode},
    )
    return {"ok": True, "impersonation": {"targetUserId": request.targetUserId, "mode": mode}}


@app.post("/api/admin/impersonate/stop")
def stop_impersonation(
    user: Dict[str, Any] = Depends(require_admin),
    authorization: Optional[str] = Header(None),
):
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    db.clear_admin_session(token)
    db.log_audit(
        actor_user_id=user["id"],
        action_type="VIEW_AS",
        target_type="profile",
        target_id=None,
        reason="Stop impersonation",
        metadata={},
    )
    return {"ok": True}


@app.get("/api/admin/companies")
def list_companies(q: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_admin)):
    items = db.get_admin_company_index(q)
    log.info("admin_companies list query=%s count=%s", q, len(items))
    db.log_audit(user["id"], "READ", "company", None, None, {"query": q})
    return {"companies": items}


@app.get("/api/admin/companies/{company_id}")
def get_company_detail(
    company_id: str,
    request: Request,
    user: Dict[str, Any] = Depends(require_admin),
):
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    log.info(
        "admin_company_detail company_id=%s user_id=%s request_id=%s",
        company_id, user.get("id"), request_id,
    )
    company = db.get_company(company_id)
    if not company:
        log.info("admin_company_detail company_id=%s found=0 checking orphan request_id=%s", company_id, request_id)
        # Orphan: company_id not in companies table but may appear in hr_users/relocation_cases
        with db.engine.connect() as conn:
            has_hr = conn.execute(
                text("SELECT 1 FROM hr_users WHERE company_id = :cid LIMIT 1"), {"cid": company_id}
            ).fetchone()
            has_case = conn.execute(
                text("SELECT 1 FROM relocation_cases WHERE company_id = :cid LIMIT 1"), {"cid": company_id}
            ).fetchone()
        if has_hr or has_case:
            company = {
                "id": company_id,
                "name": company_id,
                "country": None,
                "size_band": None,
                "address": None,
                "phone": None,
                "hr_contact": None,
                "created_at": None,
                "updated_at": None,
                "status": None,
                "plan_tier": None,
                "missing_from_registry": True,
            }
        else:
            log.warning("admin_company_detail company_id=%s not_found request_id=%s", company_id, request_id)
            raise HTTPException(status_code=404, detail="Company not found")
    try:
        hr_users = db.list_hr_users_with_profiles(company_id)
        employees_raw = db.list_employees_with_profiles(company_id)
        employees = [
            {
                "id": e["id"],
                "company_id": e["company_id"],
                "profile_id": e["profile_id"],
                "name": e.get("full_name") or e.get("email") or e.get("profile_id"),
                "email": e.get("email"),
                "status": e.get("status") or "active",
                "created_at": e.get("created_at"),
            }
            for e in employees_raw
        ]
        assignments = db.list_assignments_for_company_with_details(company_id)
        policies_data = db.get_admin_policies_by_company(company_id)
        if policies_data and policies_data.get("policies"):
            policies = [
                {
                    "policy_id": p["policy_id"],
                    "title": p.get("title"),
                    "latest_version": p.get("latest_version_number"),
                    "status": p.get("latest_version_status") or p.get("extraction_status") or "draft",
                    "published": bool(p.get("published_version_id")),
                }
                for p in policies_data["policies"]
            ]
        else:
            policies = []
        summary = {
            "hr_users_count": len(hr_users),
            "employee_count": len(employees),
            "assignments_count": len(assignments),
            "policies_count": len(policies),
        }
        orphan_diagnostics = db.get_company_detail_orphan_diagnostics(company_id)
        log.info(
            "admin_company_detail company_id=%s found=1 hr=%s employees=%s assignments=%s policies=%s request_id=%s",
            company_id, len(hr_users), len(employees), len(assignments), len(policies), request_id,
        )
        db.log_audit(user["id"], "READ", "company", company_id, None, {"detail": True})
        return {
            "company": company,
            "summary": summary,
            "hr_users": hr_users,
            "employees": employees,
            "assignments": assignments,
            "policies": policies,
            "counts_summary": summary,
            "orphan_diagnostics": orphan_diagnostics,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception(
            "admin_company_detail company_id=%s error=%s request_id=%s",
            company_id, type(e).__name__, request_id,
        )
        raise


class AdminCreateCompanyRequest(BaseModel):
    name: str
    country: Optional[str] = None
    size_band: Optional[str] = None
    status: Optional[str] = None
    plan_tier: Optional[str] = None
    hr_seat_limit: Optional[int] = None
    employee_seat_limit: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    hr_contact: Optional[str] = None
    support_email: Optional[str] = None


class AdminUpdateCompanyRequest(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    size_band: Optional[str] = None
    status: Optional[str] = None
    plan_tier: Optional[str] = None
    hr_seat_limit: Optional[int] = None
    employee_seat_limit: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    hr_contact: Optional[str] = None
    support_email: Optional[str] = None


@app.post("/api/admin/companies", status_code=201)
def create_company(body: AdminCreateCompanyRequest, user: Dict[str, Any] = Depends(require_admin)):
    company_id = str(uuid.uuid4())
    db.create_company(
        company_id=company_id,
        name=body.name,
        country=body.country,
        size_band=body.size_band,
        address=body.address,
        phone=body.phone,
        hr_contact=body.hr_contact,
        support_email=body.support_email,
        status=body.status,
        plan_tier=body.plan_tier,
        hr_seat_limit=body.hr_seat_limit,
        employee_seat_limit=body.employee_seat_limit,
    )
    company = db.get_company(company_id)
    log.info("admin company created id=%s name=%s by=%s", company_id, body.name, user.get("id"))
    db.log_audit(user["id"], "CREATE", "company", company_id, None, {"name": body.name})
    return {"company": company}


@app.patch("/api/admin/companies/{company_id}")
def update_company(company_id: str, body: AdminUpdateCompanyRequest, user: Dict[str, Any] = Depends(require_admin)):
    existing = db.get_company(company_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return {"company": existing}
    updated = db.update_company(company_id, **payload)
    if not updated:
        return {"company": existing}
    company = db.get_company(company_id)
    log.info("admin company updated id=%s by=%s keys=%s", company_id, user.get("id"), list(payload.keys()))
    db.log_audit(user["id"], "UPDATE", "company", company_id, None, payload)
    return {"company": company}


@app.post("/api/admin/companies/{company_id}/deactivate")
def deactivate_company(company_id: str, user: Dict[str, Any] = Depends(require_admin)):
    existing = db.get_company(company_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    if (existing.get("status") or "").lower() == "inactive":
        return {"company": existing, "message": "Already inactive"}
    db.deactivate_company(company_id)
    company = db.get_company(company_id)
    log.info("admin company deactivated id=%s by=%s", company_id, user.get("id"))
    db.log_audit(user["id"], "DEACTIVATE", "company", company_id, None, {})
    return {"company": company, "message": "Deactivated"}


@app.get("/api/admin/users")
def list_users(
    q: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
):
    people, summary = db.get_admin_people_index(company_id=company_id, query=q, role=role)
    log.info("admin_users list company_id=%s role=%s query=%s count=%s", company_id, role, q, summary.get("count"))
    db.log_audit(user["id"], "READ", "profile", None, None, {"query": q, "company_id": company_id, "role": role})
    return {"profiles": people, "summary": summary}


@app.get("/api/admin/people")
def list_people(
    company_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    query: Optional[str] = Query(None, alias="q"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin people list with company, role, and text filters. Returns admin-safe fields including company_name, status."""
    people, summary = db.get_admin_people_index(company_id=company_id, query=query, role=role)
    db.log_audit(user["id"], "READ", "people", None, None, {"company_id": company_id, "role": role, "query": query})
    return {"people": people, "summary": summary}


class AdminCreatePersonRequest(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = None
    company_id: Optional[str] = None


class AdminUpdatePersonRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    company_id: Optional[str] = None
    status: Optional[str] = None


class AdminAssignCompanyRequest(BaseModel):
    company_id: str


class AdminSetRoleRequest(BaseModel):
    role: str


@app.post("/api/admin/people", status_code=201)
def create_person(
    body: AdminCreatePersonRequest,
    request: Request,
    user: Dict[str, Any] = Depends(require_admin),
):
    email = (body.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email required")
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    person_id = str(uuid.uuid4())
    try:
        role = (body.role or "EMPLOYEE").strip().upper()
        db.create_profile(
            person_id=person_id,
            email=email,
            full_name=body.full_name,
            role=role,
            company_id=body.company_id,
        )
        if role == "HR" and body.company_id:
            db.ensure_hr_user_for_profile(person_id, body.company_id)
        if role in ("EMPLOYEE", "EMPLOYEE_USER") and body.company_id:
            db.ensure_employee_for_profile(person_id, body.company_id)
    except IntegrityError as e:
        log.warning(
            "admin_create_person conflict request_id=%s email=%s company_id=%s error=%r",
            request_id,
            email,
            body.company_id,
            e,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": "A person with this email already exists.", "request_id": request_id},
        )
    except Exception as e:
        log.error(
            "admin_create_person failed request_id=%s email=%s full_name=%s role=%s company_id=%s error=%r",
            request_id,
            email,
            body.full_name,
            body.role,
            body.company_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to create person", "request_id": request_id},
        )
    profile = db.get_profile_record(person_id)
    log.info(
        "admin_create_person success request_id=%s id=%s email=%s company_id=%s by=%s",
        request_id,
        person_id,
        email,
        body.company_id,
        user.get("id"),
    )
    db.log_audit(user["id"], "CREATE", "profile", person_id, None, {"email": email})
    return {"person": profile}


@app.patch("/api/admin/people/{person_id}")
def update_person(person_id: str, body: AdminUpdatePersonRequest, user: Dict[str, Any] = Depends(require_admin)):
    existing = db.get_profile_record(person_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return {"person": existing}
    updated = db.update_profile(person_id, **payload)
    if not updated:
        return {"person": existing}
    profile = db.get_profile_record(person_id)
    db.log_audit(user["id"], "UPDATE", "profile", person_id, None, payload)
    return {"person": profile}


@app.post("/api/admin/people/{person_id}/assign-company")
def assign_person_company(person_id: str, body: AdminAssignCompanyRequest, user: Dict[str, Any] = Depends(require_admin)):
    existing = db.get_profile_record(person_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    db.set_profile_company(person_id, body.company_id)
    if (existing.get("role") or "").upper() == "HR":
        db.ensure_hr_user_for_profile(person_id, body.company_id)
    if (existing.get("role") or "").upper() in ("EMPLOYEE", "EMPLOYEE_USER"):
        db.ensure_employee_for_profile(person_id, body.company_id)
    profile = db.get_profile_record(person_id)
    db.log_audit(user["id"], "ASSIGN_COMPANY", "profile", person_id, None, {"company_id": body.company_id})
    return {"person": profile}


@app.post("/api/admin/people/{person_id}/set-role")
def set_person_role(person_id: str, body: AdminSetRoleRequest, user: Dict[str, Any] = Depends(require_admin)):
    existing = db.get_profile_record(person_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    db.set_profile_role(person_id, body.role)
    if (body.role or "").strip().upper() == "HR" and existing.get("company_id"):
        db.ensure_hr_user_for_profile(person_id, existing["company_id"])
    if (body.role or "").strip().upper() in ("EMPLOYEE", "EMPLOYEE_USER") and existing.get("company_id"):
        db.ensure_employee_for_profile(person_id, existing["company_id"])
    profile = db.get_profile_record(person_id)
    db.log_audit(user["id"], "SET_ROLE", "profile", person_id, None, {"role": body.role})
    return {"person": profile}


@app.post("/api/admin/people/{person_id}/deactivate")
def deactivate_person(person_id: str, user: Dict[str, Any] = Depends(require_admin)):
    existing = db.get_profile_record(person_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    db.deactivate_profile(person_id)
    profile = db.get_profile_record(person_id)
    db.log_audit(user["id"], "DEACTIVATE", "profile", person_id, None, {})
    return {"person": profile}


@app.get("/api/admin/employees")
def list_employees(company_id: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_admin)):
    if company_id:
        db.ensure_employees_for_company(company_id)
        db.ensure_directory_from_assignments_for_company(company_id)
        items = db.list_employees_with_profiles(company_id)
    else:
        items = db.list_employees(company_id)
    db.log_audit(user["id"], "READ", "employee", None, None, {"company_id": company_id})
    return {"employees": items}


@app.get("/api/admin/hr-users")
def list_hr_users(company_id: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_admin)):
    if company_id:
        db.ensure_hr_users_for_company(company_id)
        items = db.list_hr_users_with_profiles(company_id)
    else:
        items = db.list_hr_users(company_id)
    db.log_audit(user["id"], "READ", "hr_user", None, None, {"company_id": company_id})
    return {"hr_users": items}


@app.get("/api/admin/relocations")
def list_relocations(
    company_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
):
    items = db.list_relocation_cases(company_id=company_id, status=status)
    db.log_audit(user["id"], "READ", "relocation_case", None, None, {"company_id": company_id, "status": status})
    return {"relocations": items}


@app.get("/api/admin/assignments")
def list_admin_assignments(
    company_id: Optional[str] = Query(None),
    employee_user_id: Optional[str] = Query(None),
    employee_search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    destination_country: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
):
    items = db.list_admin_assignments(
        company_id=company_id,
        employee_user_id=employee_user_id,
        employee_search=employee_search,
        status=status,
        destination_country=destination_country,
    )
    db.log_audit(
        user["id"], "READ", "admin_assignments", None, None,
        {"company_id": company_id, "status": status, "destination": destination_country},
    )
    return {"assignments": items}


@app.get("/api/admin/assignments/{assignment_id}")
def get_admin_assignment_detail(assignment_id: str, user: Dict[str, Any] = Depends(require_admin)):
    detail = db.get_admin_assignment_detail(assignment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.log_audit(user["id"], "READ", "admin_assignment_detail", assignment_id, None, {})
    return {"assignment": detail}


class AdminReassignEmployeeCompanyRequest(BaseModel):
    reason: str
    company_id: str


class AdminReassignHrOwnerRequest(BaseModel):
    reason: str
    hr_user_id: str


class AdminFixCompanyLinkageRequest(BaseModel):
    reason: str
    company_id: str


@app.patch("/api/admin/assignments/{assignment_id}/reassign-employee-company")
def admin_reassign_employee_company(
    assignment_id: str,
    request: AdminReassignEmployeeCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    _require_reason(request.reason)
    detail = db.get_admin_assignment_detail(assignment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Assignment not found")
    emp_id = detail.get("employee_user_id")
    if not emp_id:
        raise HTTPException(status_code=400, detail="Assignment has no linked employee")
    db.admin_reassign_employee_company(emp_id, request.company_id)
    db.log_audit(user["id"], "REASSIGN_EMPLOYEE_COMPANY", "assignment", assignment_id, request.reason, {"company_id": request.company_id})
    return {"ok": True}


@app.patch("/api/admin/assignments/{assignment_id}/reassign-hr-owner")
def admin_reassign_hr_owner(
    assignment_id: str,
    request: AdminReassignHrOwnerRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    _require_reason(request.reason)
    detail = db.get_admin_assignment_detail(assignment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.admin_reassign_hr_owner(assignment_id, request.hr_user_id)
    db.log_audit(user["id"], "REASSIGN_HR_OWNER", "assignment", assignment_id, request.reason, {"hr_user_id": request.hr_user_id})
    return {"ok": True}


@app.patch("/api/admin/assignments/{assignment_id}/fix-company-linkage")
def admin_fix_assignment_company_linkage(
    assignment_id: str,
    request: AdminFixCompanyLinkageRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    _require_reason(request.reason)
    detail = db.get_admin_assignment_detail(assignment_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.admin_fix_assignment_company_linkage(assignment_id, request.company_id)
    db.log_audit(user["id"], "FIX_COMPANY_LINKAGE", "assignment", assignment_id, request.reason, {"company_id": request.company_id})
    return {"ok": True}


class AdminAssignmentStatusRequest(BaseModel):
    status: str


@app.patch("/api/admin/assignments/{assignment_id}/status")
def admin_update_assignment_status(
    assignment_id: str,
    body: AdminAssignmentStatusRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: set assignment status (e.g. Save status change or Archive)."""
    if not db.get_assignment_by_id(assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    status = (body.status or "").strip()
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    try:
        db.update_assignment_status(assignment_id, status, request_id=None)
    except Exception as e:
        log.exception("admin_update_assignment_status: update_assignment_status failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to update assignment status. Please try again or contact support.",
        ) from e
    db.log_audit(user["id"], "UPDATE_STATUS", "assignment", assignment_id, None, {"status": status})
    return {"ok": True, "status": status}


class AdminCreateAssignmentRequest(BaseModel):
    company_id: str
    hr_user_id: str
    employee_user_id: Optional[str] = None
    employee_identifier: Optional[str] = None
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None
    destination_country: Optional[str] = None


@app.post("/api/admin/assignments")
def admin_create_assignment(
    body: AdminCreateAssignmentRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: create a new case and assignment for a company (minimal case, assigned status)."""
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    if not db.get_profile_record(body.hr_user_id):
        raise HTTPException(status_code=404, detail="HR profile not found")
    hr_users = db.list_hr_users(body.company_id)
    if not any(h.get("profile_id") == body.hr_user_id for h in hr_users):
        raise HTTPException(status_code=400, detail="HR user is not in the selected company")
    employee_user_id: Optional[str] = None
    employee_identifier = (body.employee_identifier or "").strip() or None
    if body.employee_user_id:
        emp = db.get_employee_by_profile_for_company(body.employee_user_id, body.company_id)
        if not emp:
            raise HTTPException(status_code=400, detail="Employee is not in the selected company")
        employee_user_id = body.employee_user_id
        employee_identifier = (emp.get("email") or emp.get("full_name") or employee_identifier or "admin-created")
    elif employee_identifier:
        # Link to existing user by email/username so employee sees assignment when they log in
        existing_user = db.get_user_by_identifier(employee_identifier)
        if existing_user:
            employee_user_id = existing_user["id"]
    if not employee_identifier:
        employee_identifier = "admin-created"
    employee_first_name = (body.employee_first_name or "").strip() or None
    employee_last_name = (body.employee_last_name or "").strip() or None
    case_id = str(uuid.uuid4())
    db.create_case(case_id, body.hr_user_id, {}, company_id=body.company_id)
    uar = create_assignment_with_contact_and_invites(
        db,
        company_id=body.company_id,
        hr_user_id=body.hr_user_id,
        case_id=case_id,
        employee_identifier_raw=employee_identifier,
        employee_first_name=employee_first_name,
        employee_last_name=employee_last_name,
        employee_user_id=employee_user_id,
        assignment_status=AssignmentStatus.ASSIGNED.value,
        request_id=None,
        observability_channel="admin",
    )
    assignment_id = uar.assignment_id
    if body.destination_country:
        db.update_relocation_case_host_country(case_id, body.destination_country)
    db.log_audit(user["id"], "CREATE", "assignment", assignment_id, None, {"case_id": case_id, "company_id": body.company_id, "hr_user_id": body.hr_user_id})
    return {"ok": True, "assignment_id": assignment_id, "case_id": case_id}


@app.get("/api/admin/data-integrity/overview")
def get_data_integrity_overview(user: Dict[str, Any] = Depends(require_admin)):
    """Admin: entity counts and orphan flags for data-integrity dashboard."""
    data = db.get_data_integrity_overview()
    db.log_audit(user["id"], "READ", "data_integrity_overview", None, None, {})
    return data


# ---------------------------------------------------------------------------
# Admin reconciliation (repair missing links; no destructive cleanup)
# ---------------------------------------------------------------------------

class ReconciliationLinkPersonCompanyRequest(BaseModel):
    profile_id: str
    company_id: str


class ReconciliationLinkAssignmentCompanyRequest(BaseModel):
    assignment_id: str
    company_id: str
    reason: str


class ReconciliationLinkAssignmentPersonRequest(BaseModel):
    assignment_id: str
    profile_id: str


class ReconciliationLinkPolicyCompanyRequest(BaseModel):
    policy_id: str
    company_id: str


@app.get("/api/admin/reconciliation/report")
def get_reconciliation_report(user: Dict[str, Any] = Depends(require_admin)):
    """Admin: full reconciliation report (companies, people, assignments, policies, missing links)."""
    data = db.get_reconciliation_report()
    db.log_audit(user["id"], "READ", "reconciliation_report", None, None, {})
    return data


@app.post("/api/admin/reconciliation/backfill-test-company")
def admin_backfill_test_company(
    user: Dict[str, Any] = Depends(require_admin),
):
    """
    One-time non-destructive backfill: link orphan profiles, hr_users, and relocation_cases
    to the company named exactly 'Test company'. Does not overwrite existing linkage.
    """
    result = db.run_admin_reconciliation_backfill_test_company("Test company")
    db.log_audit(
        user["id"],
        "RECONCILIATION_BACKFILL",
        "reconciliation",
        None,
        None,
        result.get("summary") or {},
    )
    return result


@app.post("/api/admin/reconciliation/link-person-company")
def reconciliation_link_person_company(
    body: ReconciliationLinkPersonCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: attach a profile (person) to a company. Updates profiles.company_id and employees if present."""
    if not db.get_profile_record(body.profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.admin_reassign_employee_company(body.profile_id, body.company_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_PERSON_COMPANY", "profile", body.profile_id, None, {"company_id": body.company_id})
    return {"ok": True}


@app.post("/api/admin/reconciliation/link-assignment-company")
def reconciliation_link_assignment_company(
    body: ReconciliationLinkAssignmentCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: set assignment's case company (relocation_cases.company_id)."""
    _require_reason(body.reason)
    if not db.get_assignment_by_id(body.assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.admin_fix_assignment_company_linkage(body.assignment_id, body.company_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_ASSIGNMENT_COMPANY", "assignment", body.assignment_id, body.reason, {"company_id": body.company_id})
    return {"ok": True}


@app.post("/api/admin/reconciliation/link-assignment-person")
def reconciliation_link_assignment_person(
    body: ReconciliationLinkAssignmentPersonRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: attach a profile (person) as employee to an assignment."""
    if not db.get_assignment_by_id(body.assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not db.get_profile_record(body.profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    db.attach_employee_to_assignment(body.assignment_id, body.profile_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_ASSIGNMENT_PERSON", "assignment", body.assignment_id, None, {"profile_id": body.profile_id})
    return {"ok": True}


@app.post("/api/admin/reconciliation/link-policy-company")
def reconciliation_link_policy_company(
    body: ReconciliationLinkPolicyCompanyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: reassign a company_policy to a company."""
    if not db.get_company_policy(body.policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    if not db.get_company(body.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.admin_link_policy_company(body.policy_id, body.company_id)
    db.log_audit(user["id"], "RECONCILIATION_LINK_POLICY_COMPANY", "company_policy", body.policy_id, None, {"company_id": body.company_id})
    return {"ok": True}


@app.get("/api/admin/debug/runtime-database")
def debug_runtime_database(user: Dict[str, Any] = Depends(require_admin)):
    """
    Admin diagnostic: show current DB scheme/target and seed flags.
    Safe to expose (sanitized, no passwords).
    """
    info = Database.get_db_info()
    db_url = info.get("db_url", "")
    # Sanitize: drop credentials if present.
    if "@" in db_url and "://" in db_url:
        scheme, rest = db_url.split("://", 1)
        if "@" in rest:
            rest = rest.split("@", 1)[-1]
        db_url = f"{scheme}://{rest}"
    disable_demo_reseed = DISABLE_DEMO_RESEED
    allow_legacy_demo_seed = ALLOW_LEGACY_DEMO_SEED
    seed_guard_active = _db_scheme == "sqlite" and disable_demo_reseed
    return {
        "db_scheme": info.get("db_url_scheme"),
        "database_target": db_url,
        "disable_demo_reseed": disable_demo_reseed,
        "allow_legacy_demo_seed": allow_legacy_demo_seed,
        "seed_guard_active": seed_guard_active,
    }


@app.get("/api/admin/debug/test-company-graph")
def debug_test_company_graph(user: Dict[str, Any] = Depends(require_admin)):
    """
    Admin diagnostic: snapshot of Test company graph (counts + sample rows).
    """
    TEST_COMPANY_ID = db.TEST_COMPANY_FIXED_ID
    with db.engine.connect() as conn:
        company = db.get_company(TEST_COMPANY_ID)
        profiles = conn.execute(
            text("SELECT id, role, email, company_id FROM profiles WHERE company_id = :cid ORDER BY id LIMIT 20"),
            {"cid": TEST_COMPANY_ID},
        ).fetchall()
        hr_users = conn.execute(
            text("SELECT id, company_id, profile_id FROM hr_users WHERE company_id = :cid ORDER BY id LIMIT 20"),
            {"cid": TEST_COMPANY_ID},
        ).fetchall()
        employees = conn.execute(
            text("SELECT id, company_id, profile_id, relocation_case_id FROM employees WHERE company_id = :cid ORDER BY id LIMIT 20"),
            {"cid": TEST_COMPANY_ID},
        ).fetchall()
        cases = conn.execute(
            text("SELECT id, company_id, employee_id, hr_user_id, status, stage FROM relocation_cases WHERE company_id = :cid ORDER BY id LIMIT 20"),
            {"cid": TEST_COMPANY_ID},
        ).fetchall()
        assignments = conn.execute(
            text(
                """
                SELECT a.id, a.case_id, a.canonical_case_id, a.hr_user_id, a.employee_user_id,
                       a.employee_identifier, a.status
                FROM case_assignments a
                LEFT JOIN relocation_cases rc ON rc.id = COALESCE(NULLIF(TRIM(a.canonical_case_id), ''), a.case_id)
                LEFT JOIN hr_users hu ON hu.profile_id = a.hr_user_id
                WHERE rc.company_id = :cid OR (rc.company_id IS NULL AND hu.company_id = :cid)
                ORDER BY a.created_at DESC
                LIMIT 20
                """
            ),
            {"cid": TEST_COMPANY_ID},
        ).fetchall()
        policies = conn.execute(
            text("SELECT id, company_id, title, extraction_status FROM company_policies WHERE company_id = :cid ORDER BY created_at DESC LIMIT 20"),
            {"cid": TEST_COMPANY_ID},
        ).fetchall()

    return {
        "company": company,
        "counts": {
            "profiles": len(profiles),
            "hr_users": len(hr_users),
            "employees": len(employees),
            "relocation_cases": len(cases),
            "case_assignments": len(assignments),
            "policies": len(policies),
        },
        "sample_profiles": [dict(r._mapping) for r in profiles],
        "sample_hr_users": [dict(r._mapping) for r in hr_users],
        "sample_employees": [dict(r._mapping) for r in employees],
        "sample_cases": [dict(r._mapping) for r in cases],
        "sample_assignments": [dict(r._mapping) for r in assignments],
        "sample_policies": [dict(r._mapping) for r in policies],
    }


@app.post("/api/admin/reconciliation/rebuild-test-company-graph")
def rebuild_test_company_graph(user: Dict[str, Any] = Depends(require_admin)):
    """
    Admin: full, idempotent rebuild of Test company graph in the current runtime DB.
    - Reassigns non-admin demo/test users and related seats/cases to the fixed Test company.
    - Repairs HR/employee seats and case/assignment linkage when recoverable.
    """
    TEST_COMPANY_ID = db.TEST_COMPANY_FIXED_ID

    # Simple before snapshot: counts per table for Test company
    with db.engine.connect() as conn:
        before_profiles = conn.execute(
            text("SELECT COUNT(*) AS n FROM profiles WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_hr = conn.execute(
            text("SELECT COUNT(*) AS n FROM hr_users WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_emp = conn.execute(
            text("SELECT COUNT(*) AS n FROM employees WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_cases = conn.execute(
            text("SELECT COUNT(*) AS n FROM relocation_cases WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        before_policies = conn.execute(
            text("SELECT COUNT(*) AS n FROM company_policies WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]

    summary = db.rebuild_test_company_graph()

    with db.engine.connect() as conn:
        after_profiles = conn.execute(
            text("SELECT COUNT(*) AS n FROM profiles WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_hr = conn.execute(
            text("SELECT COUNT(*) AS n FROM hr_users WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_emp = conn.execute(
            text("SELECT COUNT(*) AS n FROM employees WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_cases = conn.execute(
            text("SELECT COUNT(*) AS n FROM relocation_cases WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]
        after_policies = conn.execute(
            text("SELECT COUNT(*) AS n FROM company_policies WHERE company_id = :cid"),
            {"cid": TEST_COMPANY_ID},
        ).fetchone()._mapping["n"]

    db.log_audit(
        user["id"],
        "RECONCILIATION_REBUILD_TEST_COMPANY",
        "reconciliation",
        None,
        None,
        summary,
    )

    return {
        "ok": True,
        "summary": {
            "test_company_id": db.TEST_COMPANY_FIXED_ID,
            **summary,
        },
        "before": {
            "profiles": before_profiles,
            "hr_users": before_hr,
            "employees": before_emp,
            "relocation_cases": before_cases,
            "policies": before_policies,
        },
        "after": {
            "profiles": after_profiles,
            "hr_users": after_hr,
            "employees": after_emp,
            "relocation_cases": after_cases,
            "policies": after_policies,
        },
    }


class AdminPatchPolicyRequest(BaseModel):
    title: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[str] = None
    publish_version_id: Optional[str] = None
    unpublish: Optional[bool] = None


class AdminApplyDefaultTemplateRequest(BaseModel):
    company_id: str
    template_id: Optional[str] = None
    overwrite_existing: Optional[bool] = False


@app.get("/api/admin/policies/overview")
def list_admin_policy_overview(
    company_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: per-company policy status for overview."""
    items = db.list_admin_policy_overview(company_id=company_id)
    db.log_audit(user["id"], "READ", "admin_policy_overview", None, None, {"company_id": company_id})
    return {"companies": items}


@app.get("/api/admin/policies")
def list_admin_policies(
    company_id: Optional[str] = Query(None, description="Filter by company; required for company-scoped list"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: list policies for a company. Requires company_id."""
    if not company_id or not company_id.strip():
        raise HTTPException(status_code=400, detail="company_id is required")
    data = db.get_admin_policies_by_company(company_id.strip())
    if data is None:
        raise HTTPException(status_code=404, detail="Company not found")
    db.log_audit(user["id"], "READ", "admin_policies", None, None, {"company_id": company_id})
    return data


@app.get("/api/admin/policies/{policy_id}")
def get_admin_policy_detail(policy_id: str, user: Dict[str, Any] = Depends(require_admin)):
    """Admin: single policy with company, versions, published version."""
    data = db.get_admin_policy_detail(policy_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.log_audit(user["id"], "READ", "admin_policy_detail", policy_id, None, {})
    return data


@app.get("/api/admin/policies/{policy_id}/versions")
def list_admin_policy_versions(policy_id: str, user: Dict[str, Any] = Depends(require_admin)):
    """Admin: list all versions for a policy."""
    policy = db.get_company_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    versions = db.list_policy_versions(policy_id)
    db.log_audit(user["id"], "READ", "admin_policy_versions", policy_id, None, {})
    return {"policy_id": policy_id, "versions": versions}


@app.patch("/api/admin/policies/{policy_id}")
def patch_admin_policy(
    policy_id: str,
    body: AdminPatchPolicyRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: update policy metadata and/or publish/unpublish a version."""
    policy = db.get_company_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return db.get_admin_policy_detail(policy_id)

    if body.title is not None or body.version is not None or body.effective_date is not None:
        db.update_company_policy_meta(
            policy_id,
            title=body.title,
            version=body.version,
            effective_date=body.effective_date,
        )
    if body.unpublish is True:
        db.archive_all_published_versions(policy_id)
        db.log_audit(user["id"], "ADMIN_UNPUBLISH_POLICY", "policy_version", policy_id, None, {})
    elif body.publish_version_id:
        vid = body.publish_version_id
        version = db.get_policy_version(vid)
        if not version or version.get("policy_id") != policy_id:
            raise HTTPException(status_code=400, detail="Version not found or does not belong to this policy")
        db.archive_other_published_versions(policy_id, vid)
        db.update_policy_version_status(vid, "published")
        db.log_audit(user["id"], "ADMIN_PUBLISH_POLICY", "policy_version", policy_id, None, {"version_id": vid})

    updated = db.get_admin_policy_detail(policy_id)
    db.log_audit(user["id"], "UPDATE", "admin_policy", policy_id, None, payload)
    return updated


@app.get("/api/admin/policies/templates")
def list_admin_policy_templates(user: Dict[str, Any] = Depends(require_admin)):
    """Admin: list default platform policy templates."""
    templates = db.list_default_policy_templates()
    db.log_audit(user["id"], "READ", "admin_policy_templates", None, None, {})
    return {"templates": templates}


@app.post("/api/admin/policies/apply-default-template")
def apply_default_template_to_company(
    body: AdminApplyDefaultTemplateRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Admin: apply a default policy template to a company. Creates a new company policy from the template."""
    template_id = body.template_id
    if not template_id:
        templates = db.list_default_policy_templates()
        default_one = next((t for t in templates if t.get("is_default_template")), templates[0] if templates else None)
        if not default_one:
            raise HTTPException(status_code=404, detail="No default template found")
        template_id = default_one["id"]
    result = db.apply_default_template_to_company(
        company_id=body.company_id,
        template_id=template_id,
        overwrite_existing=body.overwrite_existing or False,
        created_by=user.get("id"),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Apply failed"))
    db.log_audit(
        user["id"], "APPLY_DEFAULT_TEMPLATE", "admin_policy",
        result.get("policy_id"), None,
        {"company_id": body.company_id, "template_id": template_id},
    )
    return result


@app.get("/api/admin/support-cases")
def list_support_cases(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    priority: Optional[str] = Query(None, description="low | medium | high | urgent"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """List support cases (tickets) with optional company, status, severity, priority filters."""
    items = db.list_support_cases(status=status, severity=severity, company_id=company_id, priority=priority)
    db.log_audit(user["id"], "READ", "support_case", None, None, {"status": status, "severity": severity, "company_id": company_id, "priority": priority})
    return {"support_cases": items}


@app.patch("/api/admin/support-cases/{case_id}")
def patch_support_case(
    case_id: str,
    body: AdminSupportCasePatchRequest,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Update ticket: priority, status, assignee_id, category."""
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        out = db.get_support_case(case_id)
        if not out:
            raise HTTPException(status_code=404, detail="Support case not found")
        return out
    if body.priority is not None and body.priority not in ("low", "medium", "high", "urgent"):
        raise HTTPException(status_code=400, detail="priority must be low, medium, high, or urgent")
    if body.status is not None and body.status not in ("open", "investigating", "blocked", "resolved"):
        raise HTTPException(status_code=400, detail="status must be open, investigating, blocked, or resolved")
    out = db.update_support_case(
        case_id,
        priority=body.priority,
        status=body.status,
        assignee_id=body.assignee_id,
        category=body.category,
    )
    if not out:
        raise HTTPException(status_code=404, detail="Support case not found")
    db.log_audit(user["id"], "UPDATE", "support_case", case_id, None, payload)
    return out


@app.get("/api/admin/support-cases/{case_id}/notes")
def list_support_notes(case_id: str, user: Dict[str, Any] = Depends(require_admin)):
    items = db.list_support_notes(case_id)
    db.log_audit(user["id"], "READ", "support_case", case_id, None, {"notes": True})
    return {"notes": items}


@app.post("/api/admin/support-cases/{case_id}/notes")
def add_support_note(case_id: str, request: AdminSupportNoteRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    db.add_support_note(case_id, user["id"], request.note)
    db.log_audit(
        user["id"],
        "COMMENT",
        "support_case",
        case_id,
        request.reason,
        {"note": request.note},
    )
    return {"ok": True}


# Admin Messages - HR/employee threads + internal collaboration
@app.get("/api/admin/messages/threads")
def list_admin_message_threads(
    company_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    thread_type: Optional[str] = Query(None, description="hr_employee | collaboration"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_admin),
):
    """List message threads: HR-employee (legacy messages) and/or collaboration (internal admin)."""
    hr_threads = []
    collab_threads = []
    try:
        if not thread_type or thread_type == "hr_employee":
            hr_threads = db.list_admin_message_threads(
                company_id=company_id, user_id=user_id, limit=limit, offset=offset
            )
    except Exception as e:
        log.warning("list_admin_message_threads failed: %s", e)
        hr_threads = []
    if not thread_type or thread_type == "collaboration":
        try:
            from .services.collaboration_service import list_all_threads
            collab_threads = list_all_threads(
                user.get("id", ""),
                target_type=None,
                participant_user_id=user_id,
                status=None,
                limit=limit,
                offset=offset,
            )
        except Exception as e:
            log.warning("list_all_threads failed: %s", e)
    combined = hr_threads + collab_threads
    combined.sort(key=lambda t: (t.get("last_message_at") or t.get("created_at") or ""), reverse=True)
    return {"threads": combined[:limit], "total": len(combined)}


@app.get("/api/admin/messages/threads/hr-employee/{assignment_id}")
def get_admin_hr_thread_detail(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_admin),
):
    """Get HR-employee thread messages and context."""
    assign = db.get_admin_assignment_detail(assignment_id)
    if not assign:
        raise HTTPException(status_code=404, detail="Assignment not found")
    messages = db.list_messages_by_assignment(assignment_id)
    return {
        "thread_type": "hr_employee",
        "assignment_id": assignment_id,
        "company_id": assign.get("case_company_id") or assign.get("hr_company_id"),
        "company_name": assign.get("company_name"),
        "employee_name": assign.get("employee_full_name") or assign.get("employee_identifier"),
        "hr_name": assign.get("hr_full_name"),
        "participants": [p for p in [assign.get("hr_full_name"), assign.get("employee_full_name") or assign.get("employee_identifier")] if p],
        "messages": messages,
        "status": assign.get("status"),
    }


@app.post("/api/admin/actions/resend-invite")
def admin_resend_invite(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    db.log_audit(user["id"], "RESEND_INVITE", "assignment", payload.get("assignment_id"), request.reason, payload)
    return {"ok": True}


@app.post("/api/admin/actions/reset-onboarding")
def admin_reset_onboarding(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    assignment_id = payload.get("assignment_id")
    if assignment_id:
        # Default active status after reset is 'assigned'.
        new_status = normalize_status(payload.get("status") or AssignmentStatus.ASSIGNED.value)
        assert_canonical_status(new_status)
        db.update_assignment_status(assignment_id, new_status)
    db.log_audit(user["id"], "RESET", "assignment", assignment_id, request.reason, payload)
    return {"ok": True}


@app.post("/api/admin/actions/unlock-case")
def admin_unlock_case(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    case_id = payload.get("case_id")
    if case_id:
        db.upsert_relocation_case(
            case_id=case_id,
            company_id=payload.get("company_id"),
            employee_id=payload.get("employee_id"),
            status="active",
            stage=payload.get("stage"),
            host_country=payload.get("host_country"),
            home_country=payload.get("home_country"),
        )
    db.log_audit(user["id"], "UPDATE", "relocation_case", case_id, request.reason, payload)
    return {"ok": True}


@app.post("/api/admin/actions/rerun-document")
def admin_rerun_document(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    db.log_audit(user["id"], "REPROCESS", "document", payload.get("document_id"), request.reason, payload)
    return {"ok": True}


@app.post("/api/admin/actions/refresh-policy")
def admin_refresh_policy(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    db.log_audit(user["id"], "UPDATE", "policy", payload.get("policy_id"), request.reason, payload)
    return {"ok": True}


@app.post("/api/admin/actions/override-eligibility")
def admin_override_eligibility(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    assignment_id = payload.get("assignment_id")
    if assignment_id:
        db.create_eligibility_override(
            assignment_id=assignment_id,
            category=payload.get("category", "unknown"),
            allowed=bool(payload.get("allowed", True)),
            expires_at=payload.get("expires_at"),
            note=payload.get("note"),
            created_by_user_id=user["id"],
        )
    db.log_audit(user["id"], "OVERRIDE", "assignment", assignment_id, request.reason, payload)
    return {"ok": True}


@app.post("/api/admin/actions/export-support-bundle")
def admin_export_support_bundle(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    bundle = {
        "support_case_id": payload.get("support_case_id"),
        "exported_at": datetime.utcnow().isoformat(),
        "note": "Anonymized snapshot",
        "policy_ids": payload.get("policy_ids", []),
        "error_codes": payload.get("error_codes", []),
        "timestamps": payload.get("timestamps", []),
    }
    db.log_audit(user["id"], "EXPORT", "support_case", payload.get("support_case_id"), request.reason, payload)
    return {"ok": True, "bundle": bundle}


@app.post("/api/admin/actions/purge-cases")
def admin_purge_cases(request: AdminReasonRequest, user: Dict[str, Any] = Depends(require_admin)):
    _require_reason(request.reason)
    payload = request.payload or {}
    active_statuses = payload.get("active_statuses") or [
        AssignmentStatus.ASSIGNED.value,
        AssignmentStatus.AWAITING_INTAKE.value,
        AssignmentStatus.SUBMITTED.value,
    ]
    stats = db.purge_inactive_cases(active_statuses)
    db.log_audit(user["id"], "RESET", "assignment", None, request.reason, {"active_statuses": active_statuses, **stats})
    return {"ok": True, "stats": stats}


@app.get("/api/profile/current", response_model=RelocationProfile)
def get_current_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile."""
    effective = _effective_user(user, UserRole.EMPLOYEE)
    profile = db.get_profile(effective["id"])
    
    if not profile:
        # Return empty profile
        profile = RelocationProfile(userId=effective["id"]).model_dump()
    
    return profile


@app.get("/api/profile/next-question", response_model=NextQuestionResponse)
def get_next_question(user: Dict[str, Any] = Depends(get_current_user)):
    """Get the next question to ask the user."""
    effective = _effective_user(user, UserRole.EMPLOYEE)
    profile = db.get_profile(effective["id"])
    
    if not profile:
        profile = RelocationProfile(userId=effective["id"]).model_dump()
    
    # Get answered questions
    answers = db.get_answers(effective["id"])
    answered_question_ids = set(ans["question_id"] for ans in answers)
    
    # Get next question from orchestrator
    response = orchestrator.get_next_question(profile, answered_question_ids)
    
    return response


@app.post("/api/profile/answer")
def submit_answer(request: AnswerRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Submit an answer to a question.
    Updates profile and returns next question.
    """
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    # Get current profile
    profile = db.get_profile(effective["id"])
    
    if not profile:
        profile = RelocationProfile(userId=effective["id"]).model_dump()
    
    # Apply answer to profile
    profile = orchestrator.apply_answer(profile, request.questionId, request.answer, request.isUnknown)
    
    # Save profile
    db.save_profile(effective["id"], profile)
    
    # Save answer to audit trail
    db.save_answer(effective["id"], request.questionId, request.answer, request.isUnknown)
    
    # Get next question
    answers = db.get_answers(effective["id"])
    answered_question_ids = set(ans["question_id"] for ans in answers)
    next_response = orchestrator.get_next_question(profile, answered_question_ids)
    
    return {
        "success": True,
        "nextQuestion": next_response
    }


@app.post("/api/profile/complete")
def complete_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Mark profile as complete and compute final state.
    Returns readiness rating and recommendations.
    """
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    profile = db.get_profile(effective["id"])
    
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found")
    
    # Compute completion state
    completion_state = orchestrator.compute_completion_state(profile)
    
    return {
        "success": True,
        "completionState": completion_state
    }


@app.get("/api/employee/recommendations")
def get_employee_recommendations(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    """Get recommendations for employee's assignment (uses employee_profile from wizard)."""
    effective = _effective_user(user, UserRole.EMPLOYEE)
    assignment = db.get_assignment_for_employee(effective["id"], request_id=request.state.request_id)
    if not assignment:
        return {"housing": [], "schools": [], "movers": []}
    profile = db.get_employee_profile(assignment["id"])
    if not profile:
        return {"housing": [], "schools": [], "movers": []}
    completion = orchestrator.compute_completion_state(profile)
    recs = completion.get("recommendations", {})
    return {
        "housing": recs.get("housing", []),
        "schools": recs.get("schools", []),
        "movers": recs.get("movers", []),
    }


@app.get("/api/recommendations/housing")
def get_housing_recommendations(user: Dict[str, Any] = Depends(get_current_user)) -> List[HousingRecommendation]:
    """Get housing recommendations based on profile."""
    profile = db.get_profile(user["id"])
    
    if not profile:
        return []
    
    recommendations = orchestrator.recommendation_engine.get_housing_recommendations(profile)
    return recommendations


@app.get("/api/recommendations/schools")
def get_school_recommendations(user: Dict[str, Any] = Depends(get_current_user)) -> List[SchoolRecommendation]:
    """Get school recommendations based on profile."""
    profile = db.get_profile(user["id"])
    
    if not profile:
        return []
    
    recommendations = orchestrator.recommendation_engine.get_school_recommendations(profile)
    return recommendations


@app.get("/api/recommendations/movers")
def get_mover_recommendations(user: Dict[str, Any] = Depends(get_current_user)) -> List[MoverRecommendation]:
    """Get mover recommendations based on profile."""
    profile = db.get_profile(user["id"])
    
    if not profile:
        return []
    
    recommendations = orchestrator.recommendation_engine.get_mover_recommendations(profile)
    return recommendations


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get complete dashboard data including:
    - Profile completeness
    - Immigration readiness
    - Next actions
    - Timeline
    - All recommendations
    """
    profile = db.get_profile(user["id"])
    # Employees may use case/assignment flow: try assignment's employee_profile
    if not profile and user.get("role") in (UserRole.EMPLOYEE.value, UserRole.ADMIN.value):
        if user.get("role") == UserRole.EMPLOYEE.value and not user.get("impersonation"):
            _best_effort_reconcile_employee_assignments(
                context="get_dashboard",
                user_id=user["id"],
                email=user.get("email"),
                username=user.get("username"),
                role=UserRole.EMPLOYEE.value,
                request_id=request.state.request_id,
            )
        assignment = db.get_assignment_for_employee(user["id"], request_id=request.state.request_id)
        if assignment:
            profile = db.get_employee_profile(assignment["id"])

    if not profile:
        # Return minimal dashboard instead of 400 so Providers/other pages can load
        return DashboardResponse(
            profileCompleteness=0,
            immigrationReadiness={"score": 0, "status": "RED", "reasons": ["Complete your case wizard for full dashboard"], "missingDocs": []},
            nextActions=["Complete your relocation case wizard"],
            timeline=[],
            recommendations={"housing": [], "schools": [], "movers": []},
            overallStatus="incomplete",
        )
    
    # Compute completion state
    completion_state = orchestrator.compute_completion_state(profile)
    
    # Build next actions list
    next_actions = _build_next_actions(profile, completion_state)
    
    # Build timeline
    timeline = _build_timeline(profile, completion_state)
    
    # Determine overall status
    overall_status = _determine_overall_status(completion_state)
    
    # Get all recommendations
    recommendations = {}
    if "housing" in completion_state.get("recommendations", {}):
        recommendations["housing"] = completion_state["recommendations"]["housing"]
    if "schools" in completion_state.get("recommendations", {}):
        recommendations["schools"] = completion_state["recommendations"]["schools"]
    if "movers" in completion_state.get("recommendations", {}):
        recommendations["movers"] = completion_state["recommendations"]["movers"]
    
    return DashboardResponse(
        profileCompleteness=completion_state["profileCompleteness"],
        immigrationReadiness=completion_state["immigrationReadiness"] or {
            "score": 0,
            "status": "RED",
            "reasons": ["Profile incomplete"],
            "missingDocs": []
        },
        nextActions=next_actions,
        timeline=timeline,
        recommendations=recommendations,
        overallStatus=overall_status
    )


@app.post("/api/hr/cases", response_model=CreateCaseResponse)
def create_case(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    company_id = _get_hr_company_id(effective)
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="No company linked to your profile. Please complete your company profile first.",
        )
    case_id = str(uuid.uuid4())
    profile = RelocationProfile(userId=effective["id"]).model_dump()
    db.create_case(case_id, effective["id"], profile, company_id=company_id)
    return CreateCaseResponse(caseId=case_id)


@app.get("/api/hr/company-profile")
def get_company_profile(request: Request, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    t0 = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    effective = _effective_user(user, UserRole.HR)
    # Align hr_users with profiles.company_id so resolution matches Admin-assigned company
    db.sync_hr_user_company_from_profile(effective["id"])
    cid = _get_hr_company_id(effective)
    company = db.get_company(cid) if cid else db.get_company_for_user(effective["id"])
    dur_ms = (time.perf_counter() - t0) * 1000
    _log_endpoint_perf("/api/hr/company-profile", request_id, user.get("id"), dur_ms, 200)
    if os.getenv("PERF_DEBUG", "").lower() in ("1", "true", "yes") and company:
        log.info(
            "company_profile_loaded user_id=%s company_id=%s name=%s",
            effective.get("id"),
            company.get("id"),
            company.get("name"),
        )
    return {"company": company}


@app.get("/api/company")
def get_current_user_company(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    """Return the authenticated user's company (for header branding). Available to HR and Employee."""
    t0 = time.perf_counter()
    request_id = getattr(request.state, "request_id", None)
    # HR users: same resolution as /api/hr/company-profile (sync + coalesced company_id)
    if user.get("role") == UserRole.HR.value or user.get("is_admin"):
        effective = _effective_user(user, UserRole.HR) if user.get("role") == UserRole.HR.value else user
        if user.get("role") == UserRole.HR.value:
            db.sync_hr_user_company_from_profile(effective["id"])
        cid = _get_hr_company_id(effective if user.get("role") == UserRole.HR.value else user)
        company = db.get_company(cid) if cid else None
    else:
        company = db.get_company_for_user(user["id"])
    dur_ms = (time.perf_counter() - t0) * 1000
    _log_endpoint_perf("/api/company", request_id, user.get("id"), dur_ms, 200)
    return {"company": company}


@app.post("/api/hr/company-profile")
def save_company_profile(request: CompanyProfileRequest, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = (profile.get("company_id") if profile else None) or _get_hr_company_id(effective)
    if not company_id:
        company_id = str(uuid.uuid4())
        db.set_profile_company(effective["id"], company_id)
    db.create_company(
        company_id,
        request.name,
        request.country,
        request.size_band,
        request.address,
        request.phone,
        request.hr_contact,
        legal_name=request.legal_name,
        website=request.website,
        hq_city=request.hq_city,
        industry=request.industry,
        default_destination_country=request.default_destination_country,
        support_email=request.support_email,
        default_working_location=request.default_working_location,
    )
    db.log_audit(effective["id"], "UPDATE", "company", company_id, "HR company profile update", {
        "name": request.name,
        "country": request.country,
        "size_band": request.size_band,
        "address": request.address,
        "phone": request.phone,
        "hr_contact": request.hr_contact,
        "legal_name": request.legal_name,
        "website": request.website,
        "hq_city": request.hq_city,
        "industry": request.industry,
        "default_destination_country": request.default_destination_country,
        "support_email": request.support_email,
        "default_working_location": request.default_working_location,
    })
    # Ensure hr_users row exists and matches (set_profile_company UPDATE may no-op if row missing)
    prof_after = db.get_profile_record(effective["id"])
    if prof_after and (prof_after.get("role") or "").strip().upper() == "HR":
        db.ensure_hr_user_for_profile(effective["id"], company_id)
    return {"ok": True, "company_id": company_id}


# ---------------------------------------------------------------------------
# HR company-scoped employees
# ---------------------------------------------------------------------------


@app.get("/api/hr/employees")
def list_hr_company_employees(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    """List employees for the HR user's company. Company-scoped only."""
    effective = _effective_user(user, UserRole.HR)
    company_id = _get_hr_company_id(effective)
    if not company_id:
        # Align with get_company_profile: return empty list instead of 400 when no company
        return {"employees": [], "has_company": False}
    # Reconcile profiles (Admin/HR assignments) into employees before listing (same as Admin)
    db.ensure_employees_for_company(company_id)
    # People linked only via case_assignments (claimed intake) used to skip profiles.company_id;
    # backfill so they appear alongside manually-added employees.
    db.ensure_directory_from_assignments_for_company(company_id)
    items = db.list_employees_with_profiles(company_id)
    db.log_audit(effective["id"], "READ", "employee", None, None, {"company_id": company_id})
    return {"employees": items, "has_company": True}


@app.get("/api/hr/employees/{employee_id}")
def get_hr_company_employee(
    employee_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Get employee detail for HR's company. 404 if not in company."""
    effective = _effective_user(user, UserRole.HR)
    company_id = _get_hr_company_id(effective)
    if not company_id:
        raise HTTPException(status_code=400, detail="No company linked to your profile")
    employee = db.get_employee_for_company(employee_id, company_id)
    if not employee:
        emp_by_profile = db.get_employee_by_profile_for_company(employee_id, company_id)
        employee = emp_by_profile
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.log_audit(effective["id"], "READ", "employee", employee_id, None, {"company_id": company_id})
    return {"employee": employee}


class HrEmployeeUpdateRequest(BaseModel):
    band: Optional[str] = None
    assignment_type: Optional[str] = None
    status: Optional[str] = None


@app.patch("/api/hr/employees/{employee_id}")
def update_hr_company_employee(
    employee_id: str,
    request: HrEmployeeUpdateRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Update employee (band, assignment_type, status) within company boundary."""
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    company_id = _get_hr_company_id(effective)
    if not company_id:
        raise HTTPException(status_code=400, detail="No company linked to your profile")
    updated = db.update_employee_limited(
        employee_id,
        company_id,
        band=request.band,
        assignment_type=request.assignment_type,
        status=request.status,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.log_audit(effective["id"], "UPDATE", "employee", employee_id, "HR update", {"company_id": company_id})
    employee = db.get_employee_for_company(employee_id, company_id)
    return {"employee": employee or db.get_employee_by_profile_for_company(employee_id, company_id)}


ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "svg"}
ALLOWED_LOGO_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml"}
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2MB


def _logo_extension_from_filename(filename: str) -> Optional[str]:
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_LOGO_EXTENSIONS else None


@app.post("/api/hr/company-profile/logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = profile.get("company_id") if profile else None
    if not company_id:
        raise HTTPException(status_code=400, detail="No company linked to your profile")

    ext = _logo_extension_from_filename(file.filename or "")
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Use PNG, JPG, or SVG.",
        )
    content_type = file.content_type or ""
    if content_type and content_type.lower() not in ALLOWED_LOGO_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Use image/png, image/jpeg, or image/svg+xml.",
        )

    content = await file.read()
    if len(content) > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Logo must be 2MB or smaller")

    try:
        supabase = get_supabase_admin_client()
        path = f"companies/{company_id}/logo.{ext}"
        supabase.storage.from_("company-logos").upload(
            path,
            content,
            file_options={"content-type": content_type or "image/png", "upsert": "true"},
        )
    except Exception as e:
        log.warning("company logo upload failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail="Logo upload failed. Check Supabase storage and bucket company-logos.",
        ) from e

    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    logo_url = f"{supabase_url}/storage/v1/object/public/company-logos/{path}"
    db.update_company_logo(company_id, logo_url)
    db.log_audit(effective["id"], "UPDATE", "company", company_id, "HR company logo upload", {"logo_url": logo_url})
    return {"ok": True, "logo_url": logo_url}


@app.post("/api/hr/company-profile/remove-logo")
def remove_company_logo(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = profile.get("company_id") if profile else None
    if not company_id:
        raise HTTPException(status_code=400, detail="No company linked to your profile")
    db.update_company_logo(company_id, None)
    db.log_audit(effective["id"], "UPDATE", "company", company_id, "HR company logo removed", {})
    return {"ok": True}


@app.get("/api/hr/preferred-suppliers")
def list_hr_preferred_suppliers(
    service_category: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """List company preferred suppliers for the HR user's company."""
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = profile.get("company_id") if profile else None
    if not company_id:
        return {"preferred": []}
    items = db.list_company_preferred_suppliers(company_id, service_category)
    return {"preferred": items}


@app.post("/api/hr/preferred-suppliers")
def add_hr_preferred_supplier(
    body: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Add supplier to company preferred list."""
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = profile.get("company_id") if profile else None
    if not company_id:
        raise HTTPException(status_code=400, detail="No company linked to your profile")
    supplier_id = (body.get("supplier_id") or "").strip()
    if not supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id required")
    rec = db.add_company_preferred_supplier(
        company_id=company_id,
        supplier_id=supplier_id,
        service_category=(body.get("service_category") or "").strip() or None,
        priority_rank=int(body.get("priority_rank", 0) or 0),
        notes=(body.get("notes") or "").strip() or None,
    )
    return rec


@app.delete("/api/hr/preferred-suppliers/{supplier_id}")
def remove_hr_preferred_supplier(
    supplier_id: str,
    service_category: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Remove supplier from company preferred list."""
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = profile.get("company_id") if profile else None
    if not company_id:
        raise HTTPException(status_code=400, detail="No company linked to your profile")
    n = db.remove_company_preferred_supplier(company_id, supplier_id, service_category)
    return {"ok": True, "removed": n}


@app.post("/api/hr/cases/{case_id}/assign", response_model=AssignCaseResponse)
def assign_case(
    case_id: str,
    request: AssignCaseRequest,
    request_obj: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    request_id = getattr(request_obj.state, "request_id", None) or str(uuid.uuid4())
    try:
        _deny_if_impersonating(user)
        effective = _effective_user(user, UserRole.HR)
        case = db.get_case_by_id(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        hr_company_id = _get_hr_company_id(effective)
        if not hr_company_id:
            raise HTTPException(
                status_code=400,
                detail="No company linked to your profile. Please complete your company profile first.",
            )
        if not case.get("company_id"):
            db.upsert_relocation_case(
                case_id=case_id,
                company_id=hr_company_id,
                employee_id=case.get("employee_id"),
                status=case.get("status"),
                stage=case.get("stage"),
                host_country=case.get("host_country"),
                home_country=case.get("home_country"),
            )

        employee_identifier_raw = request.employeeIdentifier.strip()
        if not employee_identifier_raw:
            raise HTTPException(status_code=400, detail="Employee identifier required")

        fn = getattr(request, "employeeFirstName", None) or getattr(request, "employee_first_name", None)
        ln = getattr(request, "employeeLastName", None) or getattr(request, "employee_last_name", None)
        employee_first_name = (fn or "").strip() or None
        employee_last_name = (ln or "").strip() or None

        employee_user = db.get_user_by_identifier(employee_identifier_raw)
        if employee_user and hr_company_id:
            emp_profile = db.get_profile_record(employee_user["id"])
            if emp_profile and not emp_profile.get("company_id"):
                db.ensure_profile_record(
                    employee_user["id"],
                    emp_profile.get("email") or employee_identifier_raw,
                    emp_profile.get("role") or UserRole.EMPLOYEE.value,
                    emp_profile.get("full_name") or employee_identifier_raw.split("@")[0],
                    hr_company_id,
                )
        # Ensure employees row exists so HR Employees tab shows this employee (real auth accounts only)
        if employee_user and hr_company_id:
            db.ensure_employee_for_profile(employee_user["id"], hr_company_id)

        # New assignments created by HR are immediately in the 'assigned' state.
        assert_canonical_status(AssignmentStatus.ASSIGNED.value)
        try:
            with timed("unified_assignment_creation", request_id):
                uar = create_assignment_with_contact_and_invites(
                    db,
                    company_id=hr_company_id,
                    hr_user_id=effective["id"],
                    case_id=case_id,
                    employee_identifier_raw=employee_identifier_raw,
                    employee_first_name=employee_first_name,
                    employee_last_name=employee_last_name,
                    employee_user_id=employee_user["id"] if employee_user else None,
                    assignment_status=AssignmentStatus.ASSIGNED.value,
                    request_id=request_id,
                    observability_channel="hr",
                )
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve)) from ve
        assignment_id = uar.assignment_id
        invite_token = uar.invite_token
        stored_identifier = uar.stored_identifier
        now_iso = datetime.utcnow().isoformat()
        try:
            db.ensure_case_participant(
                case_id=case_id,
                person_id=effective["id"],
                role="hr_owner",
                joined_at=now_iso,
                request_id=request_id,
            )
        except Exception as exc:
            log.warning(
                "ensure_case_participant skipped assignment_id=%s case_id=%s role=hr_owner error=%s",
                assignment_id, case_id, str(exc),
            )
        event_type = "assignment.created"
        try:
            db.insert_case_event(
                case_id=case_id,
                assignment_id=assignment_id,
                actor_principal_id=effective["id"],
                event_type=event_type,
                payload={"employee_identifier": stored_identifier},
                request_id=request_id,
            )
        except Exception as exc:
            log.warning(
                "insert_case_event skipped assignment_id=%s case_id=%s event_type=%s error=%s",
                assignment_id,
                case_id,
                event_type,
                str(exc),
            )

        # Prefill invitation message in Messages
        invite_line = (
            f"Invitation token: {invite_token}"
            if invite_token
            else "You can claim your assignment after signing in."
        )
        message_body = (
            f"Hello,\n\n"
            f"You have been assigned a relocation case on ReloPass.\n\n"
            f"Assignment ID: {assignment_id}\n"
            f"Employee identifier: {employee_identifier_raw}\n"
            f"{invite_line}\n\n"
            f"Sign up or log in at https://relopass.com/auth?mode=login\n"
            f"Once logged in, go to My Case to start your intake.\n"
        )
        try:
            db.create_message(
                message_id=str(uuid.uuid4()),
                assignment_id=assignment_id,
                hr_user_id=effective["id"],
                employee_identifier=stored_identifier,
                subject="Your relocation case is ready",
                body=message_body,
                status="draft",
            )
        except Exception as exc:
            log.warning(
                "create_message skipped assignment_id=%s case_id=%s error=%s",
                assignment_id, case_id, str(exc),
            )

        return AssignCaseResponse(assignmentId=assignment_id, inviteToken=invite_token)
    except HTTPException:
        # Let explicit 4xx/404 propagate as-is.
        raise
    except Exception as e:
        err_msg = str(e)
        log.error(
            "request_id=%s method=POST route=/api/hr/cases/%s/assign user_id=%s email=%s employee_identifier=%s error=%s",
            request_id,
            case_id,
            user.get("id"),
            user.get("email"),
            getattr(request, "employeeIdentifier", None),
            repr(e),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Unable to assign case",
                "detail": err_msg,
                "request_id": request_id,
            },
        )


@app.get("/api/employee/assignments/current")
def get_employee_assignment(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    effective = _effective_user(user, UserRole.EMPLOYEE)
    if not user.get("impersonation"):
        _best_effort_reconcile_employee_assignments(
            context="get_employee_assignment",
            user_id=effective["id"],
            email=effective.get("email"),
            username=effective.get("username"),
            role=UserRole.EMPLOYEE.value,
            request_id=getattr(request.state, "request_id", None),
        )

    rid = request.state.request_id
    eid = effective["id"]
    linked = db.list_linked_assignments_for_employee(eid, request_id=rid)
    pending_claim = db.list_pending_claim_assignments_for_auth_user(eid, request_id=rid)
    for row in linked:
        row["status"] = normalize_status(row.get("status"))
    for row in pending_claim:
        row["status"] = normalize_status(row.get("status"))
    primary = linked[0] if linked else None
    if not primary:
        return {
            "assignment": None,
            "linked_assignments": [],
            "pending_claim_assignments": pending_claim,
        }
    return {
        "assignment": primary,
        "linked_assignments": linked,
        "pending_claim_assignments": pending_claim,
    }


@app.get("/api/employee/assignments/overview")
def get_employee_assignments_overview(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    """
    Lightweight linked + pending assignment summaries for the authenticated employee.
    No case draft/profile hydration.
    """
    effective = _effective_user(user, UserRole.EMPLOYEE)
    if not user.get("impersonation"):
        _best_effort_reconcile_employee_assignments(
            context="get_employee_assignments_overview",
            user_id=effective["id"],
            email=effective.get("email"),
            username=effective.get("username"),
            role=UserRole.EMPLOYEE.value,
            request_id=getattr(request.state, "request_id", None),
        )
    rid = getattr(request.state, "request_id", None)
    overview = build_employee_assignment_overview(
        db,
        effective["id"],
        request_id=rid,
        normalize_assignment_status=normalize_status,
    )
    linked_n = len(overview.get("linked") or [])
    pending_n = len(overview.get("pending") or [])
    identity_event(
        "identity.assignments.overview",
        request_id=rid,
        auth_user_id=str(effective["id"]).strip(),
        linked_count=linked_n,
        pending_count=pending_n,
    )
    return overview


@app.post("/api/employee/assignments/{assignment_id}/dismiss-pending")
def dismiss_pending_claim_assignment(
    request: Request,
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    """Employee declines a pending_claim assignment (same contact as linked account); does not unlink linked work."""
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    ok = db.dismiss_pending_claim_assignment_for_auth_user(
        assignment_id,
        effective["id"],
        request_id=getattr(request.state, "request_id", None),
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Pending assignment not found or not dismissible for this account.",
        )
    return {"ok": True}


@app.get("/api/employee/me/assignment-package-policy")
def get_employee_me_assignment_package_policy(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    """
    Single lightweight round-trip for the employee HR Policy / Assignment Package page.
    Resolves current assignment + applicable published policy (or explicit no_policy_found).
    """
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    effective = _effective_user(user, UserRole.EMPLOYEE)
    eid = effective.get("id")
    if not eid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not user.get("impersonation"):
        _best_effort_reconcile_employee_assignments(
            context="get_employee_me_assignment_package_policy",
            user_id=eid,
            email=effective.get("email"),
            username=effective.get("username"),
            role=UserRole.EMPLOYEE.value,
            request_id=getattr(request.state, "request_id", None),
        )

    assignment = db.get_assignment_for_employee(eid, request_id=request_id)
    if not assignment:
        return {
            "status": "no_assignment",
            "ok": True,
            "assignment_id": None,
            "has_policy": False,
            "policy": None,
            "benefits": [],
            "exclusions": [],
            "resolution_context": None,
            "resolved_at": None,
            "message": "You don't have an active assignment yet.",
            "message_secondary": None,
        }

    assignment_id = assignment.get("id")
    if not assignment_id:
        return {
            "status": "no_assignment",
            "ok": True,
            "assignment_id": None,
            "has_policy": False,
            "policy": None,
            "benefits": [],
            "exclusions": [],
            "resolution_context": None,
            "resolved_at": None,
            "message": "You don't have an active assignment yet.",
            "message_secondary": None,
        }

    try:
        result = _resolve_published_policy_for_employee(assignment_id, user, request_id, read_only=True)
    except HTTPException:
        raise
    except Exception as exc:
        log.warning(
            "employee_me_assignment_package_policy failed request_id=%s assignment_id=%s exc=%s",
            request_id,
            assignment_id,
            exc,
            exc_info=True,
        )
        return {
            "status": "error",
            "ok": False,
            "assignment_id": assignment_id,
            "has_policy": False,
            "policy": None,
            "benefits": [],
            "exclusions": [],
            "resolution_context": None,
            "resolved_at": None,
            "message": "We couldn't load your policy right now. Please try again shortly.",
            "message_secondary": None,
        }

    if not result.get("has_policy"):
        return {
            "status": "no_policy_found",
            "ok": True,
            "assignment_id": assignment_id,
            "has_policy": False,
            "policy": None,
            "benefits": [],
            "exclusions": [],
            "resolution_context": None,
            "resolved_at": None,
            "message": result.get("reason") or EMPLOYEE_POLICY_FALLBACK_PRIMARY,
            "message_secondary": result.get("reason_secondary") or EMPLOYEE_POLICY_FALLBACK_SECONDARY,
            "company_id_used": result.get("company_id_used"),
        }

    return {
        "status": "found",
        "ok": True,
        "assignment_id": assignment_id,
        "has_policy": True,
        "policy": result.get("policy") or {},
        "benefits": result.get("benefits") or [],
        "exclusions": result.get("exclusions") or [],
        "resolved_at": result.get("resolved_at"),
        "resolution_context": result.get("resolution_context"),
        "message": None,
        "message_secondary": None,
        "company_id_used": result.get("company_id"),
    }


@app.get("/api/employee/messages")
def list_employee_messages(user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))):
    effective = _effective_user(user, UserRole.EMPLOYEE)
    items = db.list_messages_for_employee(effective["id"])
    return {"messages": items}


def _validated_employee_claim_identifiers(
    effective: Dict[str, Any],
    claim: ClaimAssignmentRequest,
    *,
    claim_req_id: str,
    assignment_id: str,
    failure_event: str,
) -> List[str]:
    """Require account + request identifiers; return normalized lowercase identifiers for identity checks."""
    user_identifiers = [x.lower() for x in [effective.get("email"), effective.get("username")] if x]
    if not user_identifiers:
        identity_event(
            failure_event,
            failure_code="CLAIM_MISSING_ACCOUNT_IDENTIFIER",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective.get("id"),
        )
        raise HTTPException(
            status_code=400,
            detail=err_detail(
                IdentityErrorCode.CLAIM_MISSING_ACCOUNT_IDENTIFIER,
                "Your account must have an email or username set",
            ),
        )

    if not claim.email or not claim.email.strip():
        identity_event(
            failure_event,
            failure_code="CLAIM_MISSING_REQUEST_IDENTIFIER",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective.get("id"),
        )
        raise HTTPException(
            status_code=400,
            detail=err_detail(
                IdentityErrorCode.CLAIM_MISSING_REQUEST_IDENTIFIER,
                "Enter your email or username to claim",
            ),
        )

    req_ident = claim.email.strip().lower()
    if req_ident not in user_identifiers:
        identity_event(
            failure_event,
            failure_code="CLAIM_ACCOUNT_IDENTIFIER_MISMATCH",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective.get("id"),
        )
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_ACCOUNT_IDENTIFIER_MISMATCH,
                "The identifier you entered does not match your account. Use the same email or username you used to log in.",
            ),
        )
    return user_identifiers


@app.post("/api/employee/assignments/{assignment_id}/claim")
def claim_assignment(
    request: Request,
    assignment_id: str,
    claim: ClaimAssignmentRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    claim_req_id = getattr(request.state, "request_id", None) or ""
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        identity_event(
            "identity.claim.manual.failed",
            failure_code="ASSIGNMENT_NOT_FOUND",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective.get("id"),
        )
        raise HTTPException(status_code=404, detail="Assignment not found")

    user_identifiers = _validated_employee_claim_identifiers(
        effective,
        claim,
        claim_req_id=claim_req_id,
        assignment_id=assignment_id,
        failure_event="identity.claim.manual.failed",
    )

    ident_match = db.assignment_identity_matches_user_identifiers(
        assignment, user_identifiers, request_id=None
    )
    if not ident_match:
        identity_event(
            "identity.claim.manual.failed",
            failure_code="CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective.get("id"),
        )
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH,
                "This assignment was created for a different employee. HR must have entered your exact email or username "
                "(e.g. jane@relopass.com or janedoe) when assigning the case.",
            ),
        )

    if db.is_assignment_auto_claim_blocked_by_revoked_invites(assignment_id):
        identity_event(
            "identity.claim.manual.failed",
            failure_code="CLAIM_INVITE_REVOKED",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective.get("id"),
        )
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_INVITE_REVOKED,
                "This invitation was cancelled by HR. Contact HR if you still need access to this case.",
            ),
        )

    emp_uid = assignment.get("employee_user_id")
    effective_id = str(effective["id"]).strip()
    emp_uid_str = str(emp_uid).strip() if emp_uid else ""
    # Already linked to this user (same id) -> success
    if emp_uid_str and emp_uid_str == effective_id:
        identity_event(
            "identity.claim.manual",
            outcome="idempotent_already_linked",
            request_id=claim_req_id or None,
            assignment_id=assignment_id,
            auth_user_id=effective_id,
            principal_fingerprint=principal_fingerprint(effective.get("email"), effective.get("username")),
        )
        return {"success": True, "assignmentId": assignment_id}
    # Linked to another id but assignment is for this person (identifier match) -> allow claim and attach this user
    if emp_uid_str and emp_uid_str != effective_id:
        if not ident_match:
            identity_event(
                "identity.claim.manual.failed",
                failure_code="CLAIM_ASSIGNMENT_ALREADY_CLAIMED",
                request_id=claim_req_id or None,
                assignment_id=assignment_id,
                auth_user_id=effective_id,
            )
            raise HTTPException(
                status_code=403,
                detail=err_detail(
                    IdentityErrorCode.CLAIM_ASSIGNMENT_ALREADY_CLAIMED,
                    "Assignment already claimed by another account.",
                ),
            )
        # Same person (e.g. assignment has profile id, user logged in with user id): attach and proceed

    finalize_assignment_claim_attach(
        db,
        assignment_id=assignment_id,
        employee_user_id=effective["id"],
        assignment=assignment,
        request_id=None,
        identity_event_name="identity.claim.manual",
        identity_outcome="attached",
        claim_req_id=claim_req_id,
        principal_email=effective.get("email"),
        principal_username=effective.get("username"),
        case_event_payload={},
    )
    return {"success": True, "assignmentId": assignment_id}


@app.post("/api/employee/assignments/{assignment_id}/link-pending")
def link_pending_assignment(
    request: Request,
    assignment_id: str,
    claim: ClaimAssignmentRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    """
    Explicit link for hub "pending" rows only: pending_claim + contact already linked to this user +
    overview-equivalent company alignment + invite gates. Idempotent when already linked to caller.
    """
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    claim_req_id = getattr(request.state, "request_id", None) or ""
    fail_ev = "identity.claim.pending_explicit.failed"

    user_identifiers = _validated_employee_claim_identifiers(
        effective,
        claim,
        claim_req_id=claim_req_id,
        assignment_id=assignment_id,
        failure_event=fail_ev,
    )

    res = execute_pending_explicit_link(
        db,
        auth_user_id=str(effective["id"]).strip(),
        assignment_id=assignment_id,
        user_identifiers=user_identifiers,
        request_id=claim_req_id or None,
        claim_req_id=claim_req_id,
        principal_email=effective.get("email"),
        principal_username=effective.get("username"),
    )

    if res.get("success"):
        return {
            "success": True,
            "assignmentId": res.get("assignmentId"),
            "alreadyLinked": bool(res.get("alreadyLinked")),
        }

    reason = res.get("reason") or "unknown"
    aid = res.get("assignmentId") or assignment_id
    eff_id = str(effective["id"]).strip()

    identity_event(
        fail_ev,
        failure_code=str(reason).upper(),
        request_id=claim_req_id or None,
        assignment_id=aid,
        auth_user_id=eff_id,
    )

    if reason == PENDING_LINK_NOT_FOUND:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if reason == PENDING_LINK_OTHER_OWNER:
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_ASSIGNMENT_ALREADY_CLAIMED,
                "Assignment already linked to another account.",
            ),
        )
    if reason == PENDING_LINK_NOT_PENDING:
        raise HTTPException(
            status_code=409,
            detail=err_detail(
                IdentityErrorCode.CLAIM_ASSIGNMENT_NOT_PENDING,
                "This assignment is not waiting for explicit link. Use manual claim with your assignment ID if HR gave you one.",
            ),
        )
    if reason in (PENDING_LINK_NO_CONTACT, PENDING_LINK_CONTACT_NOT_LINKED):
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_PENDING_CONTACT_MISMATCH,
                "This assignment is not linked to your profile for self-serve linking. Contact HR or use manual assignment ID entry.",
            ),
        )
    if reason == PENDING_LINK_IDENTITY_MISMATCH:
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_ASSIGNMENT_IDENTIFIER_MISMATCH,
                "This assignment was created for a different employee. HR must have entered your exact email or username when assigning the case.",
            ),
        )
    if reason == PENDING_LINK_COMPANY_MISMATCH:
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_PENDING_COMPANY_MISMATCH,
                "Company details for this assignment do not match your contact record. Contact HR to fix the assignment.",
            ),
        )
    if reason == PENDING_LINK_INVITE_REVOKED:
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_INVITE_REVOKED,
                "This invitation was cancelled by HR. Contact HR if you still need access to this case.",
            ),
        )
    if reason == PENDING_LINK_EXTRA_VERIFICATION:
        raise HTTPException(
            status_code=403,
            detail=err_detail(
                IdentityErrorCode.CLAIM_EXTRA_VERIFICATION_REQUIRED,
                "Additional HR verification is required before this assignment can be linked. Contact your HR contact.",
            ),
        )

    raise HTTPException(status_code=400, detail="Unable to link assignment")


@app.get("/api/employee/journey/next-question", response_model=EmployeeJourneyNextQuestion)
def employee_next_question(
    assignmentId: str = Query(..., alias="assignmentId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    effective = _effective_user(user, UserRole.EMPLOYEE)
    assignment = db.get_assignment_by_id(assignmentId)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != effective["id"]:
        raise HTTPException(status_code=403, detail="Assignment not assigned to user")

    return _build_employee_journey_payload(assignment)


@app.post("/api/employee/journey/answer", response_model=EmployeeJourneyNextQuestion)
def employee_submit_answer(
    request: EmployeeJourneyRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    assignment = db.get_assignment_by_id(request.assignmentId)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != effective["id"]:
        raise HTTPException(status_code=403, detail="Assignment not assigned to user")
    normalized_status = normalize_status(assignment["status"])
    if normalized_status in [
        AssignmentStatus.SUBMITTED.value,
        AssignmentStatus.APPROVED.value,
        AssignmentStatus.REJECTED.value,
        AssignmentStatus.CLOSED.value,
    ]:
        raise HTTPException(status_code=400, detail="Assignment is read-only")

    profile = db.get_employee_profile(request.assignmentId)
    if not profile:
        profile = RelocationProfile(userId=request.assignmentId).model_dump()

    profile = orchestrator.apply_answer(profile, request.questionId, request.answer, False)
    db.save_employee_profile(request.assignmentId, profile)
    db.save_employee_answer(request.assignmentId, request.questionId, request.answer)

    if normalized_status in [AssignmentStatus.CREATED.value, AssignmentStatus.ASSIGNED.value]:
        # First meaningful employee input moves the assignment into awaiting_intake.
        assert_canonical_status(AssignmentStatus.AWAITING_INTAKE.value)
        db.update_assignment_status(request.assignmentId, AssignmentStatus.AWAITING_INTAKE.value)

    assignment = db.get_assignment_by_id(request.assignmentId)
    return _build_employee_journey_payload(assignment)


def _draft_to_relocation_profile(draft: Dict[str, Any], assignment_id: str) -> Dict[str, Any]:
    """Convert wizard Case draft to RelocationProfile format for submission checks."""
    basics = draft.get("relocationBasics", {}) or {}
    ep = draft.get("employeeProfile", {}) or {}
    fm = draft.get("familyMembers", {}) or {}
    ac = draft.get("assignmentContext", {}) or {}
    origin = ", ".join(filter(None, [basics.get("originCity"), basics.get("originCountry")])) or "Unknown"
    dest = ", ".join(filter(None, [basics.get("destCity"), basics.get("destCountry")])) or "Unknown"
    profile: Dict[str, Any] = {
        "userId": assignment_id,
        "familySize": 1,
        "movePlan": {
            "origin": origin,
            "destination": dest,
            "targetArrivalDate": basics.get("targetMoveDate"),
        },
        "primaryApplicant": {
            "fullName": ep.get("fullName"),
            "nationality": ep.get("nationality"),
            "passport": {
                "expiryDate": ep.get("passportExpiry"),
                "issuingCountry": ep.get("passportCountry"),
            },
            "employer": {"name": ac.get("employerName"), "roleTitle": ac.get("jobTitle")},
            "assignment": {"startDate": ac.get("contractStartDate")},
        },
        "maritalStatus": fm.get("maritalStatus"),
        "spouse": {"fullName": (fm.get("spouse") or {}).get("fullName")},
        "dependents": [],
    }
    for c in (fm.get("children") or []):
        profile["dependents"].append({
            "firstName": (c or {}).get("fullName", "").split()[0] if (c or {}).get("fullName") else None,
            "dateOfBirth": (c or {}).get("dateOfBirth"),
        })
    emp = profile["primaryApplicant"].setdefault("employer", {})
    if ac.get("contractType"):
        emp["contractType"] = ac["contractType"]
    if ac.get("salaryBand"):
        emp["salaryBand"] = ac["salaryBand"]
    return profile


def _merge_profiles(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge update into base; update wins for leaf values."""
    result = dict(base)
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge_profiles(result[k], v)
        else:
            result[k] = v
    return result


@app.post("/api/employee/assignments/{assignment_id}/submit")
def submit_assignment(assignment_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != effective["id"]:
        raise HTTPException(status_code=403, detail="Assignment not assigned to user")

    profile = db.get_employee_profile(assignment_id)
    wizard_complete = False
    # If profile missing/incomplete, try syncing from wizard Case draft (wizard may use assignment_id or case_id as URL param)
    if not profile or (orchestrator.compute_completion_state(profile).get("profileCompleteness", 0) < 90):
        with SessionLocal() as session:
            case = app_crud.get_case(session, assignment_id) or (
                app_crud.get_case(session, assignment.get("case_id", "")) if assignment.get("case_id") else None
            )
            if case:
                draft = json.loads(case.draft_json)
                basics = draft.get("relocationBasics", {}) or {}
                required_basics = ["originCountry", "originCity", "destCountry", "destCity", "purpose", "targetMoveDate"]
                # Sync whenever wizard has step 1 basics; wizard_complete bypasses 90% check
                if all(basics.get(k) for k in required_basics):
                    wizard_profile = _draft_to_relocation_profile(draft, assignment_id)
                    profile = _merge_profiles(profile or {}, wizard_profile) if profile else wizard_profile
                    db.save_employee_profile(assignment_id, profile)
                    wizard_complete = True

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Profile is not complete. Please complete all 5 wizard steps (Relocation Basics, Employee Profile, Family, Assignment Context) and try again.",
        )
    completion_state = orchestrator.compute_completion_state(profile)
    if not wizard_complete and completion_state.get("profileCompleteness", 0) < 90:
        raise HTTPException(
            status_code=400,
            detail="Profile is not complete. Please fill in all required fields in the wizard steps (Relocation Basics, Employee Profile, Family, Assignment Context).",
        )

    db.set_assignment_submitted(assignment_id)

    case_id = assignment.get("case_id") or ""
    event_type = "assignment.submitted"
    try:
        db.insert_case_event(
            case_id=case_id,
            assignment_id=assignment_id,
            actor_principal_id=effective["id"],
            event_type=event_type,
            payload={},
        )
    except Exception as exc:
        log.error(
            "event_insert_error assignment_id=%s case_id=%s event_type=%s error=%s",
            assignment_id,
            case_id,
            event_type,
            str(exc),
            exc_info=True,
        )
        raise

    return {"success": True}


@app.post("/api/employee/assignments/{assignment_id}/photo")
def update_profile_photo(
    assignment_id: str,
    request: UpdateProfilePhotoRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    if assignment_id != request.assignmentId:
        raise HTTPException(status_code=400, detail="Assignment mismatch")

    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Assignment not assigned to user")

    profile = db.get_employee_profile(assignment_id)
    if not profile:
        profile = RelocationProfile(userId=assignment_id).model_dump()
    profile.setdefault("primaryApplicant", {})
    profile["primaryApplicant"]["photoUrl"] = request.photoUrl
    db.save_employee_profile(assignment_id, profile)
    return {"success": True}


@app.get("/api/hr/assignments", response_model=AssignmentsListResponse)
def list_hr_assignments(
    request: Request,
    limit: int = Query(25, ge=1, le=100, description="Max assignments per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    search: Optional[str] = Query(None, description="Search by employee name or email"),
    status: Optional[str] = Query(None, description="Filter by status"),
    destination: Optional[str] = Query(None, description="Filter by destination (host/home country)"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    List HR assignments (summary only). Paginated, server-side filtered. No per-row compliance N+1.
    - Auth: HR (or ADMIN).
    - Returns lightweight summary; use GET /api/hr/assignments/{id} for full detail.
    """
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    t0 = time.perf_counter()
    try:
        if user.get("is_admin") and not user.get("impersonation"):
            with timed("db.list_all_assignments", request_id):
                assignments = db.list_all_assignments()
            total = len(assignments)
            assignments = assignments[offset : offset + limit]
        else:
            effective = _effective_user(user, UserRole.HR)
            company_id = _get_hr_company_id(effective)
            if company_id:
                with timed("db.list_assignments_for_company_paginated", request_id):
                    assignments, total = db.list_assignments_for_company_paginated(
                        company_id,
                        limit=limit,
                        offset=offset,
                        search=search,
                        status=status,
                        destination=destination,
                        request_id=request_id,
                    )
            else:
                with timed("db.list_assignments_for_hr", request_id):
                    all_assignments = db.list_assignments_for_hr(effective["id"], request_id=request_id)
                total = len(all_assignments)
                assignments = all_assignments[offset : offset + limit]

        if not assignments:
            dur_ms = (time.perf_counter() - t0) * 1000
            _log_endpoint_perf("/api/hr/assignments", request_id, user.get("id"), dur_ms, 200)
            return AssignmentsListResponse(assignments=[], total=total)

        case_ids = [a.get("case_id") for a in assignments if a.get("case_id")]
        cases_by_id: Dict[str, Any] = {}
        unique_ids = list({cid for cid in case_ids if cid})
        if unique_ids:
            placeholders = ", ".join(f":id{i}" for i in range(len(unique_ids)))
            sql = (
                "SELECT id, status, stage, home_country, host_country, "
                "employee_id, company_id "
                "FROM relocation_cases WHERE id IN (" + placeholders + ")"
            )
            params = {f"id{i}": cid for i, cid in enumerate(unique_ids)}
            with db.engine.connect() as conn, timed("db.load_relocation_cases_bulk", request_id):
                rows = conn.execute(text(sql), params).fetchall()
            for row in rows:
                m = row._mapping
                cases_by_id[m["id"]] = {
                    "id": m["id"],
                    "status": m.get("status"),
                    "stage": m.get("stage"),
                    "home_country": m.get("home_country"),
                    "host_country": m.get("host_country"),
                    "employee_id": m.get("employee_id"),
                    "company_id": m.get("company_id"),
                }

        summaries: List[AssignmentSummary] = []
        for assignment in assignments:
            case_meta = cases_by_id.get(assignment.get("case_id"))
            case_id = assignment.get("case_id") or assignment.get("id") or ""
            submitted_at = assignment.get("submitted_at")
            if isinstance(submitted_at, datetime):
                submitted_at_str = submitted_at.isoformat()
            else:
                submitted_at_str = submitted_at
            summaries.append(AssignmentSummary(
                id=assignment["id"],
                caseId=case_id,
                employeeIdentifier=assignment["employee_identifier"],
                status=AssignmentStatus(normalize_status(assignment["status"])),
                submittedAt=submitted_at_str,
                complianceStatus=None,
                employeeFirstName=assignment.get("employee_first_name"),
                employeeLastName=assignment.get("employee_last_name"),
                case=case_meta,
            ))
        dur_ms = (time.perf_counter() - t0) * 1000
        _log_endpoint_perf("/api/hr/assignments", request_id, user.get("id"), dur_ms, 200)
        return AssignmentsListResponse(assignments=summaries, total=total)
    except Exception as e:
        # Structured error log with request_id and user identity.
        log.error(
            "request_id=%s method=GET route=/api/hr/assignments user_id=%s email=%s error=%s",
            request_id,
            user.get("id"),
            user.get("email"),
            repr(e),
            exc_info=True,
        )
        dur_ms = (time.perf_counter() - t0) * 1000
        _log_endpoint_perf("/api/hr/assignments", request_id, user.get("id"), dur_ms, 500)
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to load assignments", "request_id": request_id},
        )


@app.get("/api/debug/supabase")
def debug_supabase():
    """
    Lightweight Supabase admin connectivity check.
    - Verifies SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are present.
    - Runs a small SELECT via service-role client.
    """
    request_id = str(uuid.uuid4())
    supabase_url_present = bool(os.getenv("SUPABASE_URL"))
    service_role_present = bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    if not supabase_url_present or not service_role_present:
        log.error(
            "request_id=%s supabase debug missing envs: url_present=%s service_role_present=%s",
            request_id,
            supabase_url_present,
            service_role_present,
        )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "Supabase environment variables missing",
                "supabase_url_present": supabase_url_present,
                "service_role_key_present": service_role_present,
                "request_id": request_id,
            },
        )

    try:
        client = get_supabase_admin_client()
        # Lightweight query: try to select a single row (or none) from notifications.
        res = client.table("notifications").select("id").limit(1).execute()
        db_ok = res is not None
        return {
            "ok": True,
            "db_ok": db_ok,
            "supabase_url_present": True,
            "service_role_key_present": True,
            "request_id": request_id,
        }
    except Exception as e:
        log.error("request_id=%s supabase debug query failed: %s", request_id, e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "Supabase query failed",
                "supabase_url_present": True,
                "service_role_key_present": True,
                "request_id": request_id,
            },
        )


@app.get("/api/hr/messages")
def list_hr_messages(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    effective = _effective_user(user, UserRole.HR)
    items = db.list_messages_for_hr(effective["id"])
    return {"messages": items}


class HrConversationsArchiveRequest(BaseModel):
    assignment_ids: List[str]
    archived: bool = True


@app.get("/api/hr/messages/conversations")
def list_hr_message_conversations(
    q: Optional[str] = Query(None, description="Search name, email, identifier, case id"),
    archive: str = Query("active", description="active | archived | all"),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Company-scoped conversation summaries (one row per assignment / case thread)."""
    effective = _effective_user(user, UserRole.HR)
    pref_user_id = effective.get("id") or ""
    is_admin = bool(effective.get("is_admin"))
    hr_cid = None if is_admin else _get_hr_company_id(effective)
    archive_norm = archive if archive in ("active", "archived", "all") else "active"
    rows = db.list_hr_conversation_summaries(
        hr_user_id=pref_user_id,
        hr_company_id=hr_cid,
        is_admin=is_admin,
        search_q=q,
        archive_filter=archive_norm,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return {"conversations": rows, "has_more": len(rows) >= limit}


@app.get("/api/hr/messages/threads/{assignment_id}")
def get_hr_message_thread(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Full message history for one assignment; authorized via same rules as assignment detail."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    aid = assignment["id"]
    items = db.list_messages_by_assignment(aid)
    return {"assignment_id": aid, "messages": items}


@app.post("/api/hr/messages/conversations/archive")
def archive_hr_message_conversations(
    request: HrConversationsArchiveRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Soft-archive or restore conversations for the current user (non-destructive).
    archived=true sets archived_at; archived=false removes the preference row (visible in active list again).
    """
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    pref_user_id = effective.get("id") or ""
    if not request.assignment_ids:
        raise HTTPException(status_code=400, detail="assignment_ids required")
    normalized: List[str] = []
    for raw_id in request.assignment_ids:
        aid = (raw_id or "").strip()
        if not aid:
            continue
        assignment = db.get_assignment_by_id(aid)
        if not assignment:
            raise HTTPException(status_code=404, detail=f"Assignment not found: {aid}")
        if not _hr_can_access_assignment(assignment, user):
            raise HTTPException(status_code=403, detail="Not authorized for this assignment")
        normalized.append(assignment["id"])
    for aid in normalized:
        db.upsert_message_conversation_pref(pref_user_id, aid, request.archived)
    return {"ok": True, "updated": len(normalized)}


@app.delete("/api/hr/messages/{message_id}")
def delete_hr_message(
    message_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Permanently remove one message from an assignment thread.
    Authorized when the caller can access the message's assignment (same rules as thread view).
    """
    _deny_if_impersonating(user)
    mid = (message_id or "").strip()
    if not mid:
        raise HTTPException(status_code=400, detail="message_id required")
    row = db.get_message_by_id(mid)
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    aid = row.get("assignment_id")
    if not aid:
        raise HTTPException(status_code=400, detail="Message has no assignment")
    assignment = db.get_assignment_by_id(str(aid)) or db.get_assignment_by_case_id(str(aid))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this message")
    deleted = db.delete_message_by_id(mid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}


# Message state / notification bell (HR + Employee)
@app.get("/api/messages/unread-count")
def get_message_unread_count(user: Dict[str, Any] = Depends(require_hr_or_employee)):
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    count = db.get_unread_message_count(effective["id"])
    return {"count": count}


@app.get("/api/messages/unread-list")
def list_message_unread(
    limit: int = 20,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    items = db.list_unread_message_notifications(effective["id"], limit=min(limit, 50))
    return {"notifications": items}


class MarkConversationReadRequest(BaseModel):
    assignment_id: Optional[str] = None
    conversation_id: Optional[str] = None


class CaseServiceItem(BaseModel):
    service_key: str
    category: str
    selected: bool = True
    estimated_cost: Optional[float] = None
    currency: Optional[str] = None


class CaseServicesUpsert(BaseModel):
    services: List[CaseServiceItem]


class ServiceAnswerItem(BaseModel):
    service_key: str
    answers: Dict[str, Any]


class ServiceAnswersUpsert(BaseModel):
    case_id: str
    items: List[ServiceAnswerItem]


class RfqItemInput(BaseModel):
    service_key: str
    requirements: Dict[str, Any] = {}


class RfqCreatePayload(BaseModel):
    case_id: str
    items: List[RfqItemInput]
    vendor_ids: Optional[List[str]] = None
    supplier_ids: Optional[List[str]] = None


class QuoteLineInput(BaseModel):
    label: str
    amount: float


class QuoteCreatePayload(BaseModel):
    total_amount: float
    currency: str
    valid_until: Optional[str] = None
    status: str = "proposed"
    quote_lines: List[QuoteLineInput]


class PolicyBenefitItem(BaseModel):
    service_category: str
    benefit_key: str
    benefit_label: str
    eligibility: Optional[Dict[str, Any]] = None
    limits: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    source_quote: Optional[str] = None
    source_section: Optional[str] = None
    confidence: Optional[float] = None


class PolicyBenefitsUpsert(BaseModel):
    benefits: List[PolicyBenefitItem]


@app.post("/api/messages/mark-conversation-read")
def mark_conversation_read(
    req: MarkConversationReadRequest,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    assignment_id = req.assignment_id or req.conversation_id
    if not assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id or conversation_id required")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    aid = assignment["id"]
    if effective.get("role") == UserRole.EMPLOYEE.value:
        if assignment.get("employee_user_id") != effective.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    else:
        if not _hr_can_access_assignment(assignment, user):
            raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    db.mark_conversation_read(aid, effective["id"])
    return {"success": True}


@app.post("/api/messages/dismiss/{message_id}")
def dismiss_message_notification(
    message_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    updated = db.dismiss_message_notification(message_id, effective["id"])
    return {"success": updated}


@app.delete("/api/hr/assignments/{assignment_id}")
def delete_hr_assignment(assignment_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    deleted = db.delete_assignment(assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"success": True, "deleted": assignment_id}


def _hr_assignment_case_route_hints(case_row: Optional[Dict[str, Any]]) -> tuple:
    """
    Origin/destination hints from relocation_cases only (existing stored data).
    Precedence: relocationBasics in profile_json (wizard draft), then home_country / host_country.
    """
    if not case_row:
        return None, None
    origin = (case_row.get("home_country") or "").strip() or None
    dest = (case_row.get("host_country") or "").strip() or None
    raw = case_row.get("profile_json")
    if not raw:
        return origin, dest
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            rb = data.get("relocationBasics") or {}
            oc = (rb.get("originCountry") or "").strip()
            dc = (rb.get("destCountry") or "").strip()
            if oc:
                origin = oc
            if dc:
                dest = dc
    except Exception:
        pass
    return origin, dest


@app.get("/api/hr/assignments/{assignment_id}", response_model=AssignmentDetail)
def get_hr_assignment(
    request: Request,
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    req_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if not _hr_can_access_assignment(assignment, user):
            raise HTTPException(status_code=403, detail="Not authorized for this assignment")

        aid = assignment["id"]
        case_id = assignment.get("case_id") or assignment.get("id") or ""
        if not case_id:
            log.warning("request_id=%s assignment_id=%s assignment has no case_id", req_id, assignment_id)

        profile = None
        try:
            profile = db.get_employee_profile(aid)
        except Exception as e:
            log.warning(
                "request_id=%s assignment_id=%s get_employee_profile failed: %s",
                req_id, assignment_id, e, exc_info=True,
            )

        report = None
        try:
            report = db.get_latest_compliance_report(aid)
        except Exception as e:
            log.warning(
                "request_id=%s assignment_id=%s get_latest_compliance_report failed: %s",
                req_id, assignment_id, e, exc_info=True,
            )

        completeness = None
        if profile:
            try:
                completion_state = orchestrator.compute_completion_state(profile)
                completeness = completion_state.get("profileCompleteness", 0)
            except Exception as e:
                log.warning(
                    "request_id=%s assignment_id=%s compute_completion_state failed: %s",
                    req_id, assignment_id, e, exc_info=True,
                )

        parsed_profile = None
        if profile:
            try:
                parsed_profile = RelocationProfile(**profile)
            except Exception as e:
                log.warning(
                    "request_id=%s assignment_id=%s RelocationProfile validation failed: %s",
                    req_id, assignment_id, e, exc_info=True,
                )

        submitted_at = assignment.get("submitted_at")
        if isinstance(submitted_at, datetime):
            submitted_at_str = submitted_at.isoformat()
        else:
            submitted_at_str = str(submitted_at) if submitted_at is not None else None

        case_row = None
        try:
            if case_id:
                case_row = db.get_case_by_id(case_id)
        except Exception as e:
            log.warning(
                "request_id=%s assignment_id=%s get_case_by_id failed: %s",
                req_id,
                assignment_id,
                e,
            )
        case_origin_hint, case_dest_hint = _hr_assignment_case_route_hints(case_row)

        linked_email = None
        linked_full_name = None
        emp_uid = assignment.get("employee_user_id")
        if emp_uid:
            try:
                prec = db.get_profile_record(str(emp_uid))
                if prec:
                    linked_email = prec.get("email")
                    linked_full_name = prec.get("full_name")
            except Exception as e:
                log.warning(
                    "request_id=%s assignment_id=%s get_profile_record failed: %s",
                    req_id,
                    assignment_id,
                    e,
                )

        readiness_snap: Optional[Dict[str, Any]] = None
        try:
            readiness_snap = db.get_hr_readiness_summary(aid)
        except Exception as e:
            log.warning(
                "request_id=%s assignment_id=%s get_hr_readiness_summary failed: %s",
                req_id,
                assignment_id,
                e,
            )
            readiness_snap = {
                "resolved": False,
                "reason": "error",
                "user_message": "Readiness summary temporarily unavailable.",
            }

        profile_dict = profile if isinstance(profile, dict) else None
        intake_raw = build_intake_checklist_items(profile_dict)
        ui_raw = build_hr_case_readiness_ui(
            profile=profile_dict,
            intake_items=intake_raw,
            readiness_snap=readiness_snap,
            compliance_report=report,
        )
        case_readiness_ui: Optional[CaseReadinessUi] = None
        try:
            case_readiness_ui = CaseReadinessUi.model_validate(ui_raw)
        except Exception as e:
            log.warning(
                "request_id=%s assignment_id=%s CaseReadinessUi validation failed: %s",
                req_id,
                assignment_id,
                e,
            )

        intake_models: List[IntakeChecklistItem] = []
        for row in intake_raw:
            try:
                intake_models.append(IntakeChecklistItem(**row))
            except Exception:
                continue

        dur_ms = (time.perf_counter() - start) * 1000
        log.info(
            "request_id=%s assignment_id=%s get_hr_assignment ok dur_ms=%.2f",
            req_id, assignment_id, dur_ms,
        )
        return AssignmentDetail(
            id=aid,
            caseId=case_id,
            employeeIdentifier=assignment.get("employee_identifier") or "",
            status=AssignmentStatus(normalize_status(assignment.get("status"))),
            submittedAt=submitted_at_str,
            hrNotes=assignment.get("hr_notes"),
            profile=parsed_profile,
            completeness=completeness,
            complianceReport=report,
            employeeFirstName=assignment.get("employee_first_name"),
            employeeLastName=assignment.get("employee_last_name"),
            employeeEmail=linked_email,
            linkedEmployeeFullName=linked_full_name,
            caseOriginHint=case_origin_hint,
            caseDestinationHint=case_dest_hint,
            intakeChecklist=intake_models,
            readinessSnapshot=readiness_snap,
            caseReadinessUi=case_readiness_ui,
        )
    except HTTPException:
        raise
    except Exception as e:
        dur_ms = (time.perf_counter() - start) * 1000
        log.error(
            "request_id=%s assignment_id=%s get_hr_assignment failed dur_ms=%.2f error=%s",
            req_id, assignment_id, dur_ms, repr(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load assignment: {str(e)[:200]}",
        )


def _hr_assignment_or_404(assignment_id: str) -> Dict[str, Any]:
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@app.get("/api/hr/assignments/{assignment_id}/readiness/summary")
def get_hr_assignment_readiness_summary(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Case Readiness Core — compact summary (no full checklist rows)."""
    assignment = _hr_assignment_or_404(assignment_id)
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    aid = assignment["id"]
    return db.get_hr_readiness_summary(aid)


@app.get("/api/hr/assignments/{assignment_id}/readiness/detail")
def get_hr_assignment_readiness_detail(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Full checklist + milestones with case state (load after summary / when panel expanded)."""
    assignment = _hr_assignment_or_404(assignment_id)
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    aid = assignment["id"]
    return db.get_hr_readiness_detail(aid)


@app.patch("/api/hr/assignments/{assignment_id}/readiness/checklist-items/{item_id}")
def patch_hr_readiness_checklist_item(
    assignment_id: str,
    item_id: str,
    body: ReadinessChecklistPatchRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    _deny_if_impersonating(user)
    assignment = _hr_assignment_or_404(assignment_id)
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    aid = assignment["id"]
    bind = db.ensure_case_readiness_binding(aid)
    if not bind:
        raise HTTPException(status_code=400, detail="Readiness not bound for this case (destination or template missing)")
    tid = bind.get("template_id")
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM readiness_template_checklist_items WHERE id = :iid AND template_id = :tid"),
            {"iid": item_id, "tid": tid},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Checklist item not found for this readiness template")
    try:
        db.upsert_readiness_checklist_state(aid, item_id, body.status.strip().lower(), body.notes)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    return {"success": True}


@app.patch("/api/hr/assignments/{assignment_id}/readiness/milestones/{milestone_id}")
def patch_hr_readiness_milestone(
    assignment_id: str,
    milestone_id: str,
    body: ReadinessMilestonePatchRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    _deny_if_impersonating(user)
    assignment = _hr_assignment_or_404(assignment_id)
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    aid = assignment["id"]
    bind = db.ensure_case_readiness_binding(aid)
    if not bind:
        raise HTTPException(status_code=400, detail="Readiness not bound for this case (destination or template missing)")
    tid = bind.get("template_id")
    with db.engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM readiness_template_milestones WHERE id = :mid AND template_id = :tid"),
            {"mid": milestone_id, "tid": tid},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Milestone not found for this readiness template")
    db.upsert_readiness_milestone_state(aid, milestone_id, body.completed, body.notes)
    return {"success": True}


@app.get("/api/hr/assignments/{assignment_id}/resolved-policy")
def get_hr_resolved_policy(
    assignment_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR: Get resolved policy for assignment with diagnostics and context."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")

    from .services.policy_resolution import resolve_policy_for_assignment
    case_id = assignment.get("case_id")
    case = db.get_relocation_case(case_id) if case_id else None
    profile = None
    if case and case.get("profile_json"):
        try:
            profile = json.loads(case["profile_json"]) if isinstance(case["profile_json"], str) else case["profile_json"]
        except Exception:
            profile = None
    employee_profile = db.get_employee_profile(assignment_id)

    resolved = db.get_resolved_assignment_policy(assignment_id)
    if not resolved:
        resolved = resolve_policy_for_assignment(
            db, assignment_id, assignment, case, profile, employee_profile
        )
    if not resolved:
        return {
            "resolved": None,
            "message": "No published policy version for this company. Publish a policy in HR Policy Review.",
        }
    benefits = db.list_resolved_policy_benefits(resolved["id"])
    exclusions = db.list_resolved_policy_exclusions(resolved["id"])
    return {
        "resolved": {
            **resolved,
            "benefits": benefits,
            "exclusions": exclusions,
        },
        "policy_version": resolved.get("version"),
        "resolution_context": resolved.get("resolution_context", {}),
    }


@app.post("/api/hr/assignments/{assignment_id}/resolved-policy/recompute")
def recompute_resolved_policy(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR: Force recompute resolved policy (e.g. after policy republish)."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")

    from .services.policy_resolution import resolve_policy_for_assignment
    case_id = assignment.get("case_id")
    case = db.get_relocation_case(case_id) if case_id else None
    profile = None
    if case and case.get("profile_json"):
        try:
            profile = json.loads(case["profile_json"]) if isinstance(case["profile_json"], str) else case["profile_json"]
        except Exception:
            profile = None
    employee_profile = db.get_employee_profile(assignment_id)

    resolved = resolve_policy_for_assignment(
        db, assignment_id, assignment, case, profile, employee_profile
    )
    if not resolved:
        return {"resolved": None, "message": "No published policy. Publish a policy first."}
    benefits = db.list_resolved_policy_benefits(resolved["id"])
    exclusions = db.list_resolved_policy_exclusions(resolved["id"])
    return {
        "resolved": {**resolved, "benefits": benefits, "exclusions": exclusions},
        "policy_version": resolved.get("version"),
    }


@app.post("/api/hr/assignments/{assignment_id}/feedback")
def post_hr_feedback(
    assignment_id: str,
    request: HrFeedbackRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR))
):
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    effective = _effective_user(user, UserRole.HR)
    message = (request.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    row = db.insert_hr_feedback(
        feedback_id=str(uuid.uuid4()),
        assignment_id=assignment_id,
        hr_user_id=effective["id"],
        employee_user_id=assignment.get("employee_user_id"),
        message=message,
    )
    emp_id = assignment.get("employee_user_id")
    if emp_id:
        try:
            db.create_notification_with_preferences(
                user_id=emp_id,
                type_="HR_FEEDBACK_POSTED",
                title="New feedback from HR",
                body=(message[:120] + "…") if len(message) > 120 else message,
                assignment_id=assignment_id,
                case_id=assignment.get("case_id"),
                metadata={"feedback_id": row["id"], "assignment_id": assignment_id},
            )
        except Exception as e:
            try:
                db.insert_notification(
                    notification_id=str(uuid.uuid4()),
                    user_id=emp_id,
                    type_="HR_FEEDBACK_POSTED",
                    title="New feedback from HR",
                    body=(message[:120] + "…") if len(message) > 120 else message,
                    assignment_id=assignment_id,
                    case_id=assignment.get("case_id"),
                    metadata={"feedback_id": row["id"], "assignment_id": assignment_id},
                )
            except Exception as e2:
                log.warning("Failed to create notification for HR feedback: %s", e2)
    return {"ok": True, "id": row["id"], "created_at": row["created_at"]}


@app.get("/api/hr/assignments/{assignment_id}/feedback")
def get_hr_feedback(assignment_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    rows = db.list_hr_feedback(assignment_id)
    return [
        {"id": r["id"], "assignment_id": r["assignment_id"], "hr_user_id": r["hr_user_id"], "employee_user_id": r.get("employee_user_id"), "message": r["message"], "created_at": r["created_at"]}
        for r in rows
    ]


@app.get("/api/employee/assignment-feedback")
def get_employee_assignment_feedback(assignment_id: str = Query(...), user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))):
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    effective = _effective_user(user, UserRole.EMPLOYEE)
    if assignment.get("employee_user_id") != effective["id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    rows = db.list_hr_feedback(assignment_id)
    return [
        {"id": r["id"], "assignment_id": r["assignment_id"], "message": r["message"], "created_at": r["created_at"]}
        for r in rows
    ]


@app.get("/api/case-details-by-assignment")
def get_case_details_by_assignment(
    assignment_id: str = Query(..., description="Assignment id (gate for access)"),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """
    Load case details through the assignment relationship only.
    Access is gated by case_assignments (user must be employee or HR for this assignment).
    """
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found or not visible under RLS")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    effective_id = str(effective["id"]).strip()
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    visible = False
    if is_employee and emp_id and str(emp_id).strip() == effective_id:
        visible = True
    if is_employee and not emp_id:
        ident = (assignment.get("employee_identifier") or "").strip().lower()
        user_ids = [x.lower() for x in [effective.get("email"), effective.get("username")] if x]
        if ident and user_ids and ident in user_ids:
            visible = True
    if is_hr and (effective.get("is_admin") or (hr_id and str(hr_id).strip() == effective_id)):
        visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Assignment not found or not visible under RLS")
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case_id")

    # Prefill employer name/country from company profile (source of truth for HR)
    company = None
    employer_name = None
    employer_country = None
    if hr_id:
        company = db.get_company_for_user(hr_id)
    if not company and case_id:
        case_row = db.get_case_by_id(case_id)
        cid = case_row.get("company_id") if case_row else None
        if cid:
            company = db.get_company(cid)
    if company:
        employer_name = company.get("name") or company.get("legal_name")
        employer_country = company.get("country")

    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if not case:
            case = app_crud.create_case(session, case_id, {
                "relocationBasics": {},
                "employeeProfile": {},
                "familyMembers": {},
                "assignmentContext": {},
            })
        draft = json.loads(case.draft_json or "{}")
        ac = draft.get("assignmentContext") or {}
        # Employer name/country are source-of-truth from company profile; always override when available
        if company:
            ac["employerName"] = employer_name or ""
            ac["employerCountry"] = employer_country or ""
        draft["assignmentContext"] = ac
        case_dto = cases_router._case_dto(case, draft)
    # Ensure destCity/destCountry come from draft, then from relocation_cases.host_country (assignment destination)
    case_dump = case_dto.model_dump(mode="json")
    basics = draft.get("relocationBasics") or {}
    if not case_dump.get("destCity") and basics.get("destCity"):
        case_dump["destCity"] = basics.get("destCity")
    if not case_dump.get("destCountry") and basics.get("destCountry"):
        case_dump["destCountry"] = basics.get("destCountry")
    if not case_dump.get("destCountry"):
        case_row = db.get_case_by_id(case_id)
        if case_row and case_row.get("host_country"):
            case_dump["destCountry"] = case_row["host_country"]
    employee_full_name = None
    if emp_id:
        emp_profile = db.get_profile_record(emp_id)
        if emp_profile:
            employee_full_name = emp_profile.get("full_name") or emp_profile.get("email")
    if not employee_full_name and assignment.get("employee_identifier"):
        employee_full_name = assignment["employee_identifier"]
    return {
        "assignment": {
            "id": assignment["id"],
            "case_id": assignment["case_id"],
            "employee_user_id": emp_id,
            "hr_user_id": hr_id,
            "status": assignment.get("status", ""),
            "employee_identifier": assignment.get("employee_identifier"),
            "employee_full_name": employee_full_name,
        },
        "case": case_dump,
    }


@app.get("/api/assignments/{assignment_id}/timeline")
def get_assignment_timeline(
    request: Request,
    assignment_id: str,
    ensure_defaults: bool = Query(False, description="Create default milestones if none exist"),
    include_links: bool = Query(True, description="Include milestone link rows (omit for lighter payloads)"),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """List operational relocation tasks (case_milestones) for the case linked to this assignment."""
    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    milestones = db.list_case_milestones(case_id, request_id=request_id)
    if ensure_defaults and len(milestones) == 0:
        try:
            services = []
            try:
                svc_rows = db.list_case_services(assignment_id, request_id=request_id)
                services = [r["service_key"] for r in svc_rows if r.get("selected") in (True, 1)]
            except Exception:
                pass
            draft, target_move_date = {}, None
            with SessionLocal() as session:
                case = app_crud.get_case(session, case_id)
                if case:
                    try:
                        raw_draft = json.loads(getattr(case, "draft_json", None) or "{}")
                        draft = raw_draft if isinstance(raw_draft, dict) else {}
                    except (json.JSONDecodeError, TypeError, ValueError):
                        draft = {}
                    target_move_date = getattr(case, "target_move_date", None)
            defaults = compute_default_milestones(
                case_id=case_id,
                case_draft=draft,
                selected_services=services,
                target_move_date=str(target_move_date) if target_move_date else None,
            )
            for m in defaults:
                try:
                    db.upsert_case_milestone(
                        case_id=case_id,
                        milestone_type=m["milestone_type"],
                        title=m["title"],
                        description=m.get("description"),
                        target_date=m.get("target_date"),
                        status=m.get("status", "pending"),
                        sort_order=m.get("sort_order", 0),
                        owner=m.get("owner", "joint"),
                        criticality=m.get("criticality", "normal"),
                        notes=m.get("notes"),
                        request_id=request_id,
                    )
                except Exception as upsert_exc:
                    log.warning(
                        "ensure_defaults upsert_case_milestone failed case_id=%s type=%s: %s",
                        case_id,
                        m.get("milestone_type"),
                        upsert_exc,
                        exc_info=True,
                    )
            milestones = db.list_case_milestones(case_id, request_id=request_id)
        except Exception as exc:
            log.warning(
                "get_assignment_timeline ensure_defaults failed assignment_id=%s case_id=%s: %s",
                assignment_id,
                case_id,
                exc,
                exc_info=True,
            )
            milestones = db.list_case_milestones(case_id, request_id=request_id)
    if include_links:
        for m in milestones:
            m["links"] = db.list_milestone_links(m["id"], request_id=request_id)
    else:
        for m in milestones:
            m["links"] = []
    summary = compute_timeline_summary(milestones)
    return {
        "case_id": case_id,
        "assignment_id": assignment_id,
        "milestones": milestones,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Country Resources (personalized by wizard profile)
# ---------------------------------------------------------------------------
def _get_section_content(country_code: str, city: str, section_key: str) -> Dict[str, Any]:
    """Fetch section content from DB (Supabase) if available, else from Python defaults."""
    try:
        supabase = get_supabase_admin_client()
        # Try city-specific first, then country-level (city is null)
        for city_val in ([city] if city else []) + [None]:
            q = (
                supabase.table("country_resource_sections")
                .select("content_json, title")
                .eq("country_code", country_code.upper())
                .eq("section_key", section_key)
            )
            if city_val:
                q = q.eq("city", city_val)
            else:
                q = q.is_("city", "null")
            r = q.limit(1).execute()
            if r.data and len(r.data) > 0:
                return r.data[0].get("content_json") or {}
    except Exception:
        pass
    return get_default_section_content(country_code, city, section_key)


@app.get("/api/resources/country")
def get_country_resources(
    assignment_id: str = Query(..., description="Assignment id (gate for access)"),
    filters: Optional[str] = Query(None, description="JSON filters: city, family_type, budget, category, etc."),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Return profile context, sections, events, and recommended resources for the country Resources page."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found or not visible under RLS")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    eid = effective.get("id")
    visible = (is_employee and eid is not None and emp_id == eid) or (
        is_hr and (effective.get("is_admin") or (eid is not None and hr_id == eid))
    )
    if not visible:
        raise HTTPException(status_code=403, detail="Assignment not found or not visible under RLS")
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case_id")
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if not case:
            draft = {}
        else:
            try:
                draft = json.loads(case.draft_json or "{}")
                if not isinstance(draft, dict):
                    draft = {}
            except (json.JSONDecodeError, TypeError, ValueError):
                draft = {}

    profile = build_profile_context(draft)
    hints = get_personalization_hints(profile)
    country_code = (profile.get("country_code") or "NO").upper()
    city = (profile.get("destination_city") or "").strip()

    filter_dict = {}
    if filters:
        try:
            filter_dict = json.loads(filters)
        except json.JSONDecodeError:
            pass

    # Resource context for personalization
    resource_ctx = get_resource_context(draft)

    # Try RKG structured resources first (when destination is set)
    try:
        rkg_resources = []
        if country_code:
            ff = filter_dict.get("family_friendly")
            if isinstance(ff, str):
                ff = ff.lower() in ("true", "1", "yes") if ff else None
            child_age = filter_dict.get("child_age", "")
            child_age_min = child_age_max = None
            if isinstance(child_age, str) and "-" in child_age:
                try:
                    a, b = child_age.split("-", 1)
                    child_age_min = int(a.strip())
                    child_age_max = int(b.strip())
                except (ValueError, TypeError):
                    pass
            rkg_resources = rkg_get_country_resources(
                country_code=country_code,
                city=city or None,
                category=filter_dict.get("category"),
                audience=filter_dict.get("family_type"),
                budget=filter_dict.get("budget"),
                family_friendly=ff,
                child_age_min=child_age_min,
                child_age_max=child_age_max,
                published_only=True,
            )
        if rkg_resources:
            sections = resources_to_sections(country_code, city, rkg_resources, resource_ctx)
        else:
            # Fallback to legacy section content
            sections = []
            for key in RESOURCE_SECTIONS:
                content = _get_section_content(country_code, city, key)
                sections.append({
                    "key": key,
                    "title": SECTION_LABELS.get(key, key.replace("_", " ").title()),
                    "content": content,
                })
    except Exception as e:
        log.warning("RKG resources fetch failed, using fallback: %s", e, exc_info=True)
        sections = []
        for key in RESOURCE_SECTIONS:
            content = _get_section_content(country_code, city, key)
            sections.append({
                "key": key,
                "title": SECTION_LABELS.get(key, key.replace("_", " ").title()),
                "content": content,
            })

    # Events from RKG
    events = []
    try:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        ev_ff = filter_dict.get("family_friendly")
        if isinstance(ev_ff, str):
            ev_ff = ev_ff.lower() in ("true", "1", "yes") if ev_ff else None
        events = rkg_get_country_events(
            country_code=country_code,
            city=city or None,
            event_type=filter_dict.get("event_type"),
            date_from=now,
            date_to=now + timedelta(days=14),
            family_friendly=ev_ff,
            limit=20,
            published_only=True,
        )
    except Exception as e:
        log.debug("RKG events fetch failed: %s", e)

    # Recommended resources for hero
    recommended = []
    try:
        recommended = get_recommended_resources(resource_ctx, limit=5)
    except Exception as e:
        log.debug("RKG recommended fetch failed: %s", e)

    return {
        "profile": profile,
        "context": resource_ctx,
        "hints": hints,
        "sections": sections,
        "events": events,
        "recommended": recommended,
        "filters_applied": filter_dict,
    }


def _require_case_id_assignment_visible(case_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve case_id to an assignment and enforce visibility (RFQ paths, evidence, etc.). Returns assignment row."""
    assignment = db.get_assignment_by_case_id(case_id) or db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Case not found")
    return _require_assignment_visibility(assignment["id"], user)


def _require_assignment_visibility(
    assignment_id: str,
    user: Dict[str, Any],
):
    """Validate user can access assignment. HR: admin, owner, or assignment in their company."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    eid = effective.get("id")
    visible = False
    if is_employee and eid is not None and emp_id == eid:
        visible = True
    elif is_hr:
        visible = effective.get("is_admin") or (eid is not None and hr_id == eid)
        if not visible and effective.get("role") == UserRole.HR.value:
            hr_company = _get_hr_company_id(effective)
            if hr_company and db.assignment_belongs_to_company(assignment_id, hr_company):
                visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    return assignment


def _get_hr_company_id(user: Dict[str, Any]) -> Optional[str]:
    """Resolve company_id for HR user. Uses hr_users first, then profile."""
    uid = user.get("id")
    if not uid:
        return None
    cid = db.get_hr_company_id(uid)
    if cid:
        return cid
    profile = db.get_profile_record(uid)
    return profile.get("company_id") if profile else None


def _hr_can_access_assignment(assignment: Dict[str, Any], user: Dict[str, Any]) -> bool:
    """True if HR user can access this assignment (admin, owner, or company match)."""
    effective = _effective_user(user, UserRole.HR)
    if effective.get("is_admin"):
        return True
    eid = effective.get("id")
    if eid is not None and assignment.get("hr_user_id") == eid:
        return True
    hr_company = _get_hr_company_id(effective)
    return bool(hr_company and db.assignment_belongs_to_company(assignment.get("id", ""), hr_company))


def _require_company_for_user(user: Dict[str, Any]) -> Dict[str, Any]:
    profile = db.get_profile_record(user.get("id")) or {}
    company_id = _get_hr_company_id(user) if user.get("role") == UserRole.HR.value else profile.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User missing company association")
    profile["company_id"] = company_id
    return profile


def _resolve_company_for_policy(
    user: Dict[str, Any], company_id_override: Optional[str] = None
) -> str:
    """Resolve company_id for policy access. Admin may override with company_id_override."""
    if user.get("is_admin") and company_id_override:
        return company_id_override
    profile = _require_company_for_user(user)
    return profile.get("company_id") or ""


def _require_policy_access(user: Dict[str, Any], policy: Optional[Dict[str, Any]]) -> None:
    """Raise 404 if policy missing or user lacks access. Admin can access any policy."""
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if user.get("is_admin"):
        return
    profile = _require_company_for_user(user)
    if policy.get("company_id") != profile.get("company_id"):
        raise HTTPException(status_code=404, detail="Policy not found")


def _require_document_access(user: Dict[str, Any], doc: Optional[Dict[str, Any]]) -> None:
    """Raise 404 if doc missing or user lacks access. Admin can access any document."""
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if user.get("is_admin"):
        return
    profile = _require_company_for_user(user)
    if doc.get("company_id") != profile.get("company_id"):
        raise HTTPException(status_code=404, detail="Document not found")


def _map_storage_exception_to_response(exc: Exception, bucket: str) -> tuple[str, str]:
    """Return (error_code, user_safe_message). No secrets."""
    from .services.policy_storage_health import (
        STORAGE_MISSING_SERVICE_ROLE,
        STORAGE_BUCKET_NOT_FOUND,
        STORAGE_ACCESS_DENIED,
        get_storage_error_code,
    )
    code = get_storage_error_code(exc)
    if code == STORAGE_MISSING_SERVICE_ROLE:
        return (code, "Policy document uploads require Supabase storage. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend .env (see .env.example) to enable uploads.")
    if code == STORAGE_BUCKET_NOT_FOUND:
        return (code, "Policy storage bucket is unavailable.")
    if code == STORAGE_ACCESS_DENIED:
        return (code, "Policy storage access denied.")
    return (code, "Upload failed. Please try again.")


def _sanitize_storage_error(exc: Exception, bucket: str) -> str:
    """Return safe user-facing message for HTTPException detail. Used by non-upload routes."""
    _, msg = _map_storage_exception_to_response(exc, bucket)
    return msg


@app.get("/api/employee/assignments/{assignment_id}/services")
def get_assignment_services(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    assignment = _require_assignment_visibility(assignment_id, user)
    try:
        services = db.list_case_services(assignment["id"])
    except Exception as e:
        log.warning("list_case_services failed for assignment %s: %s", assignment["id"], e, exc_info=True)
        services = []
    return {
        "assignment_id": assignment["id"],
        "case_id": assignment.get("case_id"),
        "services": services,
    }


@app.get("/api/services/context")
def get_services_context(
    assignment_id: str = Query(..., description="Assignment id (gate for access)"),
    fallback_services: Optional[str] = Query(None, description="Comma-separated service keys when DB has none"),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """
    Combined endpoint: assignment, case context, services, answers, and questions in one round-trip.
    Reduces 4 requests to 1 for the services questions page.
    """
    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")

    services = db.list_case_services(assignment["id"])
    selected_keys = [r["service_key"] for r in services if r.get("selected") in (True, 1)]
    if not selected_keys and fallback_services:
        fallback = [k.strip().lower() for k in fallback_services.split(",") if k.strip()]
        valid = {"housing", "schools", "movers", "banks", "insurances", "electricity"}
        selected_keys = [k for k in fallback if k in valid]

    draft = {}
    dest_city = dest_country = origin_city = origin_country = None
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if case:
            try:
                draft = json.loads(case.draft_json or "{}")
            except Exception:
                draft = {}
            dest_city = getattr(case, "dest_city", None)
            dest_country = getattr(case, "dest_country", None)
            origin_city = getattr(case, "origin_city", None)
            origin_country = getattr(case, "origin_country", None)
    basics = draft.get("relocationBasics") or {}
    case_context = {
        "destCity": basics.get("destCity") or dest_city,
        "destCountry": basics.get("destCountry") or dest_country,
        "originCity": basics.get("originCity") or origin_city,
        "originCountry": origin_country or basics.get("originCountry"),
    }

    saved_rows = db.list_case_service_answers(case_id)
    saved_flat: Dict[str, Any] = {}
    for row in saved_rows:
        ans = row.get("answers") or {}
        if isinstance(ans, str):
            try:
                ans = json.loads(ans)
            except Exception:
                ans = {}
        for k, v in ans.items():
            if v is not None:
                saved_flat[k] = v

    questions = []
    if selected_keys:
        questions = generate_questions(
            selected_services=selected_keys,
            case_context=case_context,
            saved_answers=saved_flat,
        )

    return {
        "assignment_id": assignment["id"],
        "case_id": case_id,
        "case_context": case_context,
        "services": services,
        "answers": saved_rows,
        "questions": questions,
        "selected_services": selected_keys,
    }


@app.post("/api/employee/assignments/{assignment_id}/services")
def upsert_assignment_services(
    assignment_id: str,
    payload: CaseServicesUpsert,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=400, detail="Assignment missing case_id")
    items = [
        {
            "service_key": item.service_key,
            "category": item.category,
            "selected": item.selected,
            "estimated_cost": item.estimated_cost,
            "currency": item.currency,
        }
        for item in payload.services
    ]
    try:
        db.upsert_case_services(assignment["id"], case_id, items)
        updated = db.list_case_services(assignment["id"])
        try:
            from .services.analytics_service import emit_event, EVENT_SERVICES_SELECTED
            selected = [s["service_key"] for s in items if s.get("selected")]
            emit_event(
                EVENT_SERVICES_SELECTED,
                request_id=getattr(req.state, "request_id", None),
                assignment_id=assignment_id,
                case_id=case_id,
                user_id=user.get("id"),
                user_role=user.get("role"),
                service_categories=selected,
                counts={"selected": len(selected), "total": len(items)},
            )
        except Exception:
            pass
        return {"ok": True, "services": updated}
    except Exception as e:
        log.warning("upsert_case_services failed for assignment %s: %s", assignment["id"], e, exc_info=True)
        return {"ok": False, "services": []}


@app.get("/api/services/answers")
def get_service_answers(
    case_id: Optional[str] = Query(None),
    assignment_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Load saved service answers. Pass case_id or assignment_id."""
    if assignment_id:
        assignment = _require_assignment_visibility(assignment_id, user)
        effective_case_id = assignment.get("case_id")
    elif case_id:
        assignment = _require_assignment_visibility(case_id, user)
        effective_case_id = assignment.get("case_id") or case_id
    else:
        raise HTTPException(status_code=400, detail="case_id or assignment_id required")
    if not effective_case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")
    answers = db.list_case_service_answers(effective_case_id)
    return {"case_id": effective_case_id, "answers": answers}


@app.get("/api/services/questions")
def get_service_questions(
    assignment_id: str = Query(..., description="Assignment id (gate for access)"),
    fallback_services: Optional[str] = Query(None, description="Comma-separated service keys when DB has none (e.g. housing,schools)"),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Return dynamic questions for selected services. Adapts to case context and saved answers."""
    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")

    # Selected services (only those with selected=True)
    services = db.list_case_services(assignment["id"])
    selected_keys = [r["service_key"] for r in services if r.get("selected") in (True, 1)]
    # Fallback: when DB has none but frontend passed selection (handles save race / direct visit)
    if not selected_keys and fallback_services:
        fallback = [k.strip().lower() for k in fallback_services.split(",") if k.strip()]
        valid = {"housing", "schools", "movers", "banks", "insurances", "electricity"}
        selected_keys = [k for k in fallback if k in valid]
    if not selected_keys:
        return {"questions": [], "selected_services": []}

    # Case context (draft + top-level) via app_crud
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
    draft = {}
    dest_city = None
    dest_country = None
    origin_city = None
    origin_country = None
    if case:
        try:
            draft = json.loads(case.draft_json or "{}")
        except Exception:
            draft = {}
        dest_city = getattr(case, "dest_city", None)
        dest_country = getattr(case, "dest_country", None)
        origin_city = getattr(case, "origin_city", None)
        origin_country = getattr(case, "origin_country", None)
    basics = draft.get("relocationBasics") or {}
    case_context = {
        "destCity": basics.get("destCity") or dest_city,
        "destCountry": basics.get("destCountry") or dest_country,
        "originCity": basics.get("originCity") or origin_city,
        "originCountry": origin_country or basics.get("originCountry"),
    }

    # Saved answers (flatten service_key -> answers into one dict)
    saved_rows = db.list_case_service_answers(case_id)
    saved_flat: Dict[str, Any] = {}
    for row in saved_rows:
        ans = row.get("answers") or {}
        if isinstance(ans, str):
            try:
                ans = json.loads(ans)
            except Exception:
                ans = {}
        for k, v in ans.items():
            if v is not None:
                saved_flat[k] = v

    questions = generate_questions(
        selected_services=selected_keys,
        case_context=case_context,
        saved_answers=saved_flat,
    )
    return {"questions": questions, "selected_services": selected_keys}


def _normalize_answers_for_compare(answers: Dict[str, Any]) -> str:
    """Stable JSON for duplicate detection."""
    if not answers:
        return "{}"
    return json.dumps(answers, sort_keys=True)


@app.post("/api/services/answers")
def upsert_service_answers(
    payload: ServiceAnswersUpsert,
    request: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    start = time.perf_counter()
    assignment = _require_assignment_visibility(payload.case_id, user)
    effective_case_id = assignment.get("case_id") or payload.case_id
    assignment_id = assignment.get("id")

    try:
        existing = db.list_case_service_answers(effective_case_id, request_id=request_id)
        existing_by_key = {r["service_key"]: _normalize_answers_for_compare(r.get("answers") or {}) for r in existing}
        incoming_by_key = {item.service_key: _normalize_answers_for_compare(item.answers) for item in payload.items}
        if set(existing_by_key.keys()) == set(incoming_by_key.keys()) and all(
            existing_by_key.get(k) == incoming_by_key.get(k) for k in incoming_by_key
        ):
            dur_ms = (time.perf_counter() - start) * 1000
            log.info(
                "request_id=%s case_id=%s assignment_id=%s services_answers skipped_duplicate dur_ms=%.2f",
                request_id, effective_case_id, assignment_id, dur_ms,
            )
            return {"ok": True, "skipped_duplicate": True}

        for item in payload.items:
            db.upsert_case_service_answers(
                case_id=effective_case_id,
                service_key=item.service_key,
                answers=item.answers,
                request_id=request_id,
            )
        dur_ms = (time.perf_counter() - start) * 1000
        log.info(
            "request_id=%s case_id=%s assignment_id=%s services_answers saved dur_ms=%.2f",
            request_id, effective_case_id, assignment_id, dur_ms,
        )
        try:
            from .services.analytics_service import emit_event, EVENT_SERVICES_ANSWERS_SAVED
            emit_event(
                EVENT_SERVICES_ANSWERS_SAVED,
                request_id=request_id,
                assignment_id=assignment_id,
                case_id=effective_case_id,
                user_id=user.get("id"),
                user_role=user.get("role"),
                duration_ms=dur_ms,
                service_categories=[i.service_key for i in payload.items],
                counts={"answers_saved": len(payload.items)},
            )
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        dur_ms = (time.perf_counter() - start) * 1000
        log.warning(
            "request_id=%s case_id=%s assignment_id=%s services_answers failed dur_ms=%.2f error=%s",
            request_id, effective_case_id, assignment_id, dur_ms, repr(e), exc_info=True,
        )
        raise


@app.post("/api/rfqs")
def create_rfq(
    payload: RfqCreatePayload,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    assignment = _require_assignment_visibility(payload.case_id, user)
    effective_case_id = assignment.get("case_id") or payload.case_id

    vendor_ids: List[str] = list(payload.vendor_ids or [])
    if payload.supplier_ids:
        from .app.services.rfq_recipient_mapping import resolve_recipient_ids
        resolved, errors = resolve_recipient_ids(payload.supplier_ids)
        if errors:
            raise HTTPException(
                status_code=400,
                detail="; ".join(errors),
            )
        vendor_ids = list(resolved)
    if not vendor_ids:
        raise HTTPException(status_code=400, detail="At least one vendor_id or supplier_id required")

    req_id = getattr(req.state, "request_id", None)
    valid_vids, vid_errors = db.validate_vendor_ids(vendor_ids, request_id=req_id)
    if vid_errors:
        log.warning(
            "create_rfq vendor validation failed request_id=%s vendor_ids=%s errors=%s",
            req_id, vendor_ids, vid_errors,
        )
        raise HTTPException(
            status_code=400,
            detail="; ".join(vid_errors),
        )
    if not valid_vids:
        raise HTTPException(status_code=400, detail="No valid vendor_ids; each must exist in vendors table")

    try:
        result = db.create_rfq(
            case_id=effective_case_id,
            creator_user_id=user.get("id"),
            items=[i.model_dump(mode="json") for i in payload.items],
            vendor_ids=valid_vids,
            request_id=req_id,
        )
    except Exception as e:
        log.error(
            "create_rfq failed request_id=%s case_id=%s vendor_ids=%s error=%s",
            req_id, effective_case_id, valid_vids, e,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="RFQ creation failed. Check logs for details.")

    try:
        from .services.analytics_service import (
            emit_event,
            EVENT_RFQ_CREATED,
            EVENT_SUPPLIER_SELECTED,
        )
        emit_event(
            EVENT_RFQ_CREATED,
            request_id=req_id,
            assignment_id=assignment.get("id"),
            case_id=effective_case_id,
            user_id=user.get("id"),
            user_role=user.get("role"),
            counts={"items": len(payload.items), "vendors": len(vendor_ids)},
            extra={"rfq_id": result.get("id"), "rfq_ref": result.get("rfq_ref"), "vendor_ids": vendor_ids},
        )
        for vid in vendor_ids:
            emit_event(
                EVENT_SUPPLIER_SELECTED,
                request_id=req_id,
                assignment_id=assignment.get("id"),
                case_id=effective_case_id,
                user_id=user.get("id"),
                user_role=user.get("role"),
                extra={"vendor_id": vid, "rfq_id": result.get("id")},
            )
    except Exception:
        pass
    return {"ok": True, "rfq": result}


@app.get("/api/employee/assignments/{assignment_id}/rfqs")
def list_rfqs_for_assignment(
    assignment_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """List RFQs for an assignment (require_assignment_visibility)."""
    _ = _require_assignment_visibility(assignment_id, user)
    request_id = getattr(req.state, "request_id", None)
    rfqs = db.list_rfqs_for_assignment(assignment_id, request_id=request_id)
    return {"rfqs": rfqs}


@app.get("/api/rfqs/{rfq_id}")
def get_rfq(
    rfq_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Get RFQ detail (require case access via rfq.case_id)."""
    rfq = db.get_rfq(rfq_id, request_id=getattr(req.state, "request_id", None))
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    _ = _require_case_id_assignment_visible(rfq["case_id"], user)
    return rfq


@app.get("/api/rfqs/{rfq_id}/quotes")
def list_quotes_for_rfq(
    rfq_id: str,
    req: Request,
    comparison: bool = Query(False, description="Opening quote comparison view"),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """List quotes for RFQ (require case access). Emits quote_compared when comparison=1 and 2+ quotes."""
    rfq = db.get_rfq(rfq_id, request_id=getattr(req.state, "request_id", None))
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    _ = _require_case_access(rfq["case_id"], user)
    quotes = db.list_quotes_for_rfq(rfq_id, request_id=getattr(req.state, "request_id", None))
    if comparison and len(quotes) >= 2:
        try:
            from .services.analytics_service import emit_event, EVENT_QUOTE_COMPARED
            emit_event(
                EVENT_QUOTE_COMPARED,
                request_id=getattr(req.state, "request_id", None),
                case_id=rfq.get("case_id"),
                user_id=user.get("id"),
                user_role=user.get("role"),
                counts={"quotes": len(quotes)},
                extra={"rfq_id": rfq_id},
            )
        except Exception:
            pass
    return {"rfq_id": rfq_id, "quotes": quotes}


@app.patch("/api/rfqs/{rfq_id}/quotes/{quote_id}/accept")
def accept_quote(
    rfq_id: str,
    quote_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Accept a quote (require case access)."""
    rfq = db.get_rfq(rfq_id, request_id=getattr(req.state, "request_id", None))
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    _ = _require_case_id_assignment_visible(rfq["case_id"], user)
    updated = db.update_quote_status(quote_id, "accepted", request_id=getattr(req.state, "request_id", None))
    if not updated:
        raise HTTPException(status_code=404, detail="Quote not found")
    try:
        from .services.analytics_service import emit_event, EVENT_QUOTE_ACCEPTED
        emit_event(
            EVENT_QUOTE_ACCEPTED,
            request_id=getattr(req.state, "request_id", None),
            case_id=rfq.get("case_id"),
            canonical_case_id=rfq.get("canonical_case_id"),
            user_id=user.get("id"),
            user_role=user.get("role"),
            extra={
                "rfq_id": rfq_id,
                "quote_id": quote_id,
                "vendor_id": updated.get("vendor_id"),
            },
        )
    except Exception:
        pass
    return {"ok": True, "quote": updated}


# ---------------------------------------------------------------------------
# Vendor API (RFQs and quotes)
# ---------------------------------------------------------------------------
@app.get("/api/vendor/rfqs")
def list_vendor_rfqs(
    req: Request,
    user: Dict[str, Any] = Depends(require_vendor),
):
    """List RFQs for current vendor (require_vendor)."""
    vendor_id = user.get("vendor_id")
    if not vendor_id:
        raise HTTPException(status_code=403, detail="Vendor access only")
    request_id = getattr(req.state, "request_id", None)
    rfqs = db.list_rfqs_for_vendor(vendor_id, request_id=request_id)
    return {"rfqs": rfqs}


@app.get("/api/vendor/rfqs/{rfq_id}")
def get_vendor_rfq(
    rfq_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_vendor),
):
    """Get RFQ detail for vendor. Ensures vendor is a recipient."""
    vendor_id = user.get("vendor_id")
    if not vendor_id:
        raise HTTPException(status_code=403, detail="Vendor access only")
    rfq = db.get_rfq(rfq_id, request_id=getattr(req.state, "request_id", None))
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    recipient_vendor_ids = [r.get("vendor_id") for r in rfq.get("recipients", []) if r.get("vendor_id")]
    if vendor_id not in recipient_vendor_ids:
        raise HTTPException(status_code=403, detail="Not a recipient of this RFQ")
    return rfq


@app.post("/api/vendor/rfqs/{rfq_id}/quotes")
def submit_vendor_quote(
    rfq_id: str,
    payload: QuoteCreatePayload,
    req: Request,
    user: Dict[str, Any] = Depends(require_vendor),
):
    """Submit a quote for an RFQ (require_vendor)."""
    vendor_id = user.get("vendor_id")
    if not vendor_id:
        raise HTTPException(status_code=403, detail="Vendor access only")
    rfq = db.get_rfq(rfq_id, request_id=getattr(req.state, "request_id", None))
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    recipient_vendor_ids = [r.get("vendor_id") for r in rfq.get("recipients", []) if r.get("vendor_id")]
    if vendor_id not in recipient_vendor_ids:
        raise HTTPException(status_code=403, detail="Not a recipient of this RFQ")
    request_id = getattr(req.state, "request_id", None)
    quote_lines = [{"label": ln.label, "amount": ln.amount} for ln in payload.quote_lines]
    quote = db.create_quote(
        rfq_id=rfq_id,
        vendor_id=vendor_id,
        currency=payload.currency,
        total_amount=payload.total_amount,
        valid_until=payload.valid_until,
        quote_lines=quote_lines,
        created_by_user_id=user.get("id"),
        request_id=request_id,
    )
    try:
        from .services.analytics_service import emit_event, EVENT_QUOTE_RECEIVED
        emit_event(
            EVENT_QUOTE_RECEIVED,
            request_id=request_id,
            case_id=rfq.get("case_id"),
            canonical_case_id=rfq.get("canonical_case_id"),
            extra={
                "rfq_id": rfq_id,
                "vendor_id": vendor_id,
                "quote_id": quote.get("id"),
                "total_amount": payload.total_amount,
                "currency": payload.currency,
            },
        )
    except Exception:
        pass
    return {"ok": True, "quote": quote}


EMPLOYEE_POLICY_FALLBACK_PRIMARY = (
    "Your company has not yet published an assignment policy for this case."
)
EMPLOYEE_POLICY_FALLBACK_SECONDARY = (
    "Once HR publishes a policy that applies to your assignment, your benefits and limits will appear here."
)


def _resolve_published_policy_for_employee(
    assignment_id: str,
    user: Dict[str, Any],
    request_id: Optional[str] = None,
    *,
    read_only: bool = False,
) -> Dict[str, Any]:
    """
    Resolve published company policy for an employee's assignment context.
    Canonical resolution order: relocation_cases.company_id → HR owner's company → employee profile company_id.
    Returns structured result; never raises for "no policy" (only for auth via _require_assignment_visibility).

    read_only: do not create cases or back-fill company_id on profile/case (GET employee policy paths).
    """
    from .services.policy_resolution import (
        resolve_policy_for_assignment,
        collect_company_id_candidates_for_assignment,
        find_first_published_company_policy,
    )

    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    case = db.get_relocation_case(case_id) if case_id else None
    hr_user_id = assignment.get("hr_user_id") or ((case or {}).get("hr_user_id") if case else None)
    hr_company_id = db.get_hr_company_id(hr_user_id) if hr_user_id else None
    profile_company_id = None
    if assignment.get("employee_user_id"):
        emp_profile = db.get_profile_record(assignment["employee_user_id"])
        if emp_profile:
            profile_company_id = emp_profile.get("company_id")

    if not read_only:
        if not case and case_id and hr_user_id and hr_company_id:
            try:
                db.create_case(case_id, hr_user_id, {}, company_id=hr_company_id)
                case = db.get_relocation_case(case_id)
            except Exception:
                pass
        case_company_id = (case or {}).get("company_id") if case else None
        company_id_for_resolution = case_company_id or hr_company_id or profile_company_id
        if company_id_for_resolution:
            if case and not case.get("company_id"):
                try:
                    db.upsert_relocation_case(
                        case_id=case_id,
                        company_id=company_id_for_resolution,
                        employee_id=case.get("employee_id"),
                        status=case.get("status"),
                        stage=case.get("stage"),
                        host_country=case.get("host_country"),
                        home_country=case.get("home_country"),
                    )
                    case = db.get_relocation_case(case_id) or case
                except Exception:
                    pass
            emp_user_id = assignment.get("employee_user_id")
            if emp_user_id:
                emp_profile2 = db.get_profile_record(emp_user_id)
                if emp_profile2 and not emp_profile2.get("company_id"):
                    try:
                        db.ensure_profile_record(
                            emp_user_id,
                            emp_profile2.get("email") or "",
                            emp_profile2.get("role") or "EMPLOYEE",
                            emp_profile2.get("full_name"),
                            company_id_for_resolution,
                        )
                    except Exception:
                        pass

    case_company_id = (case or {}).get("company_id") if case else None
    company_id_used = case_company_id or hr_company_id or profile_company_id

    profile = None
    if case and case.get("profile_json"):
        try:
            profile = json.loads(case["profile_json"]) if isinstance(case["profile_json"], str) else case["profile_json"]
        except Exception:
            profile = None
    try:
        employee_profile = db.get_employee_profile(assignment_id)
    except Exception:
        employee_profile = None

    candidates = collect_company_id_candidates_for_assignment(db, assignment, case)
    pub = find_first_published_company_policy(db, candidates) if candidates else None
    if not pub:
        try:
            with_policy = db.list_company_ids_with_published_policy()
            log.info(
                "employee_policy no_policy_fast request_id=%s assignment_id=%s case_id=%s candidates=%s published_sample=%s",
                request_id,
                assignment_id,
                case_id,
                candidates,
                [c.get("company_id") for c in with_policy] if with_policy else [],
            )
        except Exception:
            log.info(
                "employee_policy no_policy_fast request_id=%s assignment_id=%s case_id=%s candidates=%s",
                request_id,
                assignment_id,
                case_id,
                candidates,
            )
        return {
            "has_policy": False,
            "reason": EMPLOYEE_POLICY_FALLBACK_PRIMARY,
            "reason_secondary": EMPLOYEE_POLICY_FALLBACK_SECONDARY,
            "assignment_id": assignment_id,
            "case_id": case_id,
            "company_id_used": company_id_used,
        }

    company_id_pub, policy_row, version_row = pub
    vid_pub = (version_row or {}).get("id")

    cached_row = None
    try:
        cached_row = db.get_resolved_assignment_policy(assignment_id)
    except Exception:
        cached_row = None

    if (
        cached_row
        and cached_row.get("id")
        and vid_pub
        and str(cached_row.get("policy_version_id") or "") == str(vid_pub)
    ):
        rid = cached_row["id"]
        try:
            benefits = db.list_resolved_policy_benefits(rid)
            exclusions = db.list_resolved_policy_exclusions(rid)
        except Exception as exc:
            log.warning("employee_policy cache list_benefits request_id=%s resolved_id=%s exc=%s", request_id, rid, exc)
            benefits = []
            exclusions = []
        policy = cached_row.get("policy") or policy_row or {}
        version = cached_row.get("version") or version_row or {}
        ctx = cached_row.get("resolution_context") or cached_row.get("resolution_context_json") or {}
        company_id_used = cached_row.get("resolution_company_id") or cached_row.get("company_id") or company_id_pub
        company = db.get_company(company_id_used) if company_id_used else None
        company_name = (company or {}).get("name") if company else None
        log.info(
            "employee_policy cache_hit request_id=%s assignment_id=%s policy_version_id=%s",
            request_id,
            assignment_id,
            vid_pub,
        )
        return {
            "has_policy": True,
            "company_id": company_id_used,
            "policy_id": (policy or {}).get("id"),
            "version_id": (version or {}).get("id"),
            "assignment_id": assignment_id,
            "case_id": case_id,
            "policy": {
                "id": (policy or {}).get("id"),
                "title": (policy or {}).get("title"),
                "version": (version or {}).get("version_number"),
                "effective_date": (policy or {}).get("effective_date"),
                "company_name": company_name,
            },
            "benefits": benefits,
            "exclusions": exclusions,
            "resolved_at": cached_row.get("resolved_at"),
            "resolution_context": ctx,
        }

    resolved = None
    try:
        resolved = resolve_policy_for_assignment(
            db, assignment_id, assignment, case, profile, employee_profile
        )
    except Exception as exc:
        log.warning(
            "employee_policy resolve_policy_for_assignment request_id=%s assignment_id=%s company_id_used=%s exc=%s",
            request_id,
            assignment_id,
            company_id_used,
            exc,
        )
        resolved = None
    if not resolved:
        return {
            "has_policy": False,
            "reason": EMPLOYEE_POLICY_FALLBACK_PRIMARY,
            "reason_secondary": EMPLOYEE_POLICY_FALLBACK_SECONDARY,
            "assignment_id": assignment_id,
            "case_id": case_id,
            "company_id_used": company_id_used,
        }
    company_id_used = resolved.get("resolution_company_id") or company_id_used or company_id_pub
    if not read_only and case_id and case and not case.get("company_id") and company_id_used:
        try:
            db.upsert_relocation_case(
                case_id=case_id,
                company_id=company_id_used,
                employee_id=case.get("employee_id"),
                status=case.get("status"),
                stage=case.get("stage"),
                host_country=case.get("host_country"),
                home_country=case.get("home_country"),
            )
        except Exception:
            pass
    rid = resolved.get("id")
    if not rid:
        return {
            "has_policy": False,
            "reason": EMPLOYEE_POLICY_FALLBACK_PRIMARY,
            "reason_secondary": EMPLOYEE_POLICY_FALLBACK_SECONDARY,
            "assignment_id": assignment_id,
            "case_id": case_id,
            "company_id_used": company_id_used,
        }
    try:
        benefits = db.list_resolved_policy_benefits(rid)
        exclusions = db.list_resolved_policy_exclusions(rid)
    except Exception as exc:
        log.warning("employee_policy list_benefits/exclusions request_id=%s resolved_id=%s exc=%s", request_id, rid, exc)
        benefits = []
        exclusions = []
    policy = resolved.get("policy") or {}
    version = resolved.get("version") or {}
    ctx = resolved.get("resolution_context") or resolved.get("resolution_context_json") or {}
    company = db.get_company(company_id_used) if company_id_used else None
    company_name = (company or {}).get("name") if company else None
    log.info(
        "employee_policy resolved request_id=%s assignment_id=%s case_id=%s company_id=%s policy_id=%s version_id=%s has_policy=true",
        request_id,
        assignment_id,
        case_id,
        company_id_used,
        policy.get("id"),
        version.get("id"),
    )
    return {
        "has_policy": True,
        "company_id": company_id_used,
        "policy_id": policy.get("id"),
        "version_id": version.get("id"),
        "assignment_id": assignment_id,
        "case_id": case_id,
        "policy": {
            "id": policy.get("id"),
            "title": policy.get("title"),
            "version": version.get("version_number"),
            "effective_date": policy.get("effective_date"),
            "company_name": company_name,
        },
        "benefits": benefits,
        "exclusions": exclusions,
        "resolved_at": resolved.get("resolved_at"),
        "resolution_context": ctx,
    }


def _log_employee_policy(
    route: str,
    request_id: Optional[str],
    user_id: Optional[str],
    role: Optional[str],
    assignment_id: str,
    case_id: Optional[str],
    company_id_used: Optional[str],
    has_policy: bool,
    policy_id: Optional[str] = None,
    version_id: Optional[str] = None,
    exc_type: Optional[str] = None,
    exc_message: Optional[str] = None,
):
    """Structured log for employee policy retrieval (no stack traces)."""
    log.info(
        "employee_policy request_id=%s route=%s user_id=%s role=%s assignment_id=%s case_id=%s "
        "company_id_used=%s has_policy=%s policy_id=%s version_id=%s exc_type=%s exc_message=%s",
        request_id or "",
        route,
        user_id or "",
        role or "",
        assignment_id,
        case_id or "",
        company_id_used or "",
        has_policy,
        policy_id or "",
        version_id or "",
        exc_type or "",
        (exc_message or "")[:200] if exc_message else "",
    )


@app.get("/api/employee/assignments/{assignment_id}/policy")
def get_employee_assignment_policy(
    assignment_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Employee: Get resolved policy for this assignment (read-only, published only). Never 500 for missing policy."""
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    try:
        result = _resolve_published_policy_for_employee(assignment_id, user, request_id, read_only=True)
    except HTTPException:
        raise
    except Exception as exc:
        try:
            _log_employee_policy(
                "GET /api/employee/assignments/{id}/policy",
                request_id,
                user.get("id"),
                user.get("role"),
                assignment_id,
                None,
                None,
                False,
                exc_type=type(exc).__name__,
                exc_message=str(exc),
            )
        except Exception:
            pass
        return {
            "ok": True,
            "has_policy": False,
            "policy": None,
            "benefits": [],
            "exclusions": [],
            "resolution_context": None,
            "message": "No published policy for your assignment.",
        }
    if not result.get("has_policy"):
        try:
            _log_employee_policy(
                "GET /api/employee/assignments/{id}/policy",
                request_id,
                user.get("id"),
                user.get("role"),
                assignment_id,
                result.get("case_id"),
                result.get("company_id_used"),
                False,
            )
        except Exception:
            pass
        return {
            "ok": True,
            "has_policy": False,
            "policy": None,
            "benefits": [],
            "exclusions": [],
            "resolution_context": None,
            "message": result.get("reason", EMPLOYEE_POLICY_FALLBACK_PRIMARY),
            "message_secondary": result.get("reason_secondary") or EMPLOYEE_POLICY_FALLBACK_SECONDARY,
            "company_id_used": result.get("company_id_used"),
        }
    try:
        _log_employee_policy(
            "GET /api/employee/assignments/{id}/policy",
            request_id,
            user.get("id"),
            user.get("role"),
            assignment_id,
            result.get("case_id"),
            result.get("company_id"),
            True,
            result.get("policy_id"),
            result.get("version_id"),
        )
    except Exception:
        pass
    return {
        "ok": True,
        "has_policy": True,
        "policy": result.get("policy") or {},
        "benefits": result.get("benefits") or [],
        "exclusions": result.get("exclusions") or [],
        "resolved_at": result.get("resolved_at"),
        "resolution_context": result.get("resolution_context"),
    }


@app.get("/api/employee/assignments/{assignment_id}/policy-envelope")
def get_employee_policy_envelope(
    assignment_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Employee: Get policy envelope (envelope cards ready) for comparison/budget logic."""
    data = get_employee_assignment_policy(assignment_id, req, user)
    if not data.get("benefits"):
        return data
    # Map to envelope shape: included, capped, excluded, approval-required
    from .services.policy_taxonomy import get_benefit_meta
    envelopes = []
    for b in data["benefits"]:
        meta = get_benefit_meta(b.get("benefit_key", ""))
        label = (meta.get("keywords") or [b.get("benefit_key", "")])[0].replace("_", " ").title()
        envelopes.append({
            "key": b.get("benefit_key"),
            "label": label,
            "included": bool(b.get("included")),
            "capped": b.get("max_value") is not None or b.get("standard_value") is not None,
            "min_value": b.get("min_value"),
            "standard_value": b.get("standard_value"),
            "max_value": b.get("max_value"),
            "currency": b.get("currency") or "USD",
            "approval_required": bool(b.get("approval_required")),
            "evidence_required": b.get("evidence_required_json") or [],
        })
    return {
        **data,
        "envelopes": envelopes,
    }


@app.get("/api/employee/assignments/{assignment_id}/policy-service-comparison")
def get_employee_policy_service_comparison(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Employee: Get comparison of selected services vs resolved policy (read-only, explanatory)."""
    _ = _require_assignment_visibility(assignment_id, user)
    from .services.policy_service_comparison import compute_policy_service_comparison
    return compute_policy_service_comparison(db, assignment_id, include_diagnostics=False)


@app.get("/api/hr/assignments/{assignment_id}/policy-service-comparison")
def get_hr_policy_service_comparison(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR: Get comparison of selected services vs resolved policy with diagnostics."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _hr_can_access_assignment(assignment, user):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    from .services.policy_service_comparison import compute_policy_service_comparison
    return compute_policy_service_comparison(db, assignment_id, assignment=assignment, include_diagnostics=True)


@app.get("/api/employee/assignments/{assignment_id}/policy-budget")
def get_assignment_policy_budget(
    assignment_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Employee: Get policy caps for this assignment. Same resolution as policy route. Never 500 for missing policy."""
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    from .services.policy_adapter import caps_from_resolved_benefits, DEFAULT_CURRENCY

    try:
        result = _resolve_published_policy_for_employee(assignment_id, user, request_id, read_only=True)
    except HTTPException:
        raise
    except Exception as exc:
        try:
            _log_employee_policy(
                "GET /api/employee/assignments/{id}/policy-budget",
                request_id,
                user.get("id"),
                user.get("role"),
                assignment_id,
                None,
                None,
                False,
                exc_type=type(exc).__name__,
                exc_message=str(exc),
            )
        except Exception:
            pass
        return {"ok": True, "has_policy": False, "budget": None, "currency": DEFAULT_CURRENCY, "caps": {}, "total_cap": None}

    if not result.get("has_policy"):
        try:
            _log_employee_policy(
                "GET /api/employee/assignments/{id}/policy-budget",
                request_id,
                user.get("id"),
                user.get("role"),
                assignment_id,
                result.get("case_id"),
                result.get("company_id_used"),
                False,
            )
        except Exception:
            pass
        return {"ok": True, "has_policy": False, "budget": None, "currency": DEFAULT_CURRENCY, "caps": {}, "total_cap": None}

    benefits = result.get("benefits") or []
    try:
        budget = caps_from_resolved_benefits(benefits)
    except Exception:
        budget = {"currency": DEFAULT_CURRENCY, "caps": {}, "total_cap": None}
    try:
        _log_employee_policy(
            "GET /api/employee/assignments/{id}/policy-budget",
            request_id,
            user.get("id"),
            user.get("role"),
            assignment_id,
            result.get("case_id"),
            result.get("company_id"),
            True,
            result.get("policy_id"),
            result.get("version_id"),
        )
    except Exception:
        pass
    return {"ok": True, "has_policy": True, "budget": budget, **budget}


@app.post("/api/assignments/{assignment_id}/evidence", response_model=AddEvidenceResponse)
def add_assignment_evidence(
    assignment_id: str,
    request: AddEvidenceRequest,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Phase 1 Step 3: Insert case_evidence for an assignment. Controlled insertion."""
    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=400, detail="Assignment missing case_id")
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    try:
        evidence_id = db.insert_case_evidence(
            case_id=case_id,
            assignment_id=assignment_id,
            participant_id=request.participant_id,
            requirement_id=request.requirement_id,
            evidence_type=request.evidence_type,
            file_url=request.file_url,
            metadata=request.metadata,
            status="submitted",
            request_id=request_id,
        )
        return AddEvidenceResponse(evidenceId=evidence_id)
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Evidence requires case_id in wizard_cases. HR-created cases use relocation_cases.",
        )


@app.get("/api/cases/{case_id}/evidence")
def get_case_evidence(
    case_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Phase 1 Step 3: List case_evidence for a case. For verification and debugging."""
    _ = _require_case_id_assignment_visible(case_id, user)
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    items = db.list_case_evidence(case_id, request_id=request_id)
    return {"case_id": case_id, "evidence": items}


# ---------------------------------------------------------------------------
# Timeline (case milestones)
# ---------------------------------------------------------------------------
@app.get("/api/cases/{case_id}/timeline")
def get_case_timeline(
    case_id: str,
    req: Request,
    ensure_defaults: bool = Query(False, description="Create default milestones if none exist"),
    include_links: bool = Query(True, description="Include milestone link rows (omit for lighter payloads)"),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """List operational relocation tasks (case_milestones). Optionally ensure default set exists."""
    access = _require_case_access(case_id, user)
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    milestones = db.list_case_milestones(case_id, request_id=request_id)

    if ensure_defaults and len(milestones) == 0:
        try:
            assignment = access.get("assignment", {})
            assignment_id = assignment.get("id")
            services = []
            if assignment_id:
                try:
                    svc_rows = db.list_case_services(assignment_id, request_id=request_id)
                    services = [r["service_key"] for r in svc_rows if r.get("selected") in (True, 1)]
                except Exception:
                    pass
            draft: Dict[str, Any] = {}
            target_move_date = None
            with SessionLocal() as session:
                case = app_crud.get_case(session, case_id)
                if case:
                    try:
                        raw_draft = json.loads(getattr(case, "draft_json", None) or "{}")
                        draft = raw_draft if isinstance(raw_draft, dict) else {}
                    except (json.JSONDecodeError, TypeError, ValueError):
                        draft = {}
                    target_move_date = getattr(case, "target_move_date", None)
            defaults = compute_default_milestones(
                case_id=case_id,
                case_draft=draft,
                selected_services=services,
                target_move_date=str(target_move_date) if target_move_date else None,
            )
            for m in defaults:
                try:
                    db.upsert_case_milestone(
                        case_id=case_id,
                        milestone_type=m["milestone_type"],
                        title=m["title"],
                        description=m.get("description"),
                        target_date=m.get("target_date"),
                        status=m.get("status", "pending"),
                        sort_order=m.get("sort_order", 0),
                        owner=m.get("owner", "joint"),
                        criticality=m.get("criticality", "normal"),
                        notes=m.get("notes"),
                        request_id=request_id,
                    )
                except Exception as upsert_exc:
                    log.warning(
                        "get_case_timeline ensure_defaults upsert failed case_id=%s type=%s: %s",
                        case_id,
                        m.get("milestone_type"),
                        upsert_exc,
                        exc_info=True,
                    )
            milestones = db.list_case_milestones(case_id, request_id=request_id)
        except Exception as exc:
            log.warning(
                "get_case_timeline ensure_defaults failed case_id=%s: %s",
                case_id,
                exc,
                exc_info=True,
            )
            milestones = db.list_case_milestones(case_id, request_id=request_id)

    if include_links:
        for m in milestones:
            m["links"] = db.list_milestone_links(m["id"], request_id=request_id)
    else:
        for m in milestones:
            m["links"] = []
    summary = compute_timeline_summary(milestones)
    return {"case_id": case_id, "milestones": milestones, "summary": summary}


@app.patch("/api/cases/{case_id}/timeline/milestones/{milestone_id}")
def update_case_milestone(
    case_id: str,
    milestone_id: str,
    req: Request,
    body: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Update a milestone (title, description, target_date, actual_date, status, sort_order)."""
    _ = _require_case_id_assignment_visible(case_id, user)
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    existing = next((m for m in db.list_case_milestones(case_id, request_id=request_id) if m.get("id") == milestone_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Milestone not found")
    merged = {
        "milestone_type": body.get("milestone_type") or existing.get("milestone_type", ""),
        "title": body.get("title") if body.get("title") is not None else existing.get("title", ""),
        "description": body.get("description") if "description" in body else existing.get("description"),
        "target_date": body.get("target_date") if "target_date" in body else existing.get("target_date"),
        "actual_date": body.get("actual_date") if "actual_date" in body else existing.get("actual_date"),
        "status": body.get("status") if body.get("status") is not None else existing.get("status", "pending"),
        "sort_order": body.get("sort_order") if body.get("sort_order") is not None else existing.get("sort_order", 0),
        "owner": body.get("owner") if "owner" in body else existing.get("owner", "joint"),
        "criticality": body.get("criticality") if "criticality" in body else existing.get("criticality", "normal"),
        "notes": body.get("notes") if "notes" in body else existing.get("notes"),
    }
    if merged.get("status") == "done" and not merged.get("actual_date"):
        merged["actual_date"] = date.today().isoformat()
    updated = db.upsert_case_milestone(
        case_id=case_id,
        milestone_type=merged["milestone_type"],
        title=merged["title"],
        description=merged["description"],
        target_date=merged["target_date"],
        actual_date=merged["actual_date"],
        status=merged["status"],
        sort_order=merged["sort_order"],
        owner=str(merged.get("owner") or "joint"),
        criticality=str(merged.get("criticality") or "normal"),
        notes=merged.get("notes"),
        milestone_id=milestone_id,
        request_id=request_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Milestone not found")
    links = db.list_milestone_links(milestone_id, request_id=request_id)
    updated["links"] = links
    return updated


@app.post("/api/cases/{case_id}/timeline/milestones/{milestone_id}/links")
def add_milestone_link(
    case_id: str,
    milestone_id: str,
    req: Request,
    body: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Link milestone to an entity (evidence, event, rfq, service). Body: { linked_entity_type, linked_entity_id }."""
    _ = _require_case_id_assignment_visible(case_id, user)
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    entity_type = body.get("linked_entity_type")
    entity_id = body.get("linked_entity_id")
    if not entity_type or not entity_id:
        raise HTTPException(status_code=400, detail="linked_entity_type and linked_entity_id required")
    db.link_milestone_entity(milestone_id, entity_type, entity_id, request_id=request_id)
    return {"ok": True}


@app.get("/api/dossier/questions", response_model=DossierQuestionsResponse)
def get_dossier_questions(
    case_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    access = _require_case_access(case_id, user)
    effective = access["effective_user"]
    with SessionLocal() as session:
        case = app_crud.get_case(session, case_id)
        if not case:
            case = app_crud.create_case(session, case_id, {
                "relocationBasics": {},
                "employeeProfile": {},
                "familyMembers": {},
                "assignmentContext": {},
            })
        draft = json.loads(case.draft_json or "{}")
    dest = _normalize_destination_country(
        (draft.get("relocationBasics") or {}).get("destCountry") or case.dest_country
    )
    if not dest:
        return DossierQuestionsResponse(
            destination_country=None,
            questions=[],
            answers={},
            mandatory_unanswered_count=0,
            is_step5_complete=True,
            sources_used=[],
        )
    profile = _build_profile_snapshot(draft)
    raw_questions = db.list_dossier_questions(dest)
    questions: List[DossierQuestionDTO] = []
    for q in raw_questions:
        if not evaluate_applies_if(q.get("applies_if"), profile):
            continue
        questions.append(DossierQuestionDTO(
            id=q["id"],
            question_text=q["question_text"],
            answer_type=q["answer_type"],
            options=q.get("options"),
            is_mandatory=bool(q.get("is_mandatory")),
            domain=q.get("domain") or "other",
            question_key=q.get("question_key"),
            source="library",
        ))
    case_questions = db.list_dossier_case_questions(case_id)
    for q in case_questions:
        questions.append(DossierQuestionDTO(
            id=q["id"],
            question_text=q["question_text"],
            answer_type=q["answer_type"],
            options=q.get("options"),
            is_mandatory=bool(q.get("is_mandatory")),
            domain="other",
            question_key=None,
            source="case",
        ))

    answers = {a["question_id"]: a["answer"] for a in db.list_dossier_answers(case_id, effective["id"])}
    case_answers = {a["case_question_id"]: a["answer"] for a in db.list_dossier_case_answers(case_id, effective["id"])}

    def _is_answered(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ""
        if isinstance(value, list):
            return len(value) > 0
        return True

    mandatory_unanswered = 0
    for q in questions:
        if not q.is_mandatory:
            continue
        value = answers.get(q.id) if q.source == "library" else case_answers.get(q.id)
        if not _is_answered(value):
            mandatory_unanswered += 1

    sources_rows = db.list_dossier_source_suggestions(case_id)
    seen_urls = set()
    sources_used: List[Dict[str, Any]] = []
    for row in sources_rows:
        for item in row.get("results") or []:
            url = item.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            sources_used.append({"title": item.get("title"), "url": url, "snippet": item.get("snippet", "")})

    return DossierQuestionsResponse(
        destination_country=dest,
        questions=questions,
        answers={**answers, **case_answers},
        mandatory_unanswered_count=mandatory_unanswered,
        is_step5_complete=mandatory_unanswered == 0,
        sources_used=sources_used,
    )


@app.post("/api/dossier/answers")
def save_dossier_answers(
    request: DossierAnswersRequest,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    access = _require_case_access(request.case_id, user)
    effective = access["effective_user"]
    raw_questions = db.list_dossier_questions("SG") + db.list_dossier_questions("US")
    question_lookup = {q["id"]: q for q in raw_questions}
    case_questions = db.list_dossier_case_questions(request.case_id)
    case_lookup = {q["id"]: q for q in case_questions}

    library_payload: List[Dict[str, Any]] = []
    case_payload: List[Dict[str, Any]] = []
    for item in request.answers:
        if item.question_id:
            q = question_lookup.get(item.question_id)
            if not q:
                raise HTTPException(status_code=400, detail="Unknown dossier question")
            err = validate_answer(item.answer, q["answer_type"], q.get("options"))
            if err:
                raise HTTPException(status_code=400, detail=err)
            library_payload.append({"question_id": item.question_id, "answer": item.answer})
        elif item.case_question_id:
            q = case_lookup.get(item.case_question_id)
            if not q:
                raise HTTPException(status_code=400, detail="Unknown case dossier question")
            err = validate_answer(item.answer, q["answer_type"], q.get("options"))
            if err:
                raise HTTPException(status_code=400, detail=err)
            case_payload.append({"case_question_id": item.case_question_id, "answer": item.answer})
        else:
            raise HTTPException(status_code=400, detail="question_id or case_question_id required")

    if library_payload:
        db.upsert_dossier_answers(request.case_id, effective["id"], library_payload)
    if case_payload:
        db.upsert_dossier_case_answers(request.case_id, effective["id"], case_payload)
    return {"ok": True}


@app.post("/api/dossier/search-suggestions", response_model=DossierSearchSuggestionsResponse)
def dossier_search_suggestions(
    request: DossierSearchSuggestionsRequest,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    _require_case_id_assignment_visible(request.case_id, user)
    with SessionLocal() as session:
        case = app_crud.get_case(session, request.case_id)
        if not case:
            return DossierSearchSuggestionsResponse(destination_country=None, sources=[], suggestions=[])
        draft = json.loads(case.draft_json or "{}")
    dest = _normalize_destination_country(
        (draft.get("relocationBasics") or {}).get("destCountry") or case.dest_country
    )
    if not dest:
        return DossierSearchSuggestionsResponse(destination_country=None, sources=[], suggestions=[])
    profile = _build_profile_snapshot(draft)
    search = fetch_search_results(dest, profile)
    results = search.get("results", [])
    if results:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            grouped.setdefault(r.get("query") or "query", []).append({
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("snippet", ""),
            })
        for q, items in grouped.items():
            db.add_dossier_source_suggestion(request.case_id, dest, q, items)
    suggestions = build_suggested_questions(dest, results)
    sources = [
        {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("snippet", "")}
        for r in results
    ]
    return DossierSearchSuggestionsResponse(
        destination_country=dest,
        sources=sources,
        suggestions=[DossierSuggestionDTO(**s) for s in suggestions],
    )


@app.post("/api/dossier/case-questions")
def add_dossier_case_question(
    request: DossierCaseQuestionRequest,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    _require_case_id_assignment_visible(request.case_id, user)
    allowed_types = {"text", "boolean", "select", "date", "multiselect"}
    if request.answer_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported answer_type")
    row = db.add_dossier_case_question(
        request.case_id,
        request.question_text,
        request.answer_type,
        request.options,
        request.is_mandatory,
        request.sources,
    )
    return {"question": row}


@app.post("/api/guidance/generate")
def generate_guidance(
    request: GuidanceGenerateRequest,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    if os.getenv("GUIDANCE_PACK_ENABLED", "true").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Guidance pack is disabled")
    access = _require_case_access(request.case_id, user)
    effective = access["effective_user"]
    guidance_mode = os.getenv("GUIDANCE_MODE", "demo").lower()
    if request.mode and user.get("is_admin"):
        if request.mode in ("demo", "strict"):
            guidance_mode = request.mode

    with SessionLocal() as session:
        case = app_crud.get_case(session, request.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        draft = json.loads(case.draft_json or "{}")
    dest = _normalize_destination_country(
        (draft.get("relocationBasics") or {}).get("destCountry") or case.dest_country
    )
    if not dest:
        raise HTTPException(status_code=400, detail="Destination country not available")
    if dest not in ("SG", "US"):
        raise HTTPException(status_code=400, detail="Unsupported destination corridor")

    packs = [p for p in db.list_knowledge_packs(dest) if p.get("status") == "active"]
    pack_ids = [p["id"] for p in packs]
    docs = db.list_knowledge_docs(pack_ids)
    rules = db.list_knowledge_rules(pack_ids)
    pack_versions = {p["id"]: p.get("version", 1) for p in packs}
    for rule in rules:
        rule["pack_version"] = pack_versions.get(rule.get("pack_id"), 1)
    docs_by_id = {d["id"]: d for d in docs}

    # Map dossier answers using question_key for stability
    dossier_answers = {}
    questions = db.list_dossier_questions(dest)
    q_by_id = {q["id"]: q for q in questions}
    for ans in db.list_dossier_answers(request.case_id, effective["id"]):
        q = q_by_id.get(ans["question_id"])
        if q and q.get("question_key"):
            dossier_answers[q["question_key"]] = ans["answer"]

    trace_id = str(uuid.uuid4())
    db.insert_trace_event(trace_id, request.case_id, "build_snapshot", {"dest": dest}, {}, "ok", None)
    outputs = generate_guidance_pack(
        case_id=request.case_id,
        user_id=effective["id"],
        destination_country=dest,
        draft=draft,
        dossier_answers=dossier_answers,
        rules=rules,
        docs_by_id=docs_by_id,
        guidance_mode=guidance_mode,
    )
    db.insert_trace_event(trace_id, request.case_id, "build_plan", {}, {"items": len(outputs["plan"].get("items", []))}, "ok", None)

    row = db.insert_guidance_pack(
        case_id=request.case_id,
        user_id=effective["id"],
        destination_country=dest,
        profile_snapshot=outputs["snapshot"],
        plan=outputs["plan"],
        checklist=outputs["checklist"],
        markdown=outputs["markdown"],
        sources=outputs["sources"],
        not_covered=outputs["not_covered"],
        coverage=outputs["coverage"],
        guidance_mode=guidance_mode,
        pack_hash=outputs["pack_hash"],
        rule_set=outputs["rule_set"],
    )
    now = datetime.utcnow().isoformat() + "Z"
    log_rows = []
    for log_item in outputs.get("rule_logs", []):
        log_rows.append({
            "id": str(uuid.uuid4()),
            "trace_id": trace_id,
            "case_id": request.case_id,
            "user_id": effective["id"],
            "destination_country": dest,
            "rule_id": log_item.get("rule_id"),
            "rule_key": log_item.get("rule_key"),
            "rule_version": log_item.get("rule_version", 1),
            "pack_id": log_item.get("pack_id"),
            "pack_version": log_item.get("pack_version", 1),
            "applies_if": json.dumps(log_item.get("applies_if")) if log_item.get("applies_if") is not None else None,
            "evaluation_result": 1 if log_item.get("evaluation_result") else 0,
            "was_baseline": 1 if log_item.get("was_baseline") else 0,
            "injected_for_minimum": 1 if log_item.get("injected_for_minimum") else 0,
            "citations": json.dumps(log_item.get("citations") or []),
            "snapshot_subset": json.dumps(log_item.get("snapshot_subset") or {}),
            "created_at": now,
        })
    db.insert_rule_evaluation_logs(log_rows)
    db.insert_trace_event(trace_id, request.case_id, "persist_pack", {"id": row["id"]}, {}, "ok", None)
    return {
        "guidance_pack_id": row["id"],
        "guidance_mode": guidance_mode,
        "pack_hash": outputs["pack_hash"],
        "rule_set": outputs["rule_set"],
        "plan": outputs["plan"],
        "checklist": outputs["checklist"],
        "markdown": outputs["markdown"],
        "sources": outputs["sources"],
        "not_covered": outputs["not_covered"],
        "coverage": outputs["coverage"],
    }


@app.get("/api/guidance/latest")
def get_guidance_latest(
    case_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    if os.getenv("GUIDANCE_PACK_ENABLED", "true").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Guidance pack is disabled")
    access = _require_case_access(case_id, user)
    effective = access["effective_user"]
    row = db.get_latest_guidance_pack(case_id, effective["id"])
    if not row:
        raise HTTPException(status_code=404, detail="No guidance pack found")
    return row


@app.get("/api/guidance/trace")
def get_guidance_trace(
    case_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    _require_case_id_assignment_visible(case_id, user)
    return {"events": db.list_trace_events(case_id)}


@app.get("/api/guidance/explain")
def get_guidance_explain(
    case_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    _require_case_id_assignment_visible(case_id, user)
    trace_events = db.list_trace_events(case_id)
    trace_id = trace_events[0]["trace_id"] if trace_events else None
    logs = db.list_rule_evaluation_logs(case_id, trace_id)
    if not user.get("is_admin"):
        rejected_count = len([l for l in logs if not l.get("evaluation_result")])
        logs = [l for l in logs if l.get("evaluation_result")]
    else:
        rejected_count = len([l for l in logs if not l.get("evaluation_result")])
    return {
        "trace_id": trace_id,
        "rejected_count": rejected_count,
        "logs": [
            {
                "rule_key": l.get("rule_key"),
                "version": l.get("rule_version"),
                "evaluation_result": l.get("evaluation_result"),
                "was_baseline": l.get("was_baseline"),
                "injected_for_minimum": l.get("injected_for_minimum"),
                "snapshot_subset": l.get("snapshot_subset"),
                "citations": l.get("citations"),
                "pack_version": l.get("pack_version"),
            }
            for l in logs
        ],
    }


@app.get("/api/requirements/sufficiency")
def get_requirements_sufficiency(
    case_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    access = _require_case_access(case_id, user)
    effective = access["effective_user"]
    uid = effective.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        data = compute_requirements_sufficiency(case_id, str(uid))
        return {
            "compute_status": "ok",
            "message": None,
            **data,
        }
    except ValueError as e:
        if "Case not found" in str(e):
            raise HTTPException(status_code=404, detail="Case not found")
        log.warning("compute_requirements_sufficiency value error case %s: %s", case_id, e)
        return {
            "compute_status": "insufficient_data",
            "message": "More case information is needed before this recommendation can be calculated.",
            "destination_country": None,
            "missing_fields": [],
            "supporting_requirements": [],
        }
    except Exception as e:
        log.warning("compute_requirements_sufficiency failed for case %s: %s", case_id, e, exc_info=True)
        return {
            "compute_status": "unavailable",
            "message": "More case information is needed before this recommendation can be calculated.",
            "destination_country": None,
            "missing_fields": [],
            "supporting_requirements": [],
        }


@app.get("/api/notifications")
def list_notifications(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    only_unread: bool = Query(False),
    user: Dict[str, Any] = Depends(get_current_user),
):
    role = UserRole.EMPLOYEE if user.get("role") == UserRole.EMPLOYEE.value else UserRole.HR
    effective = _effective_user(user, role)
    uid = effective.get("id")
    if not uid:
        return []
    rows = db.list_notifications(
        uid,
        limit=limit,
        only_unread=only_unread,
        request_id=getattr(request.state, "request_id", None),
    )
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "assignment_id": r.get("assignment_id"),
            "case_id": r.get("case_id"),
            "type": r["type"],
            "title": r["title"],
            "body": r.get("body"),
            "metadata": json.loads(r["metadata"]) if isinstance(r.get("metadata"), str) else (r.get("metadata") or {}),
            "read_at": r.get("read_at"),
        }
        for r in rows
    ]


@app.get("/api/notifications/unread-count")
def get_unread_count(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    role = UserRole.EMPLOYEE if user.get("role") == UserRole.EMPLOYEE.value else UserRole.HR
    effective = _effective_user(user, role)
    uid = effective.get("id")
    if not uid:
        return {"count": 0}
    return {
        "count": db.count_unread_notifications(
            uid, request_id=getattr(request.state, "request_id", None)
        )
    }


@app.patch("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    role = UserRole.EMPLOYEE if user.get("role") == UserRole.EMPLOYEE.value else UserRole.HR
    effective = _effective_user(user, role)
    uid = effective.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not db.mark_notification_read(notification_id, uid):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


class NotifyHrRequest(BaseModel):
    assignment_id: str


@app.post("/api/notifications/notify-hr")
def notify_hr_employee_saved(
    request: NotifyHrRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE)),
):
    assignment = db.get_assignment_by_id(request.assignment_id) or db.get_assignment_by_case_id(request.assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    effective = _effective_user(user, UserRole.EMPLOYEE)
    if assignment.get("employee_user_id") != effective["id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    hr_id = assignment.get("hr_user_id")
    if not hr_id:
        return {"ok": True}
    try:
        db.create_notification_with_preferences(
            user_id=hr_id,
            type_="EMPLOYEE_SAVED",
            title="Employee updated the case",
            body=f"New updates were saved for case {request.assignment_id[:8]}…",
            assignment_id=request.assignment_id,
            case_id=assignment.get("case_id"),
            metadata={"assignment_id": request.assignment_id},
        )
    except Exception as e:
        try:
            db.insert_notification(
                notification_id=str(uuid.uuid4()),
                user_id=hr_id,
                type_="EMPLOYEE_SAVED",
                title="Employee updated the case",
                body=f"New updates were saved for case {request.assignment_id[:8]}…",
                assignment_id=request.assignment_id,
                case_id=assignment.get("case_id"),
                metadata={"assignment_id": request.assignment_id},
            )
        except Exception as e2:
            log.warning("Failed to create notification for employee save: %s", e2)
    return {"ok": True}


@app.get("/api/debug/cases/{case_id}/events")
def debug_case_events(
    case_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Dev/admin: list case_events for a case to verify event emission."""
    events = db.list_case_events(case_id)
    return {"case_id": case_id, "events": events, "count": len(events)}


@app.get("/api/debug/assignment-check")
def debug_assignment_check(
    assignment_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Dev-only: verify assignment visibility for current user. Uses backend auth (relopass_token)."""
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        return {"found": False, "row": None, "current_user_id": user.get("id")}
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    visible = False
    eid_dbg = effective.get("id")
    if is_employee and eid_dbg is not None and emp_id == eid_dbg:
        visible = True
    if is_hr and (effective.get("is_admin") or (eid_dbg is not None and hr_id == eid_dbg)):
        visible = True
    if not visible:
        return {"found": False, "row": None, "current_user_id": effective.get("id")}
    return {
        "found": True,
        "row": {
            "id": assignment["id"],
            "case_id": assignment["case_id"],
            "employee_user_id": emp_id,
            "hr_user_id": hr_id,
            "status": assignment.get("status", ""),
            "created_at": assignment.get("created_at", ""),
            "updated_at": assignment.get("updated_at", ""),
        },
        "current_user_id": effective.get("id"),
    }


@app.post("/api/hr/assignments/{assignment_id}/identifier")
def update_assignment_identifier(
    assignment_id: str,
    request: UpdateAssignmentIdentifierRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR))
):
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    identifier = request.employeeIdentifier.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Employee identifier required")

    db.update_assignment_identifier(assignment_id, identifier)
    return {"success": True}


@app.post("/api/hr/assignments/{assignment_id}/run-compliance")
def run_compliance(assignment_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    profile = db.get_employee_profile(assignment_id)
    profile_present = profile is not None
    if not profile:
        profile = {}

    report = compliance_engine.run(profile)
    from .provenance_catalog import enrich_assignment_compliance_report

    report = enrich_assignment_compliance_report(
        report, assignment_id=assignment_id, profile_present=profile_present
    )
    db.save_compliance_report(str(uuid.uuid4()), assignment_id, report)

    status = normalize_status(assignment["status"])
    # For canonical workflow, keep the assignment in 'submitted' once compliance has run
    # (or move awaiting_intake -> submitted if HR runs compliance pre-submission).
    if status in [AssignmentStatus.SUBMITTED.value, AssignmentStatus.AWAITING_INTAKE.value]:
        assert_canonical_status(AssignmentStatus.SUBMITTED.value)
        db.update_assignment_status(assignment_id, AssignmentStatus.SUBMITTED.value)
    return report


@app.post("/api/hr/assignments/{assignment_id}/decision")
def hr_decision(assignment_id: str, request: HRAssignmentDecision, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    case_id = assignment.get("case_id") or ""

    if request.decision not in [AssignmentStatus.APPROVED, AssignmentStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Invalid decision")

    notes_payload = request.notes
    # For the simplified canonical lifecycle we treat decisions as final approved / rejected.
    assert_canonical_status(request.decision.value)
    db.set_assignment_decision(assignment_id, request.decision.value, notes_payload)

    event_type = "assignment.approved" if request.decision == AssignmentStatus.APPROVED else "assignment.rejected"
    try:
        db.insert_case_event(
            case_id=case_id,
            assignment_id=assignment_id,
            actor_principal_id=effective["id"],
            event_type=event_type,
            payload={"notes": notes_payload} if notes_payload else {},
        )
    except Exception as exc:
        log.error(
            "event_insert_error assignment_id=%s case_id=%s event_type=%s error=%s",
            assignment_id,
            case_id,
            event_type,
            str(exc),
            exc_info=True,
        )
        raise

    return {"success": True}


@app.get("/api/employee/policy/caps")
def get_employee_policy_caps(user: Dict[str, Any] = Depends(get_current_user)):
    """Return policy caps for package comparison (housing/month, movers, schools, in USD)."""
    policy = policy_engine.load_policy()
    caps = policy.get("caps", {})
    return {
        "housing_monthly_usd": caps.get("housing", {}).get("amount", 5000),
        "movers_usd": caps.get("movers", {}).get("amount", 10000),
        "schools_usd": caps.get("schools", {}).get("amount", 20000),
        "immigration_usd": caps.get("immigration", {}).get("amount", 4000),
    }


# ---------------------------------------------------------------------------
# HR Policy Management (full policy spec - create, edit, upload)
# ---------------------------------------------------------------------------
@app.get("/api/hr/policies")
def list_hr_policies(
    status: Optional[str] = Query(None),
    companyEntity: Optional[str] = Query(None, alias="companyEntity"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    policies = db.list_hr_policies(status_filter=status, company_entity=companyEntity)
    return {"policies": policies}


@app.post("/api/hr/policies")
def create_hr_policy(
    body: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    policy_id = body.get("policyId") or str(uuid.uuid4())
    body["policyId"] = policy_id
    body["status"] = body.get("status", "draft")
    body["version"] = body.get("version", 1)
    db.create_hr_policy(policy_id, body, created_by=user.get("id"))
    return {"policyId": policy_id, "policy": body}


@app.post("/api/hr/policies/upload")
async def upload_hr_policy(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Upload HR policy JSON or YAML file. Creates a new policy from the file content."""
    content = await file.read()
    try:
        raw = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    try:
        if file.filename and (file.filename.endswith(".yaml") or file.filename.endswith(".yml")):
            try:
                import yaml
                policy = yaml.safe_load(raw)
            except ImportError:
                raise HTTPException(status_code=400, detail="YAML support requires PyYAML. Use JSON format.")
        else:
            policy = json.loads(raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON/YAML: {str(e)}")
    if not isinstance(policy, dict):
        raise HTTPException(status_code=400, detail="Policy must be a JSON object")
    policy_id = policy.get("policyId") or str(uuid.uuid4())
    policy["policyId"] = policy_id
    policy["status"] = policy.get("status", "draft")
    policy["version"] = policy.get("version", 1)
    if not policy.get("effectiveDate"):
        policy["effectiveDate"] = datetime.utcnow().strftime("%Y-%m-%d")
    if not policy.get("employeeBands"):
        policy["employeeBands"] = ["Band1", "Band2", "Band3", "Band4"]
    if not policy.get("assignmentTypes"):
        policy["assignmentTypes"] = ["Permanent", "Long-Term", "Short-Term"]
    if not policy.get("benefitCategories"):
        policy["benefitCategories"] = {}
    db.create_hr_policy(policy_id, policy, created_by=user.get("id"))
    return {"policyId": policy_id, "policy": policy, "message": "Policy uploaded successfully"}


# ---------------------------------------------------------------------------
# Company Policy Documents (docx/pdf + extracted benefits)
# ---------------------------------------------------------------------------
@app.get("/api/company-policies")
def list_company_policies(
    company_id: Optional[str] = Query(None, description="Admin override: scope to this company"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    cid = _resolve_company_for_policy(user, company_id)
    policies = db.list_company_policies(cid)
    return {"policies": policies}


# ---------------------------------------------------------------------------
# Policy Document Intake (staging layer before company_policies)
#
# Three-stage pipeline:
# - Ingest (upload): store file, extract raw text and metadata, segment clauses.
#   One document -> one policy_documents row; clauses in policy_document_clauses.
# - Reprocess: re-run extraction and clause segmentation from stored file.
#   Used when extraction/segmentation logic improves or to fix failures.
# - Normalize: transform clauses into company_policies, policy_versions, benefit_rules,
#   exclusions, evidence_requirements, conditions, source_links. Separate so HR can
#   reprocess without overwriting normalized edits and so we can re-normalize after
#   taxonomy changes while keeping versioning and traceability.
# ---------------------------------------------------------------------------

BUCKET_HR_POLICIES = "hr-policies"

# Download-url error codes (stable, for frontend mapping)
POLICY_POLICY_NOT_FOUND = "policy_policy_not_found"
POLICY_FILE_MISSING = "policy_file_missing"
POLICY_FILE_PATH_INVALID = "policy_file_path_invalid"
POLICY_FILE_SIGN_FAILED = "policy_file_sign_failed"
POLICY_STORAGE_UNEXPECTED_ERROR = "policy_storage_unexpected_error"


def resolve_policy_storage_object_key(raw: str) -> str:
    """
    Resolve raw file_url / storage_path to object key only for storage.from_(BUCKET_HR_POLICIES).
    Handles:
    - legacy bucket-prefixed: hr-policies/companies/...
    - object-key-only: companies/...
    - full signed/public URL: extract object key from path
    Returns empty string if invalid.
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip()
    if not s:
        return ""
    # Full URL: extract path and resolve
    if s.startswith("http://") or s.startswith("https://"):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(s)
            path = parsed.path or ""
            # Supabase: .../object/public/hr-policies/KEY or .../object/sign/hr-policies/KEY
            if "/hr-policies/" in path:
                return path.split("/hr-policies/", 1)[-1].lstrip("/")
            return ""
        except Exception:
            return ""
    # Strip leading bucket prefix
    if s.startswith("hr-policies/"):
        return s[len("hr-policies/"):]
    if "/hr-policies/" in s:
        return s.split("/hr-policies/", 1)[-1]
    # Already object key (companies/...)
    if s.startswith("companies/"):
        return s
    return s


def normalize_policy_storage_object_key(path: str) -> str:
    """Alias for resolve_policy_storage_object_key. Used by extract/reprocess."""
    return resolve_policy_storage_object_key(path)


def _sanitize_storage_filename(name: str) -> str:
    """Make filename S3/storage-safe: replace spaces and problematic chars."""
    import re
    import unicodedata
    base, _, ext = name.rpartition(".")
    safe = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    safe = re.sub(r"[^a-zA-Z0-9._-]", "-", safe).strip("-._") or "file"
    safe = re.sub(r"-+", "-", safe)
    ext = (ext or "").lower()
    return f"{safe}.{ext}" if ext else safe


# Policy upload error codes (stable, for frontend mapping)
UPLOAD_MISSING_FILE = "upload_missing_file"
UPLOAD_INVALID_MIME_TYPE = "upload_invalid_mime_type"
UPLOAD_EMPTY_FILE = "upload_empty_file"
UPLOAD_STORAGE_FAILED = "upload_storage_failed"
UPLOAD_DB_INSERT_FAILED = "upload_db_insert_failed"
UPLOAD_EXTRACT_FAILED = "upload_extract_failed"
UPLOAD_PROCESSING_FAILED = "upload_processing_failed"
UPLOAD_UNEXPECTED_EXCEPTION = "upload_unexpected_exception"


def _upload_error_response(
    error_code: str,
    message: str,
    status: int = 500,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Return structured JSON error for policy upload."""
    content: Dict[str, Any] = {"ok": False, "error_code": error_code, "message": message}
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=status, content=content)


@app.get("/api/hr/policy-documents/health")
def policy_documents_health(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    """
    Diagnostic endpoint for policy document upload readiness.
    Returns: supabase_project_ref, database_project_ref, project_refs_match,
    bucket_probe (list_buckets, list_objects, diagnosis), table checks.
    """
    from .services.policy_storage_health import check_policy_storage_health
    health = check_policy_storage_health(db)
    return health


@app.post("/api/hr/policy-documents/upload")
async def upload_policy_document(
    req: Request,
    file: Optional[UploadFile] = File(None),
    company_id: Optional[str] = Query(None, description="Admin override: scope upload to this company"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Upload policy PDF/DOCX for intake: extract text, classify, extract metadata.
    When admin is viewing a company's policy workspace, pass company_id so the document is stored for that company.
    Stages: A.validate -> B.storage -> C.db_insert -> D.extraction -> E.update_status -> F.return
    """
    from .services.policy_storage_health import (
        check_policy_storage_health,
        STORAGE_MISSING_SERVICE_ROLE,
        STORAGE_BUCKET_NOT_FOUND,
        POLICY_DOCUMENTS_TABLE_MISSING,
    )
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    user_id = user.get("id", "")
    filename = ""
    mime = ""
    file_size = 0
    content: bytes = b""

    # --- Stage A: Resolve company (admin may override with company_id) ---
    log.info(
        "request_id=%s policy_upload started user_id=%s",
        request_id, user_id[:8] + "…" if user_id and len(user_id) > 8 else user_id,
    )
    try:
        cid = _resolve_company_for_policy(user, company_id)
        if not cid or not str(cid).strip():
            return _upload_error_response(
                "upload_company_required",
                "Company is required for upload. When viewing a company's policy workspace, uploads are scoped to that company.",
                400,
                request_id=request_id,
            )
        company_id = cid.strip()
    except HTTPException:
        raise
    except Exception as exc:
        log.error("request_id=%s policy_upload company lookup failed: %s", request_id, exc, exc_info=True)
        return _upload_error_response(
            UPLOAD_UNEXPECTED_EXCEPTION,
            "Failed to resolve company for user.",
            500,
            request_id=request_id,
        )

    if not file or not getattr(file, "filename", None) or not str(file.filename).strip():
        log.warning("request_id=%s policy_upload stage=validate error=upload_missing_file", request_id)
        return _upload_error_response(
            UPLOAD_MISSING_FILE,
            "Please choose a file first.",
            400,
            request_id=request_id,
        )

    filename = str(file.filename).strip()
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ("docx", "pdf"):
        log.warning("request_id=%s policy_upload stage=validate error=upload_invalid_mime_type filename=%s ext=%s", request_id, filename, ext)
        return _upload_error_response(
            UPLOAD_INVALID_MIME_TYPE,
            "Only PDF or DOCX files are supported.",
            400,
            request_id=request_id,
        )

    try:
        content = await file.read()
    except Exception as exc:
        log.error("request_id=%s policy_upload stage=validate read failed: %s", request_id, exc, exc_info=True)
        return _upload_error_response(
            UPLOAD_UNEXPECTED_EXCEPTION,
            "Failed to read uploaded file.",
            500,
            request_id=request_id,
        )

    file_size = len(content)
    if file_size == 0:
        log.warning("request_id=%s policy_upload stage=validate error=upload_empty_file filename=%s", request_id, filename)
        return _upload_error_response(
            UPLOAD_EMPTY_FILE,
            "The selected file is empty.",
            400,
            request_id=request_id,
        )

    mime = file.content_type or (
        "application/pdf" if ext == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    log.info(
        "request_id=%s policy_upload stage=validate ok filename=%s mime=%s file_size=%d company_id=%s",
        request_id, filename, mime, file_size, company_id[:8] + "…" if company_id and len(company_id) > 8 else company_id,
    )

    # Validate config before upload
    health = check_policy_storage_health(db)
    if not health["supabase_url_present"] or not health["service_role_present"]:
        log.error(
            "request_id=%s policy_upload stage=config error=config_missing url=%s service_role=%s",
            request_id, health["supabase_url_present"], health["service_role_present"],
        )
        return _upload_error_response(
            STORAGE_MISSING_SERVICE_ROLE,
            "Policy document uploads require Supabase storage. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend .env (see .env.example) to enable uploads.",
            503,
            request_id=request_id,
        )
    if not health["bucket_access_ok"]:
        config_err = health.get("config_error")
        if config_err in ("wrong_key_type", "wrong_project_url_key_mismatch"):
            log.error("request_id=%s policy_upload stage=config error=config_error diagnosis=%s", request_id, config_err)
            return _upload_error_response(
                STORAGE_MISSING_SERVICE_ROLE,
                "Invalid API key: in the backend .env use SUPABASE_URL from your project (e.g. https://xxxxx.supabase.co) "
                "and SUPABASE_SERVICE_ROLE_KEY from Supabase → Settings → API (the service_role secret, not the anon key). "
                "Restart the backend after changing .env.",
                503,
                request_id=request_id,
            )
        log.error("request_id=%s policy_upload stage=config error=bucket_not_ok", request_id)
        return _upload_error_response(
            STORAGE_BUCKET_NOT_FOUND,
            "Policy storage bucket is unavailable. In Supabase go to Storage → New bucket, create a bucket named hr-policies (public or private), then try again.",
            503,
            request_id=request_id,
        )
    if not health["policy_documents_table_ok"]:
        log.error("request_id=%s policy_upload stage=config error=policy_documents_table_missing", request_id)
        return _upload_error_response(
            POLICY_DOCUMENTS_TABLE_MISSING,
            "Policy database tables are missing.",
            503,
            request_id=request_id,
        )

    checksum = None
    try:
        from .services.policy_document_intake import compute_checksum
        checksum = compute_checksum(content)
    except Exception as e:
        log.warning("request_id=%s policy_upload checksum failed: %s", request_id, e)

    doc_id = str(uuid.uuid4())
    storage_filename = _sanitize_storage_filename(filename)
    path = f"companies/{company_id}/policy-documents/{doc_id}/{storage_filename}"

    # --- Stage B: Upload to Supabase Storage ---
    try:
        supabase = get_supabase_admin_client()
        supabase.storage.from_(BUCKET_HR_POLICIES).upload(
            path, content,
            {"content-type": mime, "upsert": "true"},
        )
        log.info("request_id=%s policy_upload stage=storage ok path=%s", request_id, path)
    except Exception as exc:
        # Extract StorageException details for logging (storage3 passes dict as exc.args)
        exc_detail = {}
        if hasattr(exc, "args") and exc.args and isinstance(exc.args[0], dict):
            d = exc.args[0]
            exc_detail = {
                "status_code": d.get("statusCode") or d.get("status_code"),
                "error_code": d.get("error") or d.get("code"),
                "message": (d.get("message") or str(d))[:200],
            }
        log.error(
            "request_id=%s policy_upload stage=storage failed filename=%s path=%s exc=%s exc_detail=%s",
            request_id, filename, path, exc, exc_detail, exc_info=True,
        )
        code, msg = _map_storage_exception_to_response(exc, BUCKET_HR_POLICIES)
        return _upload_error_response(code, msg, 500, request_id=request_id)

    # --- Stage C: Insert row in policy_documents ---
    try:
        db.create_policy_document(
            doc_id=doc_id,
            company_id=company_id,
            uploaded_by_user_id=user_id,
            filename=filename,
            mime_type=mime,
            storage_path=path,
            checksum=checksum,
            request_id=request_id,
        )
        log.info("request_id=%s policy_upload stage=db_insert ok doc_id=%s", request_id, doc_id)
    except Exception as exc:
        safe_msg = (str(exc) or type(exc).__name__)[:200]
        log.error(
            "request_id=%s policy_pipeline stage=ingest document_id=%s company_id=%s user_id=%s success=false exc_type=%s exc_msg=%s",
            request_id, doc_id, company_id, user_id, type(exc).__name__, safe_msg, exc_info=True,
        )
        try:
            supabase = get_supabase_admin_client()
            supabase.storage.from_(BUCKET_HR_POLICIES).remove([path])
            log.info("request_id=%s policy_upload stage=db_insert cleanup ok removed path=%s", request_id, path)
        except Exception as cleanup_exc:
            log.warning("request_id=%s policy_upload stage=db_insert cleanup failed: %s", request_id, cleanup_exc)
        return _upload_error_response(
            UPLOAD_DB_INSERT_FAILED,
            "Failed to save uploaded policy document.",
            500,
            request_id=request_id,
        )

    # --- Stage D: Run extraction/classification ---
    extraction_failed = False
    try:
        from .services.policy_document_intake import process_uploaded_document
        result = process_uploaded_document(content, mime, filename, request_id=request_id)
        log.info(
            "request_id=%s policy_upload stage=extract ok status=%s",
            request_id, result.get("processing_status"),
        )
        # --- Stage E: Update processing_status ---
        db.update_policy_document(
            doc_id,
            processing_status=result.get("processing_status"),
            detected_document_type=result.get("detected_document_type"),
            detected_policy_scope=result.get("detected_policy_scope"),
            version_label=result.get("version_label"),
            effective_date=result.get("effective_date"),
            raw_text=result.get("raw_text"),
            extraction_error=result.get("extraction_error"),
            extracted_metadata=result.get("extracted_metadata"),
            request_id=request_id,
        )
        if result.get("processing_status") == "failed":
            extraction_failed = True
            log.warning(
                "request_id=%s policy_upload stage=extract failed extraction_error=%s",
                request_id, (result.get("extraction_error") or "")[:200],
            )
        # Segment into clauses when we have raw text
        if result.get("raw_text") and result.get("processing_status") != "failed":
            try:
                from .services.policy_document_clauses import segment_document_from_raw_text
                clauses, seg_err = segment_document_from_raw_text(
                    result["raw_text"], mime, data=content
                )
                if not seg_err and clauses:
                    db.upsert_policy_document_clauses(doc_id, clauses, request_id=request_id)
                    log.info("request_id=%s policy_upload stage=segment ok clauses=%d", request_id, len(clauses))
            except Exception as seg_exc:
                log.warning("request_id=%s policy_upload stage=segment failed: %s", request_id, seg_exc)
    except Exception as exc:
        safe_msg = (str(exc) or type(exc).__name__)[:200]
        log.error(
            "request_id=%s policy_pipeline stage=ingest document_id=%s company_id=%s user_id=%s success=false exc_type=%s exc_msg=%s",
            request_id, doc_id, company_id, user_id, type(exc).__name__, safe_msg, exc_info=True,
        )
        extraction_failed = True
        db.update_policy_document(
            doc_id,
            processing_status="failed",
            extraction_error=str(exc),
            request_id=request_id,
        )

    doc = db.get_policy_document(doc_id, request_id=request_id)
    num_clauses = len(db.list_policy_document_clauses(doc_id, request_id=request_id)) if doc_id else 0
    success = not extraction_failed
    log.info(
        "request_id=%s policy_pipeline stage=ingest document_id=%s company_id=%s user_id=%s success=%s rows_document=1 rows_clauses=%d",
        request_id, doc_id, company_id, user_id, success, num_clauses,
    )

    # --- Stage F: Return ---
    if extraction_failed:
        return JSONResponse(
            status_code=207,
            content={
                "ok": False,
                "error_code": UPLOAD_EXTRACT_FAILED,
                "message": "The file was uploaded, but extraction failed.",
                "request_id": request_id,
                "document": doc,
            },
        )
    return {"ok": True, "document": doc, "request_id": request_id}


@app.get("/api/hr/policy-documents")
def list_policy_documents(
    req: Request,
    company_id: Optional[str] = Query(None, description="Admin override: scope to this company"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """List policy documents for company. Admin without company_id gets empty list (no error)."""
    request_id = getattr(req.state, "request_id", None)
    # Admin with no company scope: return empty list so the page loads; they can use Admin → company → Policy for scope.
    if user.get("is_admin") and not (company_id and str(company_id).strip()):
        return {"documents": []}
    cid = _resolve_company_for_policy(user, company_id)
    docs = db.list_policy_documents(cid, request_id=request_id)
    return {"documents": docs}


@app.get("/api/hr/policy-documents/{doc_id}")
def get_policy_document(
    doc_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Get policy document by id."""
    request_id = getattr(req.state, "request_id", None)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    _require_document_access(user, doc)
    return {"document": doc}


@app.post("/api/hr/policy-documents/bulk-delete")
def bulk_delete_policy_documents(
    body: Dict[str, Any] = Body(...),
    req: Request = None,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Delete uploaded policy document records by id. Skips documents that are referenced
    by any policy_version (source_policy_document_id). Only deletes source document
    records; does not delete published policy versions.
    """
    request_id = getattr(req.state, "request_id", None) if req else None
    doc_ids = body.get("document_ids") or []
    if not isinstance(doc_ids, list):
        raise HTTPException(status_code=400, detail="document_ids must be a list")
    deleted = 0
    skipped: List[Dict[str, Any]] = []
    for doc_id in doc_ids:
        doc_id = str(doc_id).strip()
        if not doc_id:
            continue
        doc = db.get_policy_document(doc_id, request_id=request_id)
        if not doc:
            skipped.append({"id": doc_id, "reason": "not_found"})
            continue
        try:
            _require_document_access(user, doc)
        except HTTPException:
            skipped.append({"id": doc_id, "reason": "forbidden"})
            continue
        if db.policy_version_references_document(doc_id):
            skipped.append({"id": doc_id, "reason": "referenced_by_version"})
            continue
        if db.delete_policy_document(doc_id, request_id=request_id):
            deleted += 1
    return {"ok": True, "deleted": deleted, "skipped": skipped}


@app.get("/api/hr/policy-documents/{doc_id}/clauses")
def list_policy_document_clauses(
    doc_id: str,
    req: Request,
    clause_type: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """List clauses for a policy document. Optional filter by clause_type."""
    request_id = getattr(req.state, "request_id", None) if req else None
    doc = db.get_policy_document(doc_id, request_id=request_id)
    _require_document_access(user, doc)
    clauses = db.list_policy_document_clauses(doc_id, clause_type=clause_type, request_id=request_id)
    return {"clauses": clauses}


@app.get("/api/hr/policy-documents/{doc_id}/clauses/{clause_id}")
def get_policy_document_clause(
    doc_id: str,
    clause_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Get a single clause for source comparison / view source."""
    request_id = getattr(req.state, "request_id", None) if req else None
    doc = db.get_policy_document(doc_id, request_id=request_id)
    _require_document_access(user, doc)
    clause = db.get_policy_document_clause(clause_id, request_id=request_id)
    if not clause or clause.get("policy_document_id") != doc_id:
        raise HTTPException(status_code=404, detail="Clause not found")
    return {"clause": clause}


@app.patch("/api/hr/policy-documents/{doc_id}/clauses/{clause_id}")
def patch_policy_document_clause(
    doc_id: str,
    clause_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR override: update clause_type, title, or hr_override_notes."""
    request_id = getattr(req.state, "request_id", None)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    _require_document_access(user, doc)
    clause = db.get_policy_document_clause(clause_id, request_id=request_id)
    if not clause or clause.get("policy_document_id") != doc_id:
        raise HTTPException(status_code=404, detail="Clause not found")
    db.update_policy_document_clause(
        clause_id,
        clause_type=body.get("clause_type"),
        title=body.get("title"),
        hr_override_notes=body.get("hr_override_notes"),
        request_id=request_id,
    )
    updated = db.get_policy_document_clause(clause_id, request_id=request_id)
    return {"clause": updated}


@app.post("/api/hr/policy-documents/{doc_id}/reprocess")
async def reprocess_policy_document(
    doc_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Reprocess stage: re-run text extraction, classification, and clause segmentation from stored file.
    Does not re-upload; uses existing storage_path. Use when extraction logic improves or to fix failures.
    Does not overwrite normalized policy_versions/benefit_rules; those are created only by normalize.
    """
    request_id = getattr(req.state, "request_id", None)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    _require_document_access(user, doc)
    file_path = doc.get("storage_path") or ""
    object_key = normalize_policy_storage_object_key(file_path)
    log.info("request_id=%s policy_document_reprocess bucket=%s object_key=%s", request_id, BUCKET_HR_POLICIES, object_key)
    try:
        supabase = get_supabase_admin_client()
        data = supabase.storage.from_(BUCKET_HR_POLICIES).download(object_key)
    except Exception as exc:
        log.warning("request_id=%s policy_document_reprocess download failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=_sanitize_storage_error(exc, BUCKET_HR_POLICIES))
    try:
        from .services.policy_document_intake import process_uploaded_document
        result = process_uploaded_document(
            data, doc.get("mime_type", ""), doc.get("filename", ""), request_id=request_id
        )
        db.update_policy_document(
            doc_id,
            processing_status=result.get("processing_status"),
            detected_document_type=result.get("detected_document_type"),
            detected_policy_scope=result.get("detected_policy_scope"),
            version_label=result.get("version_label"),
            effective_date=result.get("effective_date"),
            raw_text=result.get("raw_text"),
            extraction_error=result.get("extraction_error"),
            extracted_metadata=result.get("extracted_metadata"),
            request_id=request_id,
        )
        # Re-segment clauses
        if result.get("raw_text") and result.get("processing_status") != "failed":
            try:
                from .services.policy_document_clauses import segment_document_from_raw_text
                clauses, seg_err = segment_document_from_raw_text(
                    result["raw_text"], doc.get("mime_type", ""), data=data
                )
                if not seg_err and clauses:
                    db.upsert_policy_document_clauses(doc_id, clauses, request_id=request_id)
                    log.info("request_id=%s policy_document_reprocess segmented %d clauses", request_id, len(clauses))
            except Exception as seg_exc:
                log.warning("request_id=%s policy_document_reprocess segmentation failed: %s", request_id, seg_exc)
    except Exception as exc:
        safe_msg = (str(exc) or type(exc).__name__)[:200]
        log.warning(
            "request_id=%s policy_pipeline stage=reprocess document_id=%s company_id=%s user_id=%s success=false exc_type=%s exc_msg=%s",
            request_id, doc_id, doc.get("company_id") if doc else None, user.get("id") if user else None,
            type(exc).__name__, safe_msg, exc_info=True,
        )
        db.update_policy_document(
            doc_id, processing_status="failed", extraction_error=str(exc), request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"Reprocess failed: {str(exc)}")
    doc = db.get_policy_document(doc_id, request_id=request_id)
    num_clauses = len(db.list_policy_document_clauses(doc_id, request_id=request_id))
    log.info(
        "request_id=%s policy_pipeline stage=reprocess document_id=%s company_id=%s user_id=%s success=true clauses=%d",
        request_id, doc_id, doc.get("company_id") if doc else None, user.get("id") if user else None, num_clauses,
    )
    return {"document": doc}


@app.post("/api/hr/policy-documents/{doc_id}/normalize")
def normalize_policy_document(
    doc_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    Normalize stage: transform extracted clauses into structured policy objects.
    Creates/attaches company_policy, policy_version, benefit_rules, exclusions, evidence_requirements,
    conditions, assignment/family applicability, and source_links (traceability to clauses).
    Output is versioned and traceable to source_policy_document_id and clause ids.
    """
    request_id = getattr(req.state, "request_id", None)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    _require_document_access(user, doc)
    if not doc.get("raw_text"):
        raise HTTPException(status_code=400, detail="Document has no extracted text. Run Reprocess first.")
    clauses = db.list_policy_document_clauses(doc_id, request_id=request_id)
    if not clauses:
        raise HTTPException(status_code=400, detail="No clauses. Run Reprocess to segment the document first.")
    try:
        from .services.policy_normalization import run_normalization
        result = run_normalization(db, doc, clauses, created_by=user.get("id"), request_id=request_id)
        summary = result.get("summary") or {}
        log.info(
            "request_id=%s policy_pipeline stage=normalize document_id=%s company_id=%s user_id=%s success=true "
            "policy_id=%s policy_version_id=%s benefit_rules=%d exclusions=%d rows_created=%d",
            request_id, doc_id, doc.get("company_id") if doc else None, user.get("id") if user else None,
            result["policy_id"], result["policy_version_id"],
            summary.get("benefit_rules", 0), summary.get("exclusions", 0),
            summary.get("benefit_rules", 0) + summary.get("exclusions", 0) + summary.get("evidence_requirements", 0) + summary.get("conditions", 0),
        )
        return {"policy_id": result["policy_id"], "policy_version_id": result["policy_version_id"], "summary": result["summary"]}
    except ValueError as exc:
        err_str = str(exc)
        log.warning("request_id=%s normalize validation: %s", request_id, err_str)
        raise HTTPException(status_code=400, detail=err_str)
    except Exception as exc:
        err_str = str(exc)
        safe_msg = err_str[:200]
        log.warning(
            "request_id=%s policy_pipeline stage=normalize document_id=%s company_id=%s user_id=%s success=false exc_type=%s exc_msg=%s",
            request_id, doc_id, doc.get("company_id") if doc else None, user.get("id") if user else None,
            type(exc).__name__, safe_msg, exc_info=True,
        )
        if "DatatypeMismatch" in err_str or "auto_generated" in err_str or "boolean" in err_str:
            msg = "Normalization failed because of an invalid policy_versions payload. " + (err_str[:250] or "")
        elif "UndefinedColumn" in err_str or "does not exist" in err_str or "template_source" in err_str or "template_name" in err_str or "is_default_template" in err_str:
            msg = "Normalization failed due to a database schema mismatch (missing optional columns). " + (err_str[:200] or "")
        else:
            msg = f"Normalization failed: {err_str[:500]}"
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error_code": "normalization_failed",
                "message": msg,
                "request_id": request_id,
                "detail": err_str[:500],
            },
        )


# ---------------------------------------------------------------------------
# Company Policies (extracted benefits, linked to policy_documents later)
# ---------------------------------------------------------------------------

@app.get("/api/company-policies/{policy_id}/normalized")
def get_normalized_policy(
    policy_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Get normalized policy version with benefits, exclusions, evidence, conditions, source links."""
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    version = db.get_latest_policy_version(policy_id)
    if not version:
        return {"policy": policy, "version": None, "benefit_rules": [], "exclusions": [], "evidence_requirements": [], "conditions": [], "source_links": []}
    vid = version["id"]
    benefit_rules = db.list_policy_benefit_rules(vid)
    exclusions = db.list_policy_exclusions(vid)
    evidence_requirements = db.list_policy_evidence_requirements(vid)
    conditions = db.list_policy_rule_conditions(vid)
    assignment_applicability = db.list_policy_assignment_applicability(vid)
    family_applicability = db.list_policy_family_applicability(vid)
    source_links = db.list_policy_source_links(vid)
    return {
        "policy": policy,
        "version": version,
        "benefit_rules": benefit_rules,
        "exclusions": exclusions,
        "evidence_requirements": evidence_requirements,
        "conditions": conditions,
        "assignment_applicability": assignment_applicability,
        "family_applicability": family_applicability,
        "source_links": source_links,
    }


@app.patch("/api/company-policies/{policy_id}/benefits/{benefit_rule_id}")
def patch_benefit_rule(
    policy_id: str,
    benefit_rule_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR override: update benefit rule fields."""
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    rule = db.get_policy_benefit_rule(benefit_rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Benefit rule not found")
    version = db.get_policy_version(rule["policy_version_id"])
    if not version or version.get("policy_id") != policy_id:
        raise HTTPException(status_code=404, detail="Benefit rule not found")
    db.update_policy_benefit_rule(
        benefit_rule_id,
        amount_value=body.get("amount_value"),
        amount_unit=body.get("amount_unit"),
        currency=body.get("currency"),
        frequency=body.get("frequency"),
        description=body.get("description"),
        review_status=body.get("review_status"),
        benefit_key=body.get("benefit_key"),
        metadata_json=body.get("metadata_json"),
    )
    updated = db.get_policy_benefit_rule(benefit_rule_id)
    return {"benefit_rule": updated}


@app.patch("/api/company-policies/{policy_id}/versions/latest/status")
def patch_policy_version_status_latest(
    policy_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Update the latest policy version status. Avoids version_id mismatch."""
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    version = db.get_latest_policy_version(policy_id)
    if not version:
        log.warning("request_id=%s patch_version_status_latest policy_id=%s no_version", request_id, policy_id)
        raise HTTPException(status_code=404, detail="No policy version found. Normalize a document first.")
    version_id = version["id"]
    status = body.get("status")
    if status not in ("draft", "review_required", "reviewed", "published", "archived"):
        raise HTTPException(status_code=400, detail="Invalid status")
    try:
        db.update_policy_version_status(version_id, status)
        updated = db.get_policy_version(version_id)
        return {"version": updated}
    except Exception as exc:
        log.warning("request_id=%s patch_version_status_latest failed policy_id=%s exc=%s", request_id, policy_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Status update failed")


@app.post("/api/company-policies/{policy_id}/versions/latest/publish")
def publish_policy_version_latest(
    policy_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Publish the latest policy version. Avoids version_id mismatch."""
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    version = db.get_latest_policy_version(policy_id)
    if not version:
        log.warning("request_id=%s publish_version_latest policy_id=%s no_version", request_id, policy_id)
        raise HTTPException(status_code=404, detail="No policy version found. Normalize a document first.")
    version_id = version["id"]
    company_id = (policy or {}).get("company_id") if policy else None
    try:
        db.archive_other_published_versions(policy_id, version_id)
        db.update_policy_version_status(version_id, "published")
        updated = db.get_policy_version(version_id)
        log.info(
            "publish request_id=%s company_id=%s policy_id=%s version_id=%s status=published visibility=employee_lookup",
            request_id, company_id, policy_id, version_id,
        )
        return {"version": updated}
    except Exception as exc:
        log.warning("request_id=%s publish_version_latest failed policy_id=%s exc=%s", request_id, policy_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Publish failed")


@app.patch("/api/company-policies/{policy_id}/versions/{version_id}/status")
def patch_policy_version_status(
    policy_id: str,
    version_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Update policy version status: draft, review_required, reviewed, published."""
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    version = db.get_policy_version(version_id)
    if not version:
        log.warning("request_id=%s patch_version_status policy_id=%s version_id=%s version_not_found", request_id, policy_id, version_id)
        raise HTTPException(status_code=404, detail="Version not found")
    if version.get("policy_id") != policy_id:
        log.warning("request_id=%s patch_version_status policy_id=%s version_id=%s version_policy_mismatch version_policy=%s", request_id, policy_id, version_id, version.get("policy_id"))
        raise HTTPException(status_code=404, detail="Version not found")
    status = body.get("status")
    if status not in ("draft", "review_required", "reviewed", "published", "archived"):
        raise HTTPException(status_code=400, detail="Invalid status")
    try:
        db.update_policy_version_status(version_id, status)
        updated = db.get_policy_version(version_id)
        return {"version": updated}
    except Exception as exc:
        log.warning("request_id=%s patch_version_status failed policy_id=%s version_id=%s exc=%s", request_id, policy_id, version_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Status update failed")


@app.post("/api/company-policies/{policy_id}/versions/{version_id}/publish")
def publish_policy_version(
    policy_id: str,
    version_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Publish this version and archive any previously published version. Employees see only published."""
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    version = db.get_policy_version(version_id)
    if not version:
        log.warning("request_id=%s publish_version policy_id=%s version_id=%s version_not_found", request_id, policy_id, version_id)
        raise HTTPException(status_code=404, detail="Version not found")
    if version.get("policy_id") != policy_id:
        log.warning("request_id=%s publish_version policy_id=%s version_id=%s version_policy_mismatch", request_id, policy_id, version_id)
        raise HTTPException(status_code=404, detail="Version not found")
    try:
        db.archive_other_published_versions(policy_id, version_id)
        db.update_policy_version_status(version_id, "published")
        updated = db.get_policy_version(version_id)
        policy = db.get_company_policy(policy_id)
        company_id = (policy or {}).get("company_id") if policy else None
        log.info(
            "publish request_id=%s company_id=%s policy_id=%s version_id=%s status=published visibility=employee_lookup",
            request_id, company_id, policy_id, version_id,
        )
        return {"version": updated}
    except Exception as exc:
        log.warning("request_id=%s publish_version failed policy_id=%s version_id=%s exc=%s", request_id, policy_id, version_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Publish failed")


@app.patch("/api/company-policies/{policy_id}/exclusions/{excl_id}")
def patch_exclusion(
    policy_id: str,
    excl_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR override: update exclusion."""
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM policy_exclusions WHERE id = :id"), {"id": excl_id}).fetchone()
    excl = db._row_to_dict(row) if row else None
    if not excl:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    version = db.get_policy_version(excl["policy_version_id"])
    if not version or version.get("policy_id") != policy_id:
        raise HTTPException(status_code=404, detail="Exclusion not found")
    db.update_policy_exclusion(excl_id, description=body.get("description"), review_status=body.get("review_status"))
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM policy_exclusions WHERE id = :id"), {"id": excl_id}).fetchone()
    return {"exclusion": db._row_to_dict(row)}


@app.patch("/api/company-policies/{policy_id}/conditions/{cond_id}")
def patch_condition(
    policy_id: str,
    cond_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR override: update condition."""
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM policy_rule_conditions WHERE id = :id"), {"id": cond_id}).fetchone()
    cond = db._row_to_dict(row) if row else None
    if not cond:
        raise HTTPException(status_code=404, detail="Condition not found")
    version = db.get_policy_version(cond["policy_version_id"])
    if not version or version.get("policy_id") != policy_id:
        raise HTTPException(status_code=404, detail="Condition not found")
    db.update_policy_rule_condition(cond_id, condition_value_json=body.get("condition_value_json"), review_status=body.get("review_status"))
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM policy_rule_conditions WHERE id = :id"), {"id": cond_id}).fetchone()
    d = db._row_to_dict(row)
    if d and d.get("condition_value_json") and isinstance(d["condition_value_json"], str):
        try:
            d["condition_value_json"] = json.loads(d["condition_value_json"])
        except Exception:
            pass
    return {"condition": d}


@app.get("/api/company-policies/latest")
def get_latest_company_policy(
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    profile = _require_company_for_user(user)
    policy = db.get_latest_company_policy(profile["company_id"])
    if not policy:
        return {"policy": None, "benefits": [], "company_name": None}
    benefits = db.list_policy_benefits(policy["id"])
    company = db.get_company(profile["company_id"])
    company_name = company.get("name") if company else None
    return {"policy": policy, "benefits": benefits, "company_name": company_name}


@app.get("/api/company-policies/{policy_id}")
def get_company_policy(
    policy_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    benefits = db.list_policy_benefits(policy_id)
    return {"policy": policy, "benefits": benefits}


def _download_url_error_response(
    error_code: str,
    message: str,
    status: int = 500,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Return structured JSON error for download-url."""
    content: Dict[str, Any] = {"ok": False, "error_code": error_code, "message": message}
    if request_id:
        content["request_id"] = request_id
    return JSONResponse(status_code=status, content=content)


def _map_download_storage_exception(exc: Exception) -> tuple[str, str]:
    """Map storage exception to (error_code, user_safe_message) for download-url."""
    msg = str(exc).lower()
    status = None
    if hasattr(exc, "args") and exc.args and isinstance(exc.args[0], dict):
        d = exc.args[0]
        if isinstance(d.get("statusCode"), int):
            status = d["statusCode"]
    if status == 404 or "not found" in msg or "does not exist" in msg or "object not found" in msg:
        return (POLICY_FILE_MISSING, "Policy file not found in storage.")
    if status == 400 or "bad request" in msg or "invalid" in msg and "path" in msg:
        return (POLICY_FILE_PATH_INVALID, "Invalid policy file path.")
    if "sign" in msg or "signed" in msg:
        return (POLICY_FILE_SIGN_FAILED, "Failed to create signed download URL.")
    return (POLICY_STORAGE_UNEXPECTED_ERROR, "Policy download failed. Please try again.")


@app.get("/api/company-policies/{policy_id}/download-url")
def get_company_policy_download_url(
    policy_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    request_id = getattr(req.state, "request_id", None)
    profile = _require_company_for_user(user)
    company_id = profile.get("company_id", "")

    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != company_id:
        log.warning(
            "request_id=%s download-url policy_id=%s company_id=%s policy_not_found",
            request_id, policy_id, company_id[:8] + "…" if company_id and len(company_id) > 8 else company_id,
        )
        return _download_url_error_response(
            POLICY_POLICY_NOT_FOUND,
            "Policy not found.",
            404,
            request_id=request_id,
        )

    raw_file_url = policy.get("file_url") or ""
    raw_storage_path = policy.get("storage_path") or ""
    object_key = resolve_policy_storage_object_key(raw_file_url or raw_storage_path)

    # Fallback: if company_policies has no file, use source policy_document from latest policy_version
    if not object_key:
        versions = db.list_policy_versions(policy_id)
        for ver in versions:
            source_doc_id = ver.get("source_policy_document_id")
            if not source_doc_id:
                continue
            doc = db.get_policy_document(source_doc_id)
            if not doc:
                continue
            doc_storage = (doc.get("storage_path") or "").strip()
            if doc_storage:
                object_key = resolve_policy_storage_object_key(doc_storage)
                if object_key:
                    log.info(
                        "request_id=%s download-url policy_id=%s fallback source_doc=%s object_key=%s",
                        request_id, policy_id, source_doc_id[:8] + "…", object_key[:60] + "…" if len(object_key) > 60 else object_key,
                    )
                    break

    log.info(
        "request_id=%s download-url policy_id=%s company_id=%s raw_file_url=%s raw_storage_path=%s object_key=%s bucket=%s",
        request_id,
        policy_id,
        company_id[:8] + "…" if company_id and len(company_id) > 8 else company_id,
        (raw_file_url[:80] + "…" if raw_file_url and len(raw_file_url) > 80 else raw_file_url) or "(empty)",
        (raw_storage_path[:80] + "…" if raw_storage_path and len(raw_storage_path) > 80 else raw_storage_path) or "(empty)",
        (object_key[:80] + "…" if object_key and len(object_key) > 80 else object_key) or "(empty)",
        BUCKET_HR_POLICIES,
    )

    if not object_key:
        # No downloadable file: return 200 with ok false so UI shows muted message, not 404/500
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "reason": "No downloadable file available for this policy version.",
            },
        )

    try:
        supabase = get_supabase_admin_client()
        signed = supabase.storage.from_(BUCKET_HR_POLICIES).create_signed_url(object_key, 3600)
        url = signed.get("signedURL") or signed.get("signed_url") or ""
        if not url:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "reason": "No downloadable file available for this policy version."},
            )
        return JSONResponse(status_code=200, content={"ok": True, "url": url})
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)[:300] if str(exc) else "(no message)"
        log.warning(
            "request_id=%s download-url policy_id=%s exc_type=%s exc_msg=%s",
            request_id, policy_id, exc_type, exc_msg,
        )
        return JSONResponse(
            status_code=200,
            content={"ok": False, "reason": "No downloadable file available for this policy version."},
        )


@app.post("/api/company-policies/upload")
async def upload_company_policy(
    req: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    request_id = getattr(req.state, "request_id", None) if req else None
    profile = _require_company_for_user(user)
    filename = file.filename or "policy"
    ext = filename.split(".")[-1].lower()
    if ext not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="Only .docx or .pdf supported")
    policy_id = str(uuid.uuid4())
    path = f"companies/{profile['company_id']}/policies/{policy_id}/{filename}"
    content = await file.read()
    try:
        supabase = get_supabase_admin_client()
        supabase.storage.from_(BUCKET_HR_POLICIES).upload(
            path,
            content,
            {
                "content-type": file.content_type or "application/octet-stream",
                "upsert": "true",
            },
        )
    except Exception as exc:
        log.error("request_id=%s company_policy_upload storage failed: %s", request_id or "?", exc, exc_info=True)
        detail = _sanitize_storage_error(exc, BUCKET_HR_POLICIES)
        raise HTTPException(status_code=500, detail=detail)
    db.create_company_policy(
        policy_id=policy_id,
        company_id=profile["company_id"],
        title=title,
        version=version,
        effective_date=effective_date,
        file_url=path,
        file_type=ext,
        created_by=user.get("id"),
    )
    policy = db.get_company_policy(policy_id)
    return {"policy": policy}


@app.put("/api/company-policies/{policy_id}/benefits")
def update_company_policy_benefits(
    policy_id: str,
    payload: PolicyBenefitsUpsert,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    db.replace_policy_benefits(
        policy_id,
        [b.model_dump(mode="json") for b in payload.benefits],
        updated_by=user.get("id"),
    )
    benefits = db.list_policy_benefits(policy_id)
    return {"policy": policy, "benefits": benefits}


@app.post("/api/policies/{policy_id}/extract")
def extract_company_policy(
    policy_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    request_id = getattr(req.state, "request_id", None)
    policy = db.get_company_policy(policy_id)
    _require_policy_access(user, policy)
    file_path = policy.get("file_url") or ""
    object_key = normalize_policy_storage_object_key(file_path)
    log.info("request_id=%s extract bucket=%s object_key=%s", request_id, BUCKET_HR_POLICIES, object_key)
    try:
        supabase = get_supabase_admin_client()
        data = supabase.storage.from_(BUCKET_HR_POLICIES).download(object_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_sanitize_storage_error(exc, BUCKET_HR_POLICIES))
    try:
        extraction = extract_policy_from_bytes(data, policy.get("file_type") or "docx")
        meta = extraction.get("policy_meta", {})
        db.update_company_policy_meta(
            policy_id,
            title=meta.get("title") if not policy.get("title") else None,
            version=meta.get("version") if not policy.get("version") else None,
            effective_date=meta.get("effective_date") if not policy.get("effective_date") else None,
        )
        db.replace_policy_benefits(policy_id, extraction.get("benefits", []), updated_by=user.get("id"))
        db.update_company_policy_status(policy_id, "extracted", extracted_at=extraction.get("extracted_at"))
    except Exception as exc:
        db.update_company_policy_status(policy_id, "failed", extracted_at=None)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(exc)}")
    policy = db.get_company_policy(policy_id)
    benefits = db.list_policy_benefits(policy_id)
    return {"policy": policy, "benefits": benefits}


@app.get("/api/hr/policies/{policy_id}")
def get_hr_policy_by_id(
    policy_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    policy = db.get_hr_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.put("/api/hr/policies/{policy_id}")
def update_hr_policy(
    policy_id: str,
    body: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    existing = db.get_hr_policy(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")
    body["policyId"] = policy_id
    version = existing.get("version", 1)
    if body.get("status") == "published" and existing.get("_meta", {}).get("status") != "published":
        version = version + 1
    body["version"] = body.get("version", version)
    db.update_hr_policy(policy_id, body)
    return {"policyId": policy_id, "policy": body}


@app.delete("/api/hr/policies/{policy_id}")
def delete_hr_policy(
    policy_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    ok = db.delete_hr_policy(policy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"success": True}


# Employee: get applicable policy and wizard criteria for auto-fill
@app.get("/api/employee/policy/applicable")
def get_applicable_employee_policy(
    assignmentId: Optional[str] = Query(None, alias="assignmentId"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Return applicable HR policy for the employee's assignment, plus wizard criteria for auto-fill."""
    from .app.services.hr_policy_resolver import resolve_applicable_benefits, policy_to_wizard_criteria

    assignment = None
    profile = None
    if assignmentId:
        assignment = db.get_assignment_by_id(assignmentId)
        if assignment and assignment.get("employee_user_id") == user.get("id"):
            profile = db.get_employee_profile(assignmentId)
    if not assignment:
        res = db.get_assignment_for_employee(user.get("id", ""))
        if res:
            assignment = res
            assignmentId = res["id"]
            profile = db.get_employee_profile(res["id"])

    if not assignment:
        return {"policy": None, "allowedBenefits": [], "wizardCriteria": {}, "message": "No assignment"}

    profile = profile or {}
    mp = profile.get("movePlan") or {}
    dest = mp.get("destination", "Singapore")
    country_code = None
    if isinstance(dest, str) and "," in dest:
        parts = dest.split(",")
        if len(parts) >= 2:
            country_code = parts[-1].strip()[:2].upper() if parts[-1].strip() else "SG"
    if not country_code and "Singapore" in str(dest):
        country_code = "SG"
    employee_band = profile.get("primaryApplicant", {}).get("employer", {}).get("jobLevel") or "Band2"
    if "L" in str(employee_band) and "Band" not in str(employee_band):
        employee_band = f"Band{employee_band.replace('L', '')}" if employee_band.replace("L", "").isdigit() else "Band2"
    assignment_type = "Long-Term"
    policy = db.get_published_hr_policy_for_employee(
        employee_band=employee_band,
        assignment_type=assignment_type,
        country_code=country_code,
    )
    if not policy:
        return {"policy": None, "allowedBenefits": [], "wizardCriteria": {}, "message": "No matching published policy"}

    allowed = resolve_applicable_benefits(policy, employee_band, assignment_type, country_code)
    wizard_criteria = policy_to_wizard_criteria(policy, employee_band, assignment_type, country_code, profile)
    return {
        "policy": {
            "policyId": policy.get("policyId"),
            "policyName": policy.get("policyName"),
            "effectiveDate": policy.get("effectiveDate"),
            "employeeBands": policy.get("employeeBands"),
            "assignmentTypes": policy.get("assignmentTypes"),
        },
        "allowedBenefits": allowed,
        "wizardCriteria": wizard_criteria,
        "employeeBand": employee_band,
        "assignmentType": assignment_type,
    }


@app.get("/api/hr/policy")
def get_hr_policy(caseId: str = Query(...), user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    assignment = db.get_assignment_by_id(caseId)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    profile = db.get_employee_profile(caseId)
    if not profile:
        profile = RelocationProfile(userId=caseId).model_dump()

    policy = policy_engine.load_policy()
    exceptions = db.list_policy_exceptions(caseId)
    return policy_engine.build_policy_response(caseId, profile, policy, exceptions)


@app.post("/api/hr/cases/{case_id}/policy/exceptions")
def create_policy_exception(
    case_id: str,
    request: PolicyExceptionRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    assignment = db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not request.category:
        raise HTTPException(status_code=400, detail="Category required")
    exception_id = str(uuid.uuid4())
    db.create_policy_exception(
        exception_id,
        case_id,
        request.category,
        "PENDING",
        request.reason,
        request.amount,
        effective["id"],
    )
    return {"success": True, "exceptionId": exception_id}


@app.get("/api/hr/cases/{case_id}/compliance")
def get_case_compliance(case_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    assignment = db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    profile = db.get_employee_profile(case_id)
    if not profile:
        profile = RelocationProfile(userId=case_id).model_dump()

    cached = db.get_latest_compliance_run(case_id)
    if cached:
        return cached

    policy = policy_engine.load_policy()
    exceptions = db.list_policy_exceptions(case_id)
    spend = policy_engine.compute_spend(case_id, profile, policy)
    report = policy_engine.build_compliance_report(case_id, profile, policy, spend, exceptions, assignment.get("status"))
    return report


@app.post("/api/hr/cases/{case_id}/compliance/run")
def run_case_compliance(case_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    assignment = db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    profile = db.get_employee_profile(case_id)
    if not profile:
        profile = RelocationProfile(userId=case_id).model_dump()

    policy = policy_engine.load_policy()
    exceptions = db.list_policy_exceptions(case_id)
    spend = policy_engine.compute_spend(case_id, profile, policy)
    report = policy_engine.build_compliance_report(case_id, profile, policy, spend, exceptions, assignment.get("status"))
    db.save_compliance_run(str(uuid.uuid4()), case_id, report)
    return report


@app.post("/api/hr/cases/{case_id}/compliance/actions")
def record_compliance_action(
    case_id: str,
    request: ComplianceActionRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    _deny_if_impersonating(user)
    assignment = db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not request.checkId or not request.actionType:
        raise HTTPException(status_code=400, detail="Missing action details")
    db.create_compliance_action(
        str(uuid.uuid4()),
        case_id,
        request.checkId,
        request.actionType,
        request.notes,
        user["id"],
    )
    return {"success": True}


# ---------------------------------------------------------------------------
# HR Command Center (Portfolio & Risk Dashboard)
# ---------------------------------------------------------------------------
class CommandCenterKPIs(BaseModel):
    activeCases: int
    atRiskCount: int
    attentionNeededCount: int
    overdueTasksCount: int
    avgVisaDurationDays: Optional[float] = None
    budgetOverrunsCount: int
    actionRequiredCount: int
    departingSoonCount: int
    completedCount: int


class CommandCenterCaseRow(BaseModel):
    id: str
    employeeIdentifier: str
    destCountry: Optional[str] = None
    status: str
    riskStatus: str
    tasksDonePercent: int
    budgetLimit: Optional[float] = None
    budgetEstimated: Optional[float] = None
    nextDeadline: Optional[str] = None


class CommandCenterCaseDetail(BaseModel):
    id: str
    employeeIdentifier: str
    destCountry: Optional[str] = None
    status: str
    riskStatus: str
    budgetLimit: Optional[float] = None
    budgetEstimated: Optional[float] = None
    expectedStartDate: Optional[str] = None
    tasksTotal: int
    tasksDone: int
    tasksOverdue: int
    phases: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []


def _effective_hr_user(user: Dict[str, Any]) -> Optional[str]:
    if user.get("is_admin") and not user.get("impersonation"):
        return None
    return user.get("id")


def _command_center_scope(user: Dict[str, Any]) -> tuple:
    """Return (company_id, hr_user_id) for command center queries. Prefer company scope."""
    effective = _effective_user(user, UserRole.HR)
    company_id = _get_hr_company_id(effective)
    hr_user_id = _effective_hr_user(user)
    if company_id:
        return (company_id, None)
    return (None, hr_user_id)


@app.get("/api/hr/command-center/kpis", response_model=CommandCenterKPIs)
def get_command_center_kpis(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    company_id, hr_user_id = _command_center_scope(user)
    kpis = db.get_command_center_kpis(company_id=company_id, hr_user_id=hr_user_id)
    return CommandCenterKPIs(**kpis)


@app.get("/api/hr/command-center/cases", response_model=List[CommandCenterCaseRow])
def list_command_center_cases(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    risk_filter: Optional[str] = Query(None, pattern="^(green|yellow|red)$"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    company_id, hr_user_id = _command_center_scope(user)
    rows = db.list_command_center_cases(
        company_id=company_id, hr_user_id=hr_user_id, page=page, limit=limit, risk_filter=risk_filter
    )
    return [CommandCenterCaseRow(**r) for r in rows]


@app.get("/api/hr/command-center/cases/{assignment_id}", response_model=CommandCenterCaseDetail)
def get_command_center_case_detail(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    company_id, hr_user_id = _command_center_scope(user)
    detail = db.get_command_center_case_detail(
        assignment_id=assignment_id, company_id=company_id, hr_user_id=hr_user_id
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Case not found or not visible")
    return CommandCenterCaseDetail(**detail)


def _build_next_actions(profile: Dict[str, Any], completion_state: Dict[str, Any]) -> List[str]:
    """Build list of next actions for the user."""
    actions = []
    
    # Check missing documents
    if completion_state.get("immigrationReadiness"):
        missing_docs = completion_state["immigrationReadiness"].missingDocs
        for doc in missing_docs[:3]:  # Top 3
            actions.append(f"Obtain {doc}")
    
    # Check incomplete areas
    completeness = completion_state.get("completeness", {})
    
    if not completeness.get("housing"):
        actions.append("Complete housing preferences")
    
    if not completeness.get("schools"):
        actions.append("Complete school preferences")
    
    if not completeness.get("movers"):
        actions.append("Complete moving preferences")
    
    # Add some standard actions
    if profile.get("movePlan", {}).get("housing", {}).get("budgetMonthlySGD") == "unknown":
        actions.append("Decide on housing budget range")
    
    if profile.get("movePlan", {}).get("schooling", {}).get("curriculumPreference") == "unknown":
        actions.append("Research school curriculum options")
    
    # Limit to top 5
    return actions[:5] if actions else ["Complete your relocation profile"]


def _build_employee_journey_payload(
    assignment: Dict[str, Any],
) -> EmployeeJourneyNextQuestion:
    assignment_id = assignment["id"]
    normalized_status = normalize_status(assignment.get("status"))
    profile = db.get_employee_profile(assignment_id)
    if not profile:
        profile = RelocationProfile(userId=assignment_id).model_dump()
        db.save_employee_profile(assignment_id, profile)
    else:
        # Coerce empty strings to None to avoid date/enum parsing errors.
        profile = _normalize_profile_values(profile)
        # Normalize profile fields before validation (legacy wizard can store Title Case).
        marital = profile.get("maritalStatus")
        if isinstance(marital, str):
            normalized = marital.strip().lower()
            allowed = {"married", "single", "divorced", "widowed"}
            profile["maritalStatus"] = normalized if normalized in allowed else marital
    answers = db.get_employee_answers(assignment_id)
    answered_question_ids = set(ans["question_id"] for ans in answers)

    completion_state = orchestrator.compute_completion_state(
        profile,
        total_questions=len(orchestrator.all_questions),
    )
    missing_items = []
    for err in completion_state.get("validationErrors", []):
        message = getattr(err, "message", None)
        if not message and isinstance(err, dict):
            message = err.get("message")
        if message:
            missing_items.append(message)

    response = orchestrator.get_next_question(profile, answered_question_ids)

    if normalized_status in [
        AssignmentStatus.SUBMITTED.value,
        AssignmentStatus.APPROVED.value,
        AssignmentStatus.REJECTED.value,
        AssignmentStatus.CLOSED.value,
    ]:
        response.question = None
        response.isComplete = True

    try:
        parsed_profile = RelocationProfile(**profile)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Invalid employee profile for assignment %s: %s", assignment_id, exc)
        parsed_profile = RelocationProfile(userId=assignment_id)

    return EmployeeJourneyNextQuestion(
        question=response.question,
        isComplete=response.isComplete,
        progress=response.progress,
        completeness=completion_state.get("profileCompleteness", 0),
        missingItems=missing_items,
        assignmentStatus=AssignmentStatus(normalize_status(assignment["status"])),
        hrNotes=assignment.get("hr_notes"),
        profile=parsed_profile,
    )


def _normalize_profile_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize_profile_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_profile_values(v) for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def _build_timeline(profile: Dict[str, Any], completion_state: Dict[str, Any]) -> List[TimelinePhase]:
    """Build timeline with phases and tasks."""
    timeline = []
    
    # Phase 1: Visa & Eligibility
    visa_tasks = []
    docs = profile.get("complianceDocs", {})
    
    if docs.get("hasPassportScans"):
        visa_tasks.append(TimelineTask(title="Passport scans ready", status="done"))
    else:
        visa_tasks.append(TimelineTask(title="Scan all passports", status="todo"))
    
    if docs.get("hasEmploymentLetter"):
        visa_tasks.append(TimelineTask(title="Employment letter obtained", status="done"))
    else:
        visa_tasks.append(TimelineTask(title="Request employment letter from Norwegian Investment", status="todo"))
    
    visa_tasks.append(TimelineTask(title="Submit work permit application", status="todo"))
    visa_tasks.append(TimelineTask(title="Apply for dependent passes", status="todo"))
    
    timeline.append(TimelinePhase(phase="Visa & Eligibility", tasks=visa_tasks))
    
    # Phase 2: Documents
    doc_tasks = []
    if docs.get("hasMarriageCertificate"):
        doc_tasks.append(TimelineTask(title="Marriage certificate ready", status="done"))
    else:
        doc_tasks.append(TimelineTask(title="Obtain marriage certificate", status="todo"))
    
    if docs.get("hasBirthCertificates"):
        doc_tasks.append(TimelineTask(title="Birth certificates ready", status="done"))
    else:
        doc_tasks.append(TimelineTask(title="Obtain children's birth certificates", status="todo"))
    
    timeline.append(TimelinePhase(phase="Documents", tasks=doc_tasks))
    
    # Phase 3: Housing
    housing_complete = completion_state.get("completeness", {}).get("housing", False)
    housing_tasks = []
    
    if housing_complete:
        housing_tasks.append(TimelineTask(title="Housing preferences defined", status="done"))
        housing_tasks.append(TimelineTask(title="Review temporary housing options", status="in_progress"))
    else:
        housing_tasks.append(TimelineTask(title="Define housing preferences", status="todo"))
    
    housing_tasks.append(TimelineTask(title="Book temporary accommodation", status="todo"))
    housing_tasks.append(TimelineTask(title="Search for permanent housing", status="todo"))
    
    timeline.append(TimelinePhase(phase="Housing", tasks=housing_tasks))
    
    # Phase 4: Schools
    schools_complete = completion_state.get("completeness", {}).get("schools", False)
    school_tasks = []
    
    if schools_complete:
        school_tasks.append(TimelineTask(title="School preferences defined", status="done"))
        school_tasks.append(TimelineTask(title="Review school options", status="in_progress"))
    else:
        school_tasks.append(TimelineTask(title="Define school preferences", status="todo"))
    
    school_tasks.append(TimelineTask(title="Submit school applications", status="todo"))
    school_tasks.append(TimelineTask(title="Arrange school visits", status="todo"))
    
    timeline.append(TimelinePhase(phase="Schools", tasks=school_tasks))
    
    # Phase 5: Moving Logistics
    movers_complete = completion_state.get("completeness", {}).get("movers", False)
    moving_tasks = []
    
    if movers_complete:
        moving_tasks.append(TimelineTask(title="Moving requirements defined", status="done"))
        moving_tasks.append(TimelineTask(title="Request quotes from movers", status="in_progress"))
    else:
        moving_tasks.append(TimelineTask(title="Define moving requirements", status="todo"))
    
    moving_tasks.append(TimelineTask(title="Select moving company", status="todo"))
    moving_tasks.append(TimelineTask(title="Schedule packing and shipment", status="todo"))
    
    timeline.append(TimelinePhase(phase="Moving Logistics", tasks=moving_tasks))
    
    return timeline


def _determine_overall_status(completion_state: Dict[str, Any]) -> OverallStatus:
    """Determine overall relocation status."""
    readiness = completion_state.get("immigrationReadiness")
    completeness = completion_state.get("profileCompleteness", 0)
    
    if not readiness:
        return OverallStatus.AT_RISK
    
    # Check readiness score and completeness
    if readiness.score >= 70 and completeness >= 60:
        return OverallStatus.ON_TRACK
    else:
        return OverallStatus.AT_RISK


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
