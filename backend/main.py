"""
FastAPI main application for ReloPass backend.
"""
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime

from schemas import (
    LoginRequest, LoginResponse, AnswerRequest, NextQuestionResponse,
    RelocationProfile, DashboardResponse, HousingRecommendation,
    SchoolRecommendation, MoverRecommendation, TimelinePhase, TimelineTask,
    OverallStatus
)
from database import db
from agents.orchestrator import IntakeOrchestrator

app = FastAPI(title="ReloPass API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator
orchestrator = IntakeOrchestrator()


# Auth dependency
async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Extract user ID from authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Remove "Bearer " prefix if present
    token = authorization.replace("Bearer ", "")
    
    user_id = db.get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user_id


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ReloPass API"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """
    Mock login endpoint.
    Creates or retrieves user by email.
    """
    # Check if user exists
    user = db.get_user_by_email(request.email)
    
    if not user:
        # Create new user
        user_id = str(uuid.uuid4())
        db.create_user(user_id, request.email)
    else:
        user_id = user["id"]
    
    # Create session token
    token = str(uuid.uuid4())
    db.create_session(token, user_id)
    
    # Initialize empty profile if doesn't exist
    existing_profile = db.get_profile(user_id)
    if not existing_profile:
        initial_profile = RelocationProfile(userId=user_id).model_dump()
        db.save_profile(user_id, initial_profile)
    
    return LoginResponse(
        token=token,
        userId=user_id,
        email=request.email
    )


@app.get("/api/profile/current", response_model=RelocationProfile)
def get_current_profile(user_id: str = Depends(get_current_user)):
    """Get current user's profile."""
    profile = db.get_profile(user_id)
    
    if not profile:
        # Return empty profile
        profile = RelocationProfile(userId=user_id).model_dump()
    
    return profile


@app.get("/api/profile/next-question", response_model=NextQuestionResponse)
def get_next_question(user_id: str = Depends(get_current_user)):
    """Get the next question to ask the user."""
    profile = db.get_profile(user_id)
    
    if not profile:
        profile = RelocationProfile(userId=user_id).model_dump()
    
    # Get answered questions
    answers = db.get_answers(user_id)
    answered_question_ids = set(ans["question_id"] for ans in answers)
    
    # Get next question from orchestrator
    response = orchestrator.get_next_question(profile, answered_question_ids)
    
    return response


@app.post("/api/profile/answer")
def submit_answer(request: AnswerRequest, user_id: str = Depends(get_current_user)):
    """
    Submit an answer to a question.
    Updates profile and returns next question.
    """
    # Get current profile
    profile = db.get_profile(user_id)
    
    if not profile:
        profile = RelocationProfile(userId=user_id).model_dump()
    
    # Apply answer to profile
    profile = orchestrator.apply_answer(profile, request.questionId, request.answer, request.isUnknown)
    
    # Save profile
    db.save_profile(user_id, profile)
    
    # Save answer to audit trail
    db.save_answer(user_id, request.questionId, request.answer, request.isUnknown)
    
    # Get next question
    answers = db.get_answers(user_id)
    answered_question_ids = set(ans["question_id"] for ans in answers)
    next_response = orchestrator.get_next_question(profile, answered_question_ids)
    
    return {
        "success": True,
        "nextQuestion": next_response
    }


@app.post("/api/profile/complete")
def complete_profile(user_id: str = Depends(get_current_user)):
    """
    Mark profile as complete and compute final state.
    Returns readiness rating and recommendations.
    """
    profile = db.get_profile(user_id)
    
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found")
    
    # Compute completion state
    completion_state = orchestrator.compute_completion_state(profile)
    
    return {
        "success": True,
        "completionState": completion_state
    }


@app.get("/api/recommendations/housing")
def get_housing_recommendations(user_id: str = Depends(get_current_user)) -> List[HousingRecommendation]:
    """Get housing recommendations based on profile."""
    profile = db.get_profile(user_id)
    
    if not profile:
        return []
    
    recommendations = orchestrator.recommendation_engine.get_housing_recommendations(profile)
    return recommendations


@app.get("/api/recommendations/schools")
def get_school_recommendations(user_id: str = Depends(get_current_user)) -> List[SchoolRecommendation]:
    """Get school recommendations based on profile."""
    profile = db.get_profile(user_id)
    
    if not profile:
        return []
    
    recommendations = orchestrator.recommendation_engine.get_school_recommendations(profile)
    return recommendations


@app.get("/api/recommendations/movers")
def get_mover_recommendations(user_id: str = Depends(get_current_user)) -> List[MoverRecommendation]:
    """Get mover recommendations based on profile."""
    profile = db.get_profile(user_id)
    
    if not profile:
        return []
    
    recommendations = orchestrator.recommendation_engine.get_mover_recommendations(profile)
    return recommendations


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(user_id: str = Depends(get_current_user)):
    """
    Get complete dashboard data including:
    - Profile completeness
    - Immigration readiness
    - Next actions
    - Timeline
    - All recommendations
    """
    profile = db.get_profile(user_id)
    
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
