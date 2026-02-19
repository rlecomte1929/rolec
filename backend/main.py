"""
FastAPI main application for ReloPass backend.
"""
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import uuid
from datetime import datetime
import re
import json

from .schemas import (
    RegisterRequest, LoginRequest, LoginResponse, AnswerRequest, NextQuestionResponse,
    RelocationProfile, DashboardResponse, HousingRecommendation,
    SchoolRecommendation, MoverRecommendation, TimelinePhase, TimelineTask,
    OverallStatus, UserResponse, UserRole, AssignmentStatus, AssignCaseRequest,
    AssignCaseResponse, CreateCaseResponse, AssignmentSummary, AssignmentDetail,
    EmployeeJourneyRequest, EmployeeJourneyNextQuestion, HRAssignmentDecision,
    UpdateAssignmentIdentifierRequest, ClaimAssignmentRequest,
    UpdateProfilePhotoRequest, PolicyExceptionRequest, ComplianceActionRequest
)
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
from .app.routers import cases as cases_router
from .app.routers import admin as admin_router
from pydantic import BaseModel as _BaseModel

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
log.info("Seeding demo cases...")
seed_demo_cases()
log.info("Startup complete.")

# CORS middleware
default_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://relopass.com",
    "https://www.relopass.com",
]
env_origins = os.getenv("CORS_ORIGINS")
if env_origins:
    extra = [o.strip() for o in env_origins.split(",") if o.strip()]
    default_origins = list(dict.fromkeys(default_origins + extra))

app.add_middleware(
    CORSMiddleware,
    allow_origins=default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router.router)
app.include_router(admin_router.router)

# ---------------------------------------------------------------------------
# Global exception handler: log unhandled errors
# ---------------------------------------------------------------------------
import traceback

@app.exception_handler(Exception)
def _log_unhandled_exception(request, exc: Exception):
    from fastapi import HTTPException as _HTTP
    if isinstance(exc, _HTTP):
        raise exc
    tb = traceback.format_exc()
    log.error("Unhandled exception: %s\n%s", exc, tb)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
    ]
    for emp_id, emp_email, emp_name in employees:
        ensure_user(emp_id, emp_email, "EMPLOYEE", emp_name)

    scenarios = [
        {
            "case_id": "demo-case-oslo-sg-family",
            "assignment_id": "demo-assignment-oslo-sg-family",
            "employee_identifier": "sarah.jenkins@relopass.local",
            "status": AssignmentStatus.EMPLOYEE_SUBMITTED.value,
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
            "case_id": "demo-case-sg-ny-single",
            "assignment_id": "demo-assignment-sg-ny-single",
            "employee_identifier": "mark.thompson@relopass.local",
            "status": AssignmentStatus.IN_PROGRESS.value,
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


_seed_demo_cases()

LEGACY_STATUS_MAP = {
    "PENDING_EMPLOYEE": AssignmentStatus.DRAFT.value,
    "SUBMITTED_TO_HR": AssignmentStatus.EMPLOYEE_SUBMITTED.value,
    "APPROVED": AssignmentStatus.HR_APPROVED.value,
}


def normalize_status(status: str) -> str:
    # Map legacy DB values to the new state machine.
    return LEGACY_STATUS_MAP.get(status, status)


# Auth dependency
async def get_current_user(
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

    return user


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


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ReloPass API"}


@app.post("/api/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest):
    """Register a new user with username or email and role."""
    username = request.username.strip() if request.username else None
    email = request.email.strip() if request.email else None

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

    user_id = str(uuid.uuid4())
    created = db.create_user(
        user_id=user_id,
        username=username,
        email=email,
        password_hash=password_hash,
        role=request.role.value,
        name=request.name,
    )
    if not created:
        raise HTTPException(status_code=400, detail="Unable to create user")

    token = str(uuid.uuid4())
    db.create_session(token, user_id)

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user_id,
            username=username,
            email=email,
            role=request.role,
            name=request.name,
            company=None,
        )
    )


@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """Login with username or email + password."""
    identifier = request.identifier.strip()
    user = db.get_user_by_identifier(identifier)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    from passlib.context import CryptContext
    # Use PBKDF2 to avoid bcrypt backend issues on Windows.
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    if not pwd_context.verify(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = str(uuid.uuid4())
    db.create_session(token, user["id"])

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            username=user.get("username"),
            email=user.get("email"),
            role=UserRole(user["role"]),
            name=user.get("name"),
            company=user.get("company"),
        )
    )


@app.get("/api/profile/current", response_model=RelocationProfile)
def get_current_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile."""
    profile = db.get_profile(user["id"])
    
    if not profile:
        # Return empty profile
        profile = RelocationProfile(userId=user["id"]).model_dump()
    
    return profile


@app.get("/api/profile/next-question", response_model=NextQuestionResponse)
def get_next_question(user: Dict[str, Any] = Depends(get_current_user)):
    """Get the next question to ask the user."""
    profile = db.get_profile(user["id"])
    
    if not profile:
        profile = RelocationProfile(userId=user["id"]).model_dump()
    
    # Get answered questions
    answers = db.get_answers(user["id"])
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
    # Get current profile
    profile = db.get_profile(user["id"])
    
    if not profile:
        profile = RelocationProfile(userId=user["id"]).model_dump()
    
    # Apply answer to profile
    profile = orchestrator.apply_answer(profile, request.questionId, request.answer, request.isUnknown)
    
    # Save profile
    db.save_profile(user["id"], profile)
    
    # Save answer to audit trail
    db.save_answer(user["id"], request.questionId, request.answer, request.isUnknown)
    
    # Get next question
    answers = db.get_answers(user["id"])
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
    profile = db.get_profile(user["id"])
    
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found")
    
    # Compute completion state
    completion_state = orchestrator.compute_completion_state(profile)
    
    return {
        "success": True,
        "completionState": completion_state
    }


@app.get("/api/employee/recommendations")
def get_employee_recommendations(user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))):
    """Get recommendations for employee's assignment (uses employee_profile from wizard)."""
    assignment = db.get_assignment_for_employee(user["id"])
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
def get_dashboard(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get complete dashboard data including:
    - Profile completeness
    - Immigration readiness
    - Next actions
    - Timeline
    - All recommendations
    """
    profile = db.get_profile(user["id"])
    
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found")
    
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
    case_id = str(uuid.uuid4())
    profile = RelocationProfile(userId=user["id"]).model_dump()
    db.create_case(case_id, user["id"], profile)
    return CreateCaseResponse(caseId=case_id)


@app.post("/api/hr/cases/{case_id}/assign", response_model=AssignCaseResponse)
def assign_case(case_id: str, request: AssignCaseRequest, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    case = db.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    employee_identifier = request.employeeIdentifier.strip()
    if not employee_identifier:
        raise HTTPException(status_code=400, detail="Employee identifier required")

    employee_user = db.get_user_by_identifier(employee_identifier)
    assignment_id = str(uuid.uuid4())
    invite_token = None

    db.create_assignment(
        assignment_id=assignment_id,
        case_id=case_id,
        hr_user_id=user["id"],
        employee_user_id=employee_user["id"] if employee_user else None,
        employee_identifier=employee_identifier,
        status=AssignmentStatus.DRAFT.value,
    )

    if not employee_user:
        invite_token = str(uuid.uuid4())
        db.create_assignment_invite(
            invite_id=str(uuid.uuid4()),
            case_id=case_id,
            hr_user_id=user["id"],
            employee_identifier=employee_identifier,
            token=invite_token,
        )

    return AssignCaseResponse(assignmentId=assignment_id, inviteToken=invite_token)


@app.get("/api/employee/assignments/current")
def get_employee_assignment(user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))):
    assignment = db.get_assignment_for_employee(user["id"])
    if not assignment:
        identifier = user.get("username") or user.get("email")
        if identifier:
            assignment = db.get_unassigned_assignment_by_identifier(identifier)
            if assignment:
                db.attach_employee_to_assignment(assignment["id"], user["id"])
                db.mark_invites_claimed(identifier)
                assignment = db.get_assignment_by_id(assignment["id"])

    if not assignment:
        return {"assignment": None}
    assignment["status"] = normalize_status(assignment["status"])
    return {"assignment": assignment}


@app.post("/api/employee/assignments/{assignment_id}/claim")
def claim_assignment(
    assignment_id: str,
    request: ClaimAssignmentRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if not request.email or not user.get("email"):
        raise HTTPException(status_code=400, detail="Email required to claim assignment")

    if request.email.strip().lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="Email does not match logged-in user")

    if assignment["employee_identifier"].lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="Email does not match assignment")

    if assignment.get("employee_user_id") and assignment["employee_user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Assignment already claimed")

    db.attach_employee_to_assignment(assignment_id, user["id"])
    db.mark_invites_claimed(assignment["employee_identifier"])
    return {"success": True}


@app.get("/api/employee/journey/next-question", response_model=EmployeeJourneyNextQuestion)
def employee_next_question(
    assignmentId: str = Query(..., alias="assignmentId"),
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    assignment = db.get_assignment_by_id(assignmentId)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Assignment not assigned to user")

    return _build_employee_journey_payload(assignment)


@app.post("/api/employee/journey/answer", response_model=EmployeeJourneyNextQuestion)
def employee_submit_answer(
    request: EmployeeJourneyRequest,
    user: Dict[str, Any] = Depends(require_role(UserRole.EMPLOYEE))
):
    assignment = db.get_assignment_by_id(request.assignmentId)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Assignment not assigned to user")
    if normalize_status(assignment["status"]) in [
        AssignmentStatus.EMPLOYEE_SUBMITTED.value,
        AssignmentStatus.HR_REVIEW.value,
        AssignmentStatus.HR_APPROVED.value,
    ]:
        raise HTTPException(status_code=400, detail="Assignment is read-only")

    profile = db.get_employee_profile(request.assignmentId)
    if not profile:
        profile = RelocationProfile(userId=request.assignmentId).model_dump()

    profile = orchestrator.apply_answer(profile, request.questionId, request.answer, False)
    db.save_employee_profile(request.assignmentId, profile)
    db.save_employee_answer(request.assignmentId, request.questionId, request.answer)

    if normalize_status(assignment["status"]) == AssignmentStatus.DRAFT.value:
        db.update_assignment_status(request.assignmentId, AssignmentStatus.IN_PROGRESS.value)

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
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.get("employee_user_id") != user["id"]:
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
def list_hr_assignments(user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    assignments = db.list_all_assignments()
    summaries = []
    for assignment in assignments:
        report = db.get_latest_compliance_report(assignment["id"])
        summaries.append(AssignmentSummary(
            id=assignment["id"],
            caseId=assignment["case_id"],
            employeeIdentifier=assignment["employee_identifier"],
            status=AssignmentStatus(normalize_status(assignment["status"])),
            submittedAt=assignment.get("submitted_at"),
            complianceStatus=report["overallStatus"] if report else None,
        ))
    return summaries


@app.delete("/api/hr/assignments/{assignment_id}")
def delete_hr_assignment(assignment_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    deleted = db.delete_assignment(assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"success": True, "deleted": assignment_id}


@app.get("/api/hr/assignments/{assignment_id}", response_model=AssignmentDetail)
def get_hr_assignment(assignment_id: str, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    profile = db.get_employee_profile(assignment_id)
    report = db.get_latest_compliance_report(assignment_id)

    completeness = None
    if profile:
        completion_state = orchestrator.compute_completion_state(profile)
        completeness = completion_state.get("profileCompleteness", 0)

    return AssignmentDetail(
        id=assignment["id"],
        caseId=assignment["case_id"],
        employeeIdentifier=assignment["employee_identifier"],
        status=AssignmentStatus(normalize_status(assignment["status"])),
        submittedAt=assignment.get("submitted_at"),
        hrNotes=assignment.get("hr_notes"),
        profile=RelocationProfile(**profile) if profile else None,
        completeness=completeness,
        complianceReport=report
    )


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
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    profile = db.get_employee_profile(assignment_id)
    if not profile:
        raise HTTPException(status_code=400, detail="No employee profile available")

    report = compliance_engine.run(profile)
    db.save_compliance_report(str(uuid.uuid4()), assignment_id, report)
    if normalize_status(assignment["status"]) in [
        AssignmentStatus.EMPLOYEE_SUBMITTED.value,
        AssignmentStatus.CHANGES_REQUESTED.value,
    ]:
        db.update_assignment_status(assignment_id, AssignmentStatus.HR_REVIEW.value)
    return report


@app.post("/api/hr/assignments/{assignment_id}/decision")
def hr_decision(assignment_id: str, request: HRAssignmentDecision, user: Dict[str, Any] = Depends(require_role(UserRole.HR))):
    assignment = db.get_assignment_by_id(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if request.decision not in [AssignmentStatus.HR_APPROVED, AssignmentStatus.CHANGES_REQUESTED]:
        raise HTTPException(status_code=400, detail="Invalid decision")

    notes_payload = request.notes
    if request.decision == AssignmentStatus.CHANGES_REQUESTED and request.requestedSections:
        notes_payload = json.dumps(
            {
                "notes": request.notes,
                "requestedSections": request.requestedSections,
            }
        )

    db.set_assignment_decision(assignment_id, request.decision.value, notes_payload)
    return {"success": True}


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
        user["id"],
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
    profile = db.get_employee_profile(assignment_id)
    if not profile:
        profile = RelocationProfile(userId=assignment_id).model_dump()
        db.save_employee_profile(assignment_id, profile)
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

    if normalize_status(assignment["status"]) in [
        AssignmentStatus.EMPLOYEE_SUBMITTED.value,
        AssignmentStatus.HR_REVIEW.value,
        AssignmentStatus.HR_APPROVED.value,
    ]:
        response.question = None
        response.isComplete = True

    return EmployeeJourneyNextQuestion(
        question=response.question,
        isComplete=response.isComplete,
        progress=response.progress,
        completeness=completion_state.get("profileCompleteness", 0),
        missingItems=missing_items,
        assignmentStatus=AssignmentStatus(normalize_status(assignment["status"])),
        hrNotes=assignment.get("hr_notes"),
        profile=RelocationProfile(**profile),
    )


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
