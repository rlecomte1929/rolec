"""
FastAPI main application for ReloPass backend.
"""
import logging
import time

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Header, Depends, Query, UploadFile, File, Request, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import uuid
from datetime import datetime
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
    AssignCaseResponse, CreateCaseResponse, AssignmentSummary, AssignmentDetail,
    EmployeeJourneyRequest, EmployeeJourneyNextQuestion, HRAssignmentDecision,
    UpdateAssignmentIdentifierRequest, ClaimAssignmentRequest,
    UpdateProfilePhotoRequest, PolicyExceptionRequest, ComplianceActionRequest,
    AddEvidenceRequest, AddEvidenceResponse,
)
from .services.dossier import evaluate_applies_if, validate_answer, fetch_search_results, build_suggested_questions
from .services.guidance_pack_service import generate_guidance_pack
from .services.policy_adapter import normalize_policy_caps
from .services.policy_extractor import extract_policy_from_bytes
from .app.services.timeline_service import compute_default_milestones
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
from .routes import relocation as relocation_router
from .routes import compat as compat_router
from .routes import relocation_classify as relocation_classify_router
from .routes import resources as resources_router
from .app.recommendations.router import router as recommendations_router
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

log.info("DB engine: %s | host: %s", _db_scheme, _db_host)

if any(p in _db_url for p in ["YOUR_PASSWORD", "YOUR_HOST", "<password>", "placeholder"]):
    log.error("DATABASE_URL contains placeholder text! Fix it in Render env vars.")
    raise RuntimeError("DATABASE_URL contains placeholder text — refusing to start.")

if _db_scheme == "sqlite":
    log.warning("Running with SQLite — data will NOT persist across Render redeploys!")
else:
    log.info("Running with PostgreSQL — data persists across redeploys.")

app = FastAPI(title="ReloPass API", version="1.0.0")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

app.include_router(compat_router.router)
app.include_router(cases_router.router)
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
        existing = db.get_user_by_email(email)
        if existing:
            return existing["id"]
        created = db.create_user(
            user_id=user_id,
            username=None,
            email=email,
            password_hash=demo_password,
            role=role,
            name=name,
        )
        return user_id if created else db.get_user_by_email(email)["id"]

    hr_user_id = ensure_user(
        user_id="demo-hr-001",
        email="hr.demo@relopass.local",
        role="HR",
        name="HR Demo",
    )

    employees = [
        ("demo-emp-001", "sarah.jenkins@relopass.local", "Sarah Jenkins"),
        ("demo-emp-002", "mark.thompson@relopass.local", "Mark Thompson"),
        ("demo-emp-003", "demo@relopass.com", "Demo Employee"),
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
    db.ensure_profile_record(hr_user_id, "hr.demo@relopass.local", "HR", "HR Demo", company_id)
    db.ensure_profile_record(admin_user_id, "admin@relopass.com", "ADMIN", "ReloPass Admin", None)
    for emp_id, emp_email, emp_name in employees:
        db.ensure_profile_record(emp_id, emp_email, "EMPLOYEE", emp_name, company_id)

    db.create_hr_user("hr-001", company_id, hr_user_id, {"can_manage_policy": True})
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

    for scenario in scenarios:
        if not db.get_assignment_by_id(scenario["assignment_id"]):
            case_profile = {
                "origin": scenario["profile"]["movePlan"]["origin"],
                "destination": scenario["profile"]["movePlan"]["destination"],
            }
            if not db.get_case_by_id(scenario["case_id"]):
                db.create_case(scenario["case_id"], hr_user_id, case_profile)
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


# Only run legacy demo seed (relocation_cases with string IDs) on SQLite.
# Production Supabase uses UUID for relocation_cases.id; seeding would crash.
if _db_scheme == "sqlite":
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
    visible = False
    if is_employee and emp_id == effective["id"]:
        visible = True
    if is_hr and (effective.get("is_admin") or hr_id == effective["id"]):
        visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Assignment not found or not visible under RLS")
    return {"assignment": assignment, "effective_user": effective}


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ReloPass API"}


@app.post("/api/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest):
    """Register a new user with username or email and role."""
    try:
        username = request.username.strip() if request.username else None
        email_raw = request.email.strip() if request.email else None
        email = email_raw.lower() if email_raw else None

        if not username and not email:
            raise HTTPException(status_code=400, detail="Provide a username or email")

        if username:
            if not re.match(r"^[A-Za-z0-9_]{3,30}$", username):
                raise HTTPException(status_code=400, detail="Username must be 3-30 chars, alphanumeric or underscore")
            if db.get_user_by_username(username):
                raise HTTPException(status_code=400, detail="Username already in use")

        if email:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                raise HTTPException(status_code=400, detail="Invalid email format")
            if db.get_user_by_email(email):
                raise HTTPException(status_code=400, detail="Email already in use")

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
            raise HTTPException(status_code=400, detail="Unable to create user (username or email may already exist)")

        token = str(uuid.uuid4())
        db.create_session(token, user_id)
        db.ensure_profile_record(
            user_id=user_id,
            email=email,
            role=role.value,
            full_name=request.name,
            company_id=None,
        )

        log.info("auth_register success user_id=%s username=%s", user_id[:8], username)
        return LoginResponse(
            token=token,
            user=UserResponse(
                id=user_id,
                username=username,
                email=email,
                role=role,
                name=request.name,
                company=None,
            )
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


@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """Login with username or email + password."""
    identifier = (request.identifier or "").strip()
    if not identifier:
        log.warning("auth_login fail identifier_empty")
        raise HTTPException(status_code=401, detail="Enter your username or email")
    user = db.get_user_by_identifier(identifier)
    if not user:
        log.warning("auth_login fail user_not_found identifier=%s", identifier[:3] + "***")
        raise HTTPException(status_code=401, detail="Invalid username or email. Check spelling or create an account.")

    if not user.get("password_hash"):
        log.warning("auth_login fail no_password user_id=%s", user.get("id", "")[:8])
        raise HTTPException(status_code=401, detail="Invalid credentials")

    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    if not pwd_context.verify(request.password, user["password_hash"]):
        log.warning("auth_login fail wrong_password user_id=%s", user.get("id", "")[:8])
        raise HTTPException(status_code=401, detail="Incorrect password. Try again or reset.")

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

    log.info("auth_login success user_id=%s", user["id"][:8])

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            username=user.get("username"),
            email=user.get("email"),
            role=effective_role,
            name=user.get("name"),
            company=profile.get("company_id") if profile else user.get("company"),
        )
    )


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
    items = db.list_companies(q)
    db.log_audit(user["id"], "READ", "company", None, None, {"query": q})
    return {"companies": items}


@app.get("/api/admin/companies/{company_id}")
def get_company_detail(company_id: str, user: Dict[str, Any] = Depends(require_admin)):
    company = db.get_company(company_id)
    hr_users = db.list_hr_users(company_id)
    employees = db.list_employees(company_id)
    policies = db.list_hr_policies_by_company(company_id)
    db.log_audit(user["id"], "READ", "company", company_id, None, {"detail": True})
    return {
        "company": company,
        "hr_users": hr_users,
        "employees": employees,
        "policies": policies,
    }


@app.get("/api/admin/users")
def list_users(q: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_admin)):
    items = db.list_profiles(q)
    db.log_audit(user["id"], "READ", "profile", None, None, {"query": q})
    return {"profiles": items}


@app.get("/api/admin/employees")
def list_employees(company_id: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_admin)):
    items = db.list_employees(company_id)
    db.log_audit(user["id"], "READ", "employee", None, None, {"company_id": company_id})
    return {"employees": items}


@app.get("/api/admin/hr-users")
def list_hr_users(company_id: Optional[str] = Query(None), user: Dict[str, Any] = Depends(require_admin)):
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


@app.get("/api/admin/support-cases")
def list_support_cases(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_admin),
):
    items = db.list_support_cases(status=status, severity=severity, company_id=company_id)
    db.log_audit(user["id"], "READ", "support_case", None, None, {"status": status, "severity": severity, "company_id": company_id})
    return {"support_cases": items}


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
        assignment = db.get_assignment_for_employee(user["id"], request_id=request.state.request_id)
        if not assignment:
            ident = (user.get("email") or user.get("username") or "").strip().lower()
            if ident:
                assignment = db.get_unassigned_assignment_by_identifier(
                    ident, request_id=request.state.request_id
                )
                if assignment:
                    db.attach_employee_to_assignment(
                        assignment["id"], user["id"], request_id=request.state.request_id
                    )
                    assignment = db.get_assignment_by_id(assignment["id"], request_id=request.state.request_id)
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
    case_id = str(uuid.uuid4())
    profile = RelocationProfile(userId=effective["id"]).model_dump()
    db.create_case(case_id, effective["id"], profile)
    return CreateCaseResponse(caseId=case_id)


@app.get("/api/hr/company-profile")
def get_company_profile(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    effective = _effective_user(user, UserRole.HR)
    company = db.get_company_for_user(effective["id"])
    return {"company": company}


@app.get("/api/company")
def get_current_user_company(user: Dict[str, Any] = Depends(get_current_user)):
    """Return the authenticated user's company (for header branding). Available to HR and Employee."""
    company = db.get_company_for_user(user["id"])
    return {"company": company}


@app.post("/api/hr/company-profile")
def save_company_profile(request: CompanyProfileRequest, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.HR)
    profile = db.get_profile_record(effective["id"])
    company_id = profile.get("company_id") if profile else None
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
    return {"ok": True, "company_id": company_id}


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
            file_options={"content-type": content_type or "image/png", "upsert": True},
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

        employee_identifier = request.employeeIdentifier.strip()
        if not employee_identifier:
            raise HTTPException(status_code=400, detail="Employee identifier required")

        fn = getattr(request, "employeeFirstName", None) or getattr(request, "employee_first_name", None)
        ln = getattr(request, "employeeLastName", None) or getattr(request, "employee_last_name", None)
        employee_first_name = (fn or "").strip() or None
        employee_last_name = (ln or "").strip() or None
        display_name_from_hr = (
            " ".join(filter(None, [employee_first_name, employee_last_name])).strip() or None
        )
        fallback_name = employee_identifier.split("@")[0] if "@" in employee_identifier else employee_identifier

        employee_user = db.get_user_by_identifier(employee_identifier)
        created_new_employee = False
        if not employee_user and "@" in employee_identifier:
            # Auto-register employee user with a temporary password
            from passlib.context import CryptContext

            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
            temp_password = "Passw0rd!"
            employee_user_id = str(uuid.uuid4())
            initial_name = display_name_from_hr or fallback_name
            created = db.create_user(
                user_id=employee_user_id,
                username=None,
                email=employee_identifier.lower(),
                password_hash=pwd_context.hash(temp_password),
                role=UserRole.EMPLOYEE.value,
                name=initial_name,
            )
            if created:
                employee_user = db.get_user_by_id(employee_user_id)
                db.ensure_profile_record(
                    employee_user_id,
                    employee_identifier,
                    UserRole.EMPLOYEE.value,
                    initial_name,
                    None,
                )
                created_new_employee = True
        assignment_id = str(uuid.uuid4())
        invite_token = None

        # New assignments created by HR are immediately in the 'assigned' state.
        assert_canonical_status(AssignmentStatus.ASSIGNED.value)
        with timed("db.create_assignment", request_id):
            db.create_assignment(
                assignment_id=assignment_id,
                case_id=case_id,
                hr_user_id=effective["id"],
                employee_user_id=employee_user["id"] if employee_user else None,
                employee_identifier=employee_identifier,
                status=AssignmentStatus.ASSIGNED.value,
                request_id=request_id,
                employee_first_name=employee_first_name,
                employee_last_name=employee_last_name,
            )
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
                payload={"employee_identifier": employee_identifier},
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

        if not employee_user:
            invite_token = str(uuid.uuid4())
            try:
                db.create_assignment_invite(
                    invite_id=str(uuid.uuid4()),
                    case_id=case_id,
                    hr_user_id=effective["id"],
                    employee_identifier=employee_identifier,
                    token=invite_token,
                )
            except Exception as exc:
                log.warning(
                    "create_assignment_invite skipped assignment_id=%s case_id=%s error=%s",
                    assignment_id, case_id, str(exc),
                )
                invite_token = None

        # Prefill invitation message in Messages
        invite_line = (
            f"Invitation token: {invite_token}"
            if invite_token
            else "You can claim your assignment after signing in."
        )
        temp_line = "Temporary password: Passw0rd!\n\n" if created_new_employee else ""
        message_body = (
            f"Hello,\n\n"
            f"You have been registered for a relocation case on ReloPass.\n\n"
            f"Assignment ID: {assignment_id}\n"
            f"Employee identifier: {employee_identifier}\n"
            f"{invite_line}\n\n"
            f"Login at https://relopass.com/auth?mode=login\n"
            f"{temp_line}"
            f"Once logged in, go to My Case to start your intake.\n"
        )
        try:
            db.create_message(
                message_id=str(uuid.uuid4()),
                assignment_id=assignment_id,
                hr_user_id=effective["id"],
                employee_identifier=employee_identifier,
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
    assignment = db.get_assignment_for_employee(effective["id"], request_id=request.state.request_id)
    if not assignment:
        identifier = effective.get("username") or effective.get("email")
        if identifier:
            assignment = db.get_unassigned_assignment_by_identifier(
                identifier, request_id=request.state.request_id
            )
            if assignment and not user.get("impersonation"):
                assignment_id = assignment["id"]
                db.attach_employee_to_assignment(
                    assignment["id"], effective["id"], request_id=request.state.request_id
                )
                db.mark_invites_claimed(identifier)
                assignment = db.get_assignment_by_id(assignment["id"], request_id=request.state.request_id)
                case_id = assignment.get("case_id", "")
                now_iso = datetime.utcnow().isoformat()
                try:
                    db.ensure_case_participant(
                        case_id=case_id,
                        person_id=effective["id"],
                        role="relocatee",
                        joined_at=now_iso,
                        request_id=getattr(request.state, "request_id", None),
                    )
                except Exception as exc:
                    log.warning(
                        "ensure_case_participant skipped assignment_id=%s case_id=%s role=relocatee error=%s",
                        assignment_id, case_id, str(exc),
                    )
                event_type = "assignment.claimed"
                try:
                    db.insert_case_event(
                        case_id=assignment["case_id"],
                        assignment_id=assignment["id"],
                        actor_principal_id=effective["id"],
                        event_type=event_type,
                        payload={},
                        request_id=getattr(request.state, "request_id", None),
                    )
                except Exception as exc:
                    log.warning(
                        "insert_case_event skipped assignment_id=%s case_id=%s event_type=%s error=%s",
                        assignment_id,
                        case_id,
                        event_type,
                        str(exc),
                    )

    if not assignment:
        return {"assignment": None}
    assignment["status"] = normalize_status(assignment["status"])
    return {"assignment": assignment}


@app.get("/api/employee/messages")
def list_employee_messages(user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))):
    effective = _effective_user(user, UserRole.EMPLOYEE)
    items = db.list_messages_for_employee(effective["id"])
    return {"messages": items}


@app.post("/api/employee/assignments/{assignment_id}/claim")
def claim_assignment(
    assignment_id: str,
    request: ClaimAssignmentRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    _deny_if_impersonating(user)
    effective = _effective_user(user, UserRole.EMPLOYEE)
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # User may have email, username, or both. HR can assign using either.
    user_identifiers = [x.lower() for x in [effective.get("email"), effective.get("username")] if x]
    if not user_identifiers:
        raise HTTPException(status_code=400, detail="Your account must have an email or username set")

    if not request.email or not request.email.strip():
        raise HTTPException(status_code=400, detail="Enter your email or username to claim")

    req_id = request.email.strip().lower()
    if req_id not in user_identifiers:
        raise HTTPException(status_code=403, detail="The identifier you entered does not match your account. Use the same email or username you used to log in.")

    assignment_identifier = (assignment["employee_identifier"] or "").strip().lower()
    if assignment_identifier not in user_identifiers:
        raise HTTPException(
            status_code=403,
            detail="This assignment was created for a different employee. HR must have entered your exact email or username (e.g. jane@relopass.com or janedoe) when assigning the case."
        )

    if assignment.get("employee_user_id") and assignment["employee_user_id"] != effective["id"]:
        raise HTTPException(status_code=403, detail="Assignment already claimed")

    case_id = assignment.get("case_id", "")
    db.attach_employee_to_assignment(assignment_id, effective["id"])
    db.mark_invites_claimed(assignment["employee_identifier"])
    now_iso = datetime.utcnow().isoformat()
    try:
        db.ensure_case_participant(
            case_id=case_id,
            person_id=effective["id"],
            role="relocatee",
            joined_at=now_iso,
        )
    except Exception as exc:
        log.warning(
            "ensure_case_participant skipped assignment_id=%s case_id=%s role=relocatee error=%s",
            assignment_id, case_id, str(exc),
        )
    event_type = "assignment.claimed"
    try:
        db.insert_case_event(
            case_id=assignment["case_id"],
            assignment_id=assignment_id,
            actor_principal_id=effective["id"],
            event_type=event_type,
            payload={},
        )
    except Exception as exc:
        log.warning(
            "insert_case_event skipped assignment_id=%s case_id=%s event_type=%s error=%s",
            assignment_id,
            case_id,
            event_type,
            str(exc),
        )
    return {"success": True, "assignmentId": assignment_id}


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


@app.get("/api/hr/assignments", response_model=List[AssignmentSummary])
def list_hr_assignments(
    request: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """
    List HR assignments with attached relocation case summary.

    - Auth: HR (or ADMIN).
    - Data: assignments from case_assignments filtered by hr_user_id (or all for admin),
      plus case metadata from relocation_cases.
    """
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    try:
        if user.get("is_admin") and not user.get("impersonation"):
            with timed("db.list_all_assignments", request_id):
                assignments = db.list_all_assignments()
        else:
            effective = _effective_user(user, UserRole.HR)
            with timed("db.list_assignments_for_hr", request_id):
                assignments = db.list_assignments_for_hr(effective["id"], request_id=request_id)

        if not assignments:
            return []

        # Collect case_ids for bulk lookup.
        case_ids = [a.get("case_id") for a in assignments if a.get("case_id")]
        cases_by_id: Dict[str, Any] = {}

        if case_ids:
            # Deduplicate to keep query small.
            unique_ids = list({cid for cid in case_ids if cid})
            if unique_ids:
                # Build a parameterized IN clause to support both SQLite and Postgres.
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
            report = None
            try:
                report = db.get_latest_compliance_report(assignment["id"])
            except Exception:
                pass
            case_meta = cases_by_id.get(assignment.get("case_id"))
            case_id = assignment.get("case_id") or assignment.get("id") or ""

            submitted_at = assignment.get("submitted_at")
            # In SQLite this is stored as text; in Postgres it may be timestamptz.
            # Pydantic model expects Optional[str], so normalize here.
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
                complianceStatus=report["overallStatus"] if report else None,
                employeeFirstName=assignment.get("employee_first_name"),
                employeeLastName=assignment.get("employee_last_name"),
                case=case_meta,
            ))
        return summaries
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
    db.mark_conversation_read(assignment_id, effective["id"])
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
        if (not user.get("is_admin")) or user.get("impersonation"):
            effective = _effective_user(user, UserRole.HR)
            if assignment.get("hr_user_id") != effective["id"]:
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
    effective = _effective_user(user, UserRole.HR)
    if assignment.get("hr_user_id") != effective["id"] and not effective.get("is_admin"):
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
    effective = _effective_user(user, UserRole.HR)
    if assignment.get("hr_user_id") != effective["id"] and not effective.get("is_admin"):
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
    effective = _effective_user(user, UserRole.HR)
    if assignment.get("hr_user_id") != effective["id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
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
    effective = _effective_user(user, UserRole.HR)
    if assignment.get("hr_user_id") != effective["id"]:
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
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    visible = False
    if is_employee and emp_id == effective["id"]:
        visible = True
    if is_hr and (effective.get("is_admin") or hr_id == effective["id"]):
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
    # Ensure destCity/destCountry come from draft when case columns are null
    case_dump = case_dto.model_dump(mode="json")
    basics = draft.get("relocationBasics") or {}
    if not case_dump.get("destCity") and basics.get("destCity"):
        case_dump["destCity"] = basics.get("destCity")
    if not case_dump.get("destCountry") and basics.get("destCountry"):
        case_dump["destCountry"] = basics.get("destCountry")
    return {
        "assignment": {
            "id": assignment["id"],
            "case_id": assignment["case_id"],
            "employee_user_id": emp_id,
            "hr_user_id": hr_id,
            "status": assignment.get("status", ""),
            "employee_identifier": assignment.get("employee_identifier"),
        },
        "case": case_dump,
    }


@app.get("/api/assignments/{assignment_id}/timeline")
def get_assignment_timeline(
    assignment_id: str,
    ensure_defaults: bool = Query(False, description="Create default milestones if none exist"),
    req: Request = None,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """List timeline milestones for the case linked to this assignment. Convenience wrapper."""
    assignment = _require_assignment_visibility(assignment_id, user)
    case_id = assignment.get("case_id")
    if not case_id:
        raise HTTPException(status_code=404, detail="Assignment has no linked case")
    request_id = getattr(req.state, "request_id", None) if req else None
    request_id = request_id or str(uuid.uuid4())
    milestones = db.list_case_milestones(case_id, request_id=request_id)
    if ensure_defaults and len(milestones) == 0:
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
                draft = json.loads(getattr(case, "draft_json", None) or "{}")
                target_move_date = getattr(case, "target_move_date", None)
        defaults = compute_default_milestones(
            case_id=case_id,
            case_draft=draft,
            selected_services=services,
            target_move_date=str(target_move_date) if target_move_date else None,
        )
        for m in defaults:
            db.upsert_case_milestone(
                case_id=case_id,
                milestone_type=m["milestone_type"],
                title=m["title"],
                description=m.get("description"),
                target_date=m.get("target_date"),
                status=m.get("status", "pending"),
                sort_order=m.get("sort_order", 0),
                request_id=request_id,
            )
        milestones = db.list_case_milestones(case_id, request_id=request_id)
    for m in milestones:
        m["links"] = db.list_milestone_links(m["id"], request_id=request_id)
    return {"case_id": case_id, "assignment_id": assignment_id, "milestones": milestones}


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
    visible = (is_employee and emp_id == effective["id"]) or (is_hr and (effective.get("is_admin") or hr_id == effective["id"]))
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
            draft = json.loads(case.draft_json or "{}")

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


def _require_case_access(case_id: str, user: Dict[str, Any]):
    """Validate user can access case. Returns assignment. Use for RFQ/quote endpoints that have case_id from rfq."""
    assignment = db.get_assignment_by_case_id(case_id) or db.get_assignment_by_id(case_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Case not found")
    return _require_assignment_visibility(assignment["id"], user)


def _require_assignment_visibility(
    assignment_id: str,
    user: Dict[str, Any],
):
    assignment = db.get_assignment_by_id(assignment_id) or db.get_assignment_by_case_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    role = UserRole.HR if user.get("role") in (UserRole.HR.value, UserRole.ADMIN.value) else UserRole.EMPLOYEE
    effective = _effective_user(user, role)
    emp_id = assignment.get("employee_user_id")
    hr_id = assignment.get("hr_user_id")
    is_employee = effective.get("role") == UserRole.EMPLOYEE.value
    is_hr = effective.get("role") == UserRole.HR.value or effective.get("is_admin")
    visible = False
    if is_employee and emp_id == effective["id"]:
        visible = True
    if is_hr and (effective.get("is_admin") or hr_id == effective["id"]):
        visible = True
    if not visible:
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    return assignment


def _require_company_for_user(user: Dict[str, Any]) -> Dict[str, Any]:
    profile = db.get_profile_record(user.get("id"))
    if not profile or not profile.get("company_id"):
        raise HTTPException(status_code=400, detail="User missing company association")
    return profile


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
        return (code, "Policy upload is not configured correctly. Contact support.")
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
    _ = _require_case_access(rfq["case_id"], user)
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
    _ = _require_case_access(rfq["case_id"], user)
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


@app.get("/api/employee/assignments/{assignment_id}/policy")
def get_employee_assignment_policy(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Employee: Get resolved policy for this assignment (read-only, published only)."""
    assignment = _require_assignment_visibility(assignment_id, user)
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
        return {"policy": None, "benefits": [], "exclusions": [], "message": "No published policy for your assignment."}
    benefits = db.list_resolved_policy_benefits(resolved["id"])
    exclusions = db.list_resolved_policy_exclusions(resolved["id"])
    policy = resolved.get("policy") or {}
    version = resolved.get("version") or {}
    return {
        "policy": {
            "id": policy.get("id"),
            "title": policy.get("title"),
            "version": version.get("version_number"),
            "effective_date": policy.get("effective_date"),
        },
        "benefits": benefits,
        "exclusions": exclusions,
        "resolved_at": resolved.get("resolved_at"),
    }


@app.get("/api/employee/assignments/{assignment_id}/policy-envelope")
def get_employee_policy_envelope(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Employee: Get policy envelope (envelope cards ready) for comparison/budget logic."""
    data = get_employee_assignment_policy(assignment_id, user)
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
    effective = _effective_user(user, UserRole.HR)
    if assignment.get("hr_user_id") != effective["id"] and not effective.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized for this assignment")
    from .services.policy_service_comparison import compute_policy_service_comparison
    return compute_policy_service_comparison(db, assignment_id, assignment=assignment, include_diagnostics=True)


@app.get("/api/employee/assignments/{assignment_id}/policy-budget")
def get_assignment_policy_budget(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    _ = _require_assignment_visibility(assignment_id, user)
    policy = policy_engine.load_policy()
    return normalize_policy_caps(policy)


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
    _ = _require_case_access(case_id, user)
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
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """List case milestones (timeline). Optionally ensure default set exists."""
    access = _require_case_access(case_id, user)
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())
    milestones = db.list_case_milestones(case_id, request_id=request_id)

    if ensure_defaults and len(milestones) == 0:
        # Compute and persist defaults from case context
        assignment = access.get("assignment", {})
        assignment_id = assignment.get("id")
        services = []
        if assignment_id:
            try:
                svc_rows = db.list_case_services(assignment_id, request_id=request_id)
                services = [r["service_key"] for r in svc_rows if r.get("selected") in (True, 1)]
            except Exception:
                pass
        draft = {}
        target_move_date = None
        with SessionLocal() as session:
            case = app_crud.get_case(session, case_id)
            if case:
                draft = json.loads(getattr(case, "draft_json", None) or "{}")
                target_move_date = getattr(case, "target_move_date", None)
        defaults = compute_default_milestones(
            case_id=case_id,
            case_draft=draft,
            selected_services=services,
            target_move_date=str(target_move_date) if target_move_date else None,
        )
        for m in defaults:
            db.upsert_case_milestone(
                case_id=case_id,
                milestone_type=m["milestone_type"],
                title=m["title"],
                description=m.get("description"),
                target_date=m.get("target_date"),
                status=m.get("status", "pending"),
                sort_order=m.get("sort_order", 0),
                request_id=request_id,
            )
        milestones = db.list_case_milestones(case_id, request_id=request_id)

    # Enrich with links
    for m in milestones:
        links = db.list_milestone_links(m["id"], request_id=request_id)
        m["links"] = links

    return {"case_id": case_id, "milestones": milestones}


@app.patch("/api/cases/{case_id}/timeline/milestones/{milestone_id}")
def update_case_milestone(
    case_id: str,
    milestone_id: str,
    req: Request,
    body: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    """Update a milestone (title, description, target_date, actual_date, status, sort_order)."""
    _ = _require_case_access(case_id, user)
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
    }
    updated = db.upsert_case_milestone(
        case_id=case_id,
        milestone_type=merged["milestone_type"],
        title=merged["title"],
        description=merged["description"],
        target_date=merged["target_date"],
        actual_date=merged["actual_date"],
        status=merged["status"],
        sort_order=merged["sort_order"],
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
    _ = _require_case_access(case_id, user)
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
    _require_case_access(request.case_id, user)
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
    _require_case_access(request.case_id, user)
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
    _require_case_access(case_id, user)
    return {"events": db.list_trace_events(case_id)}


@app.get("/api/guidance/explain")
def get_guidance_explain(
    case_id: str = Query(...),
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    _require_case_access(case_id, user)
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
    try:
        data = compute_requirements_sufficiency(case_id, effective["id"])
        return data
    except ValueError as e:
        if "Case not found" in str(e):
            raise HTTPException(status_code=404, detail="Case not found")
        raise
    except Exception as e:
        log.warning("compute_requirements_sufficiency failed for case %s: %s", case_id, e, exc_info=True)
        return {
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
    if is_employee and emp_id == effective["id"]:
        visible = True
    if is_hr and (effective.get("is_admin") or hr_id == effective["id"]):
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
    if not profile:
        raise HTTPException(status_code=400, detail="No employee profile available")

    report = compliance_engine.run(profile)
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
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    profile = _require_company_for_user(user)
    policies = db.list_company_policies(profile["company_id"])
    return {"policies": policies}


# ---------------------------------------------------------------------------
# Policy Document Intake (staging layer before company_policies)
# ---------------------------------------------------------------------------

BUCKET_HR_POLICIES = "hr-policies"


def _upload_error_response(error_code: str, message: str, status: int = 500) -> JSONResponse:
    """Return structured JSON error for policy upload."""
    return JSONResponse(
        status_code=status,
        content={"error_code": error_code, "message": message},
    )


@app.get("/api/hr/policy-documents/health")
def policy_documents_health(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    """
    Diagnostic endpoint for policy document upload readiness.
    Returns Supabase storage and policy table health.
    """
    from .services.policy_storage_health import check_policy_storage_health
    health = check_policy_storage_health(db)
    return health


@app.post("/api/hr/policy-documents/upload")
async def upload_policy_document(
    req: Request,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Upload policy PDF/DOCX for intake: extract text, classify, extract metadata."""
    from .services.policy_storage_health import (
        check_policy_storage_health,
        STORAGE_MISSING_SERVICE_ROLE,
        STORAGE_BUCKET_NOT_FOUND,
        POLICY_DOCUMENTS_TABLE_MISSING,
        DB_INSERT_FAILED,
    )
    request_id = getattr(req.state, "request_id", None) if req else None
    profile = _require_company_for_user(user)
    filename = file.filename or "policy"
    ext = filename.split(".")[-1].lower()
    if ext not in ("docx", "pdf"):
        return _upload_error_response("invalid_file_type", "Only .docx or .pdf supported", 400)
    mime = file.content_type or ("application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    content = await file.read()

    # Validate config before upload
    health = check_policy_storage_health(db)
    if not health["supabase_url_present"] or not health["service_role_present"]:
        log.error("request_id=%s policy_upload config missing: url=%s service_role=%s", request_id, health["supabase_url_present"], health["service_role_present"])
        return _upload_error_response(STORAGE_MISSING_SERVICE_ROLE, "Policy upload is not configured correctly. Contact support.")
    if not health["bucket_access_ok"]:
        log.error("request_id=%s policy_upload bucket access failed", request_id)
        return _upload_error_response(STORAGE_BUCKET_NOT_FOUND, "Policy storage bucket is unavailable.")
    if not health["policy_documents_table_ok"]:
        log.error("request_id=%s policy_upload policy_documents table missing", request_id)
        return _upload_error_response(POLICY_DOCUMENTS_TABLE_MISSING, "Policy database tables are missing.")

    checksum = None
    try:
        from .services.policy_document_intake import (
            compute_checksum,
            process_uploaded_document,
        )
        checksum = compute_checksum(content)
    except Exception as e:
        log.warning("request_id=%s policy_document_upload checksum failed: %s", request_id, e)
    doc_id = str(uuid.uuid4())
    path = f"companies/{profile['company_id']}/policy-documents/{doc_id}/{filename}"

    try:
        supabase = get_supabase_admin_client()
        supabase.storage.from_(BUCKET_HR_POLICIES).upload(
            path, content,
            {"content-type": mime, "upsert": True},
        )
    except Exception as exc:
        log.error("request_id=%s policy_document_upload storage failed: %s", request_id or "?", exc, exc_info=True)
        code, msg = _map_storage_exception_to_response(exc, BUCKET_HR_POLICIES)
        return _upload_error_response(code, msg)

    try:
        db.create_policy_document(
            doc_id=doc_id,
            company_id=profile["company_id"],
            uploaded_by_user_id=user.get("id", ""),
            filename=filename,
            mime_type=mime,
            storage_path=path,
            checksum=checksum,
            request_id=request_id,
        )
    except Exception as exc:
        log.error("request_id=%s policy_document_upload db insert failed: %s", request_id, exc, exc_info=True)
        try:
            supabase = get_supabase_admin_client()
            supabase.storage.from_(BUCKET_HR_POLICIES).remove([path])
        except Exception as cleanup_exc:
            log.warning("request_id=%s policy_document_upload cleanup failed: %s", request_id, cleanup_exc)
        return _upload_error_response(DB_INSERT_FAILED, "Policy database tables are missing.")

    try:
        from .services.policy_document_intake import process_uploaded_document
        result = process_uploaded_document(content, mime, filename, request_id=request_id)
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
        # Segment into clauses when we have raw text
        if result.get("raw_text") and result.get("processing_status") != "failed":
            try:
                from .services.policy_document_clauses import segment_document_from_raw_text
                clauses, seg_err = segment_document_from_raw_text(
                    result["raw_text"], mime, data=content
                )
                if not seg_err and clauses:
                    db.upsert_policy_document_clauses(doc_id, clauses, request_id=request_id)
                    log.info("request_id=%s policy_document_upload segmented %d clauses", request_id, len(clauses))
            except Exception as seg_exc:
                log.warning("request_id=%s policy_document_upload segmentation failed: %s", request_id, seg_exc)
    except Exception as exc:
        log.warning("request_id=%s policy_document_upload processing failed: %s", request_id, exc, exc_info=True)
        db.update_policy_document(
            doc_id,
            processing_status="failed",
            extraction_error=str(exc),
            request_id=request_id,
        )
    doc = db.get_policy_document(doc_id, request_id=request_id)
    return {"document": doc}


@app.get("/api/hr/policy-documents")
def list_policy_documents(
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """List policy documents for company."""
    request_id = getattr(req.state, "request_id", None)
    profile = _require_company_for_user(user)
    docs = db.list_policy_documents(profile["company_id"], request_id=request_id)
    return {"documents": docs}


@app.get("/api/hr/policy-documents/{doc_id}")
def get_policy_document(
    doc_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Get policy document by id."""
    request_id = getattr(req.state, "request_id", None)
    profile = _require_company_for_user(user)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc or doc.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc}


@app.get("/api/hr/policy-documents/{doc_id}/clauses")
def list_policy_document_clauses(
    doc_id: str,
    req: Request,
    clause_type: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """List clauses for a policy document. Optional filter by clause_type."""
    request_id = getattr(req.state, "request_id", None) if req else None
    profile = _require_company_for_user(user)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc or doc.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Document not found")
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
    profile = _require_company_for_user(user)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc or doc.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Document not found")
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
    profile = _require_company_for_user(user)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc or doc.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Document not found")
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
    """Re-run text extraction, classification, and metadata extraction."""
    request_id = getattr(req.state, "request_id", None)
    profile = _require_company_for_user(user)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc or doc.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = doc.get("storage_path") or ""
    try:
        supabase = get_supabase_admin_client()
        data = supabase.storage.from_("hr-policies").download(file_path)
    except Exception as exc:
        log.warning("request_id=%s policy_document_reprocess download failed: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=_sanitize_storage_error(exc, "hr-policies"))
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
        log.warning("request_id=%s policy_document_reprocess failed: %s", request_id, exc, exc_info=True)
        db.update_policy_document(
            doc_id, processing_status="failed", extraction_error=str(exc), request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"Reprocess failed: {str(exc)}")
    doc = db.get_policy_document(doc_id, request_id=request_id)
    return {"document": doc}


@app.post("/api/hr/policy-documents/{doc_id}/normalize")
def normalize_policy_document(
    doc_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Normalize policy document clauses into canonical policy objects."""
    request_id = getattr(req.state, "request_id", None)
    profile = _require_company_for_user(user)
    doc = db.get_policy_document(doc_id, request_id=request_id)
    if not doc or doc.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.get("raw_text"):
        raise HTTPException(status_code=400, detail="Document has no extracted text. Run Reprocess first.")
    clauses = db.list_policy_document_clauses(doc_id, request_id=request_id)
    if not clauses:
        raise HTTPException(status_code=400, detail="No clauses. Run Reprocess to segment the document first.")
    try:
        from .services.policy_normalization import run_normalization
        result = run_normalization(db, doc, clauses, created_by=user.get("id"))
        log.info("request_id=%s normalize policy_document=%s -> policy=%s version=%s", request_id, doc_id, result["policy_id"], result["policy_version_id"])
        return {"policy_id": result["policy_id"], "policy_version_id": result["policy_version_id"], "summary": result["summary"]}
    except Exception as exc:
        log.warning("request_id=%s normalize failed: %s", request_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Normalization failed: {str(exc)}")


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
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
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
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
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


@app.patch("/api/company-policies/{policy_id}/versions/{version_id}/status")
def patch_policy_version_status(
    policy_id: str,
    version_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Update policy version status: draft, review_required, reviewed, published."""
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
    version = db.get_policy_version(version_id)
    if not version or version.get("policy_id") != policy_id:
        raise HTTPException(status_code=404, detail="Version not found")
    status = body.get("status")
    if status not in ("draft", "review_required", "reviewed", "published", "archived"):
        raise HTTPException(status_code=400, detail="Invalid status")
    db.update_policy_version_status(version_id, status)
    updated = db.get_policy_version(version_id)
    return {"version": updated}


@app.post("/api/company-policies/{policy_id}/versions/{version_id}/publish")
def publish_policy_version(
    policy_id: str,
    version_id: str,
    req: Request,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """Publish this version and archive any previously published version. Employees see only published."""
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
    version = db.get_policy_version(version_id)
    if not version or version.get("policy_id") != policy_id:
        raise HTTPException(status_code=404, detail="Version not found")
    db.archive_other_published_versions(policy_id, version_id)
    db.update_policy_version_status(version_id, "published")
    updated = db.get_policy_version(version_id)
    return {"version": updated}


@app.patch("/api/company-policies/{policy_id}/exclusions/{excl_id}")
def patch_exclusion(
    policy_id: str,
    excl_id: str,
    req: Request,
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    """HR override: update exclusion."""
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
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
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
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
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
    benefits = db.list_policy_benefits(policy_id)
    return {"policy": policy, "benefits": benefits}


@app.get("/api/company-policies/{policy_id}/download-url")
def get_company_policy_download_url(
    policy_id: str,
    user: Dict[str, Any] = Depends(require_hr_or_employee),
):
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
    file_path = policy.get("file_url") or ""
    if "/hr-policies/" in file_path:
        file_path = file_path.split("/hr-policies/", 1)[-1]
    try:
        supabase = get_supabase_admin_client()
        signed = supabase.storage.from_("hr-policies").create_signed_url(file_path, 3600)
        return {"url": signed.get("signedURL") or signed.get("signed_url")}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create download url: {str(exc)}")


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
        supabase.storage.from_("hr-policies").upload(
            path,
            content,
            {
                "content-type": file.content_type or "application/octet-stream",
                "upsert": True,
            },
        )
    except Exception as exc:
        log.error("request_id=%s company_policy_upload storage failed: %s", request_id or "?", exc, exc_info=True)
        detail = _sanitize_storage_error(exc, "hr-policies")
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
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
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
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    profile = _require_company_for_user(user)
    policy = db.get_company_policy(policy_id)
    if not policy or policy.get("company_id") != profile["company_id"]:
        raise HTTPException(status_code=404, detail="Policy not found")
    file_path = policy.get("file_url") or ""
    if "/hr-policies/" in file_path:
        file_path = file_path.split("/hr-policies/", 1)[-1]
    try:
        supabase = get_supabase_admin_client()
        data = supabase.storage.from_("hr-policies").download(file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_sanitize_storage_error(exc, "hr-policies"))
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


@app.get("/api/hr/command-center/kpis", response_model=CommandCenterKPIs)
def get_command_center_kpis(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    kpis = db.get_command_center_kpis(hr_user_id=_effective_hr_user(user))
    return CommandCenterKPIs(**kpis)


@app.get("/api/hr/command-center/cases", response_model=List[CommandCenterCaseRow])
def list_command_center_cases(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    risk_filter: Optional[str] = Query(None, pattern="^(green|yellow|red)$"),
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    rows = db.list_command_center_cases(
        hr_user_id=_effective_hr_user(user), page=page, limit=limit, risk_filter=risk_filter
    )
    return [CommandCenterCaseRow(**r) for r in rows]


@app.get("/api/hr/command-center/cases/{assignment_id}", response_model=CommandCenterCaseDetail)
def get_command_center_case_detail(
    assignment_id: str,
    user: Dict[str, Any] = Depends(require_role(UserRole.HR)),
):
    detail = db.get_command_center_case_detail(assignment_id=assignment_id, hr_user_id=_effective_hr_user(user))
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
