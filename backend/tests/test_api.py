"""
Tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
import os
import tempfile
from main import app
from database import Database, db as global_db


@pytest.fixture
def test_client():
    """Create test client with temporary database."""
    # Create temp database
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Replace global db with test db
    global_db.db_path = path
    global_db.init_db()
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    try:
        os.unlink(path)
    except:
        pass


def test_root_endpoint(test_client):
    """Test root health check."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_flow(test_client):
    """Test login and authentication."""
    # Login
    response = test_client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "provider": "email"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "userId" in data
    assert data["email"] == "test@example.com"
    
    token = data["token"]
    
    # Use token to access protected endpoint
    response = test_client.get(
        "/api/profile/current",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200


def test_login_creates_profile(test_client):
    """Test that login creates initial profile."""
    response = test_client.post(
        "/api/auth/login",
        json={"email": "newuser@example.com"}
    )
    
    token = response.json()["token"]
    
    # Get profile
    response = test_client.get(
        "/api/profile/current",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    profile = response.json()
    assert profile["familySize"] == 4
    assert len(profile["dependents"]) == 2


def test_unauthorized_access(test_client):
    """Test that endpoints are protected."""
    response = test_client.get("/api/profile/current")
    assert response.status_code == 401


def test_question_flow(test_client):
    """Test the question flow."""
    # Login
    response = test_client.post(
        "/api/auth/login",
        json={"email": "questioner@example.com"}
    )
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get first question
    response = test_client.get("/api/profile/next-question", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["isComplete"] is False
    assert data["question"] is not None
    first_question = data["question"]
    
    # Submit answer
    response = test_client.post(
        "/api/profile/answer",
        headers=headers,
        json={
            "questionId": first_question["id"],
            "answer": "2025-06-01",
            "isUnknown": False
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    
    # Next question should be different
    next_q = result["nextQuestion"]["question"]
    if next_q:
        assert next_q["id"] != first_question["id"]


def test_submit_multiple_answers(test_client):
    """Test submitting multiple answers."""
    # Login
    response = test_client.post(
        "/api/auth/login",
        json={"email": "multitest@example.com"}
    )
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Submit several answers
    answers = [
        {"questionId": "q_target_arrival_date", "answer": "2025-08-01"},
        {"questionId": "q_assignment_start_date", "answer": "2025-08-15"},
        {"questionId": "q_primary_name", "answer": "Test User"},
        {"questionId": "q_primary_nationality", "answer": "Norwegian"},
    ]
    
    for ans in answers:
        response = test_client.post(
            "/api/profile/answer",
            headers=headers,
            json=ans
        )
        assert response.status_code == 200
    
    # Check profile was updated
    response = test_client.get("/api/profile/current", headers=headers)
    profile = response.json()
    
    assert profile["primaryApplicant"]["fullName"] == "Test User"
    assert profile["primaryApplicant"]["nationality"] == "Norwegian"


def test_recommendations_endpoint(test_client):
    """Test recommendations endpoints."""
    # Login and setup profile
    response = test_client.post(
        "/api/auth/login",
        json={"email": "recs@example.com"}
    )
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Submit minimum data for housing recommendations
    test_client.post(
        "/api/profile/answer",
        headers=headers,
        json={"questionId": "q_move_in_date", "answer": "2025-08-01"}
    )
    test_client.post(
        "/api/profile/answer",
        headers=headers,
        json={"questionId": "q_bedrooms", "answer": "3"}
    )
    
    # Get housing recommendations
    response = test_client.get("/api/recommendations/housing", headers=headers)
    assert response.status_code == 200
    housing = response.json()
    assert isinstance(housing, list)
    
    # Get schools recommendations (might be empty without enough data)
    response = test_client.get("/api/recommendations/schools", headers=headers)
    assert response.status_code == 200
    
    # Get movers recommendations
    response = test_client.get("/api/recommendations/movers", headers=headers)
    assert response.status_code == 200


def test_dashboard_endpoint(test_client):
    """Test dashboard endpoint."""
    # Login
    response = test_client.post(
        "/api/auth/login",
        json={"email": "dashboard@example.com"}
    )
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get dashboard
    response = test_client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    dashboard = response.json()
    
    assert "profileCompleteness" in dashboard
    assert "immigrationReadiness" in dashboard
    assert "nextActions" in dashboard
    assert "timeline" in dashboard
    assert "recommendations" in dashboard
    assert "overallStatus" in dashboard
    
    assert isinstance(dashboard["timeline"], list)
    assert isinstance(dashboard["nextActions"], list)


def test_unknown_answer(test_client):
    """Test submitting 'unknown' answers."""
    response = test_client.post(
        "/api/auth/login",
        json={"email": "unknown@example.com"}
    )
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Submit unknown answer
    response = test_client.post(
        "/api/profile/answer",
        headers=headers,
        json={
            "questionId": "q_housing_budget",
            "answer": None,
            "isUnknown": True
        }
    )
    
    assert response.status_code == 200
    
    # Check profile has 'unknown' marker
    response = test_client.get("/api/profile/current", headers=headers)
    profile = response.json()
    
    # The orchestrator sets unknown values to "unknown" string
    budget = profile.get("movePlan", {}).get("housing", {}).get("budgetMonthlySGD")
    assert budget == "unknown"
