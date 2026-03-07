"""
Integration test simulating a complete user journey.
"""
import pytest
from fastapi.testclient import TestClient
import os
import tempfile
from main import app
from database import Database, db as global_db
from datetime import date, timedelta


@pytest.fixture
def test_client():
    """Create test client with temporary database."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    global_db.db_path = path
    global_db.init_db()
    
    client = TestClient(app)
    yield client
    
    try:
        os.unlink(path)
    except:
        pass


def test_complete_user_journey(test_client):
    """
    Test a complete user journey from login to dashboard.
    Simulates the Oslo -> Singapore family relocation scenario.
    """
    # Step 1: Login
    response = test_client.post(
        "/api/auth/login",
        json={"email": "johnson.family@example.com"}
    )
    assert response.status_code == 200
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Get initial profile
    response = test_client.get("/api/profile/current", headers=headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["familySize"] == 4
    
    # Step 3: Answer questions progressively
    arrival_date = (date.today() + timedelta(days=120)).isoformat()
    passport_expiry = (date.today() + timedelta(days=730)).isoformat()
    
    answers_sequence = [
        # Timing
        {"questionId": "q_target_arrival_date", "answer": arrival_date},
        {"questionId": "q_assignment_start_date", "answer": arrival_date},
        {"questionId": "q_assignment_duration", "answer": "24"},
        
        # Identity
        {"questionId": "q_primary_name", "answer": "Michael Johnson"},
        {"questionId": "q_primary_nationality", "answer": "Norwegian"},
        {"questionId": "q_primary_dob", "answer": "1985-03-15"},
        {"questionId": "q_passport_expiry", "answer": passport_expiry},
        
        # Employment
        {"questionId": "q_role_title", "answer": "Senior Investment Manager"},
        {"questionId": "q_salary_band", "answer": "150000-200000"},
        {"questionId": "q_relocation_package", "answer": True},
        
        # Family
        {"questionId": "q_spouse_name", "answer": "Sarah Johnson"},
        {"questionId": "q_spouse_nationality", "answer": "Norwegian"},
        {"questionId": "q_spouse_occupation", "answer": "Marketing Manager"},
        {"questionId": "q_child1_name", "answer": "Emma"},
        {"questionId": "q_child1_dob", "answer": (date.today() - timedelta(days=365*8)).isoformat()},
        {"questionId": "q_child2_name", "answer": "Lucas"},
        {"questionId": "q_child2_dob", "answer": (date.today() - timedelta(days=365*6)).isoformat()},
        
        # Housing
        {"questionId": "q_move_in_date", "answer": arrival_date},
        {"questionId": "q_temporary_stay_weeks", "answer": "8"},
        {"questionId": "q_housing_budget", "answer": "7000-10000"},
        {"questionId": "q_bedrooms", "answer": "4"},
        {"questionId": "q_preferred_areas", "answer": ["Tanglin", "Holland Village", "Bukit Timah"]},
        {"questionId": "q_housing_must_haves", "answer": ["Furnished", "Near MRT", "Near schools"]},
        
        # Schools
        {"questionId": "q_school_start_date", "answer": arrival_date},
        {"questionId": "q_curriculum_preference", "answer": "IB"},
        {"questionId": "q_school_budget", "answer": "35000-45000"},
        {"questionId": "q_school_priorities", "answer": ["Academic excellence", "Close to home"]},
        
        # Moving
        {"questionId": "q_inventory_size", "answer": "medium"},
        {"questionId": "q_special_items", "answer": ["Piano"]},
        {"questionId": "q_storage_needed", "answer": False},
        {"questionId": "q_insurance_needed", "answer": True},
        
        # Documents
        {"questionId": "q_has_passport_scans", "answer": True},
        {"questionId": "q_has_marriage_cert", "answer": True},
        {"questionId": "q_has_birth_certs", "answer": True},
        {"questionId": "q_has_employment_letter", "answer": True},
    ]
    
    # Submit all answers
    for answer_data in answers_sequence:
        response = test_client.post(
            "/api/profile/answer",
            headers=headers,
            json=answer_data
        )
        assert response.status_code == 200, f"Failed on {answer_data['questionId']}"
    
    # Step 4: Get updated profile
    response = test_client.get("/api/profile/current", headers=headers)
    assert response.status_code == 200
    updated_profile = response.json()
    
    # Verify profile data
    assert updated_profile["primaryApplicant"]["fullName"] == "Michael Johnson"
    assert updated_profile["spouse"]["fullName"] == "Sarah Johnson"
    assert updated_profile["dependents"][0]["firstName"] == "Emma"
    assert updated_profile["dependents"][1]["firstName"] == "Lucas"
    
    # Step 5: Get housing recommendations
    response = test_client.get("/api/recommendations/housing", headers=headers)
    assert response.status_code == 200
    housing = response.json()
    assert len(housing) > 0
    
    # Verify filtering worked (4 bedrooms, preferred areas)
    for house in housing:
        assert house["bedrooms"] >= 4
        # Budget range should match
        assert house["estMonthlySGDMin"] <= 10000 or house["estMonthlySGDMax"] >= 7000
    
    # Step 6: Get school recommendations
    response = test_client.get("/api/recommendations/schools", headers=headers)
    assert response.status_code == 200
    schools = response.json()
    assert len(schools) > 0
    
    # Verify IB curriculum schools are prioritized
    ib_schools = [s for s in schools if "IB" in s["curriculumTags"]]
    assert len(ib_schools) > 0
    
    # Step 7: Get mover recommendations
    response = test_client.get("/api/recommendations/movers", headers=headers)
    assert response.status_code == 200
    movers = response.json()
    assert len(movers) == 5
    
    # Verify RFQ template is populated
    assert "medium" in movers[0]["rfqTemplate"]
    
    # Step 8: Get dashboard
    response = test_client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    dashboard = response.json()
    
    # Verify dashboard completeness
    assert dashboard["profileCompleteness"] > 70  # Should be high
    assert dashboard["immigrationReadiness"]["score"] >= 80  # Should be GREEN
    assert dashboard["immigrationReadiness"]["status"] == "GREEN"
    assert len(dashboard["immigrationReadiness"]["missingDocs"]) == 0  # All docs provided
    assert dashboard["overallStatus"] == "On track"
    
    # Verify all recommendation types present
    assert len(dashboard["recommendations"]["housing"]) > 0
    assert len(dashboard["recommendations"]["schools"]) > 0
    assert len(dashboard["recommendations"]["movers"]) > 0
    
    # Verify timeline phases
    assert len(dashboard["timeline"]) == 5  # 5 phases
    phase_names = [p["phase"] for p in dashboard["timeline"]]
    assert "Visa & Eligibility" in phase_names
    assert "Housing" in phase_names
    assert "Schools" in phase_names
    assert "Moving Logistics" in phase_names
    
    print("\n✅ Complete journey test passed!")
    print(f"   Profile completeness: {dashboard['profileCompleteness']}%")
    print(f"   Readiness score: {dashboard['immigrationReadiness']['score']}/100")
    print(f"   Status: {dashboard['immigrationReadiness']['status']}")
    print(f"   Housing options: {len(dashboard['recommendations']['housing'])}")
    print(f"   School options: {len(dashboard['recommendations']['schools'])}")
    print(f"   Moving companies: {len(dashboard['recommendations']['movers'])}")


def test_partial_journey_with_unknowns(test_client):
    """
    Test journey where user marks some answers as unknown.
    System should still provide recommendations with explanations.
    """
    # Login
    response = test_client.post(
        "/api/auth/login",
        json={"email": "partial@example.com"}
    )
    token = response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Answer minimum questions with some unknowns
    arrival_date = (date.today() + timedelta(days=90)).isoformat()
    
    answers = [
        {"questionId": "q_target_arrival_date", "answer": arrival_date},
        {"questionId": "q_assignment_start_date", "answer": arrival_date},
        {"questionId": "q_primary_name", "answer": "Test User"},
        {"questionId": "q_primary_nationality", "answer": "Norwegian"},
        {"questionId": "q_primary_dob", "answer": "1990-01-01"},
        {"questionId": "q_passport_expiry", "answer": (date.today() + timedelta(days=700)).isoformat()},
        {"questionId": "q_role_title", "answer": "Manager"},
        
        # Housing with unknowns
        {"questionId": "q_move_in_date", "answer": arrival_date},
        {"questionId": "q_bedrooms", "answer": "3"},
        {"questionId": "q_housing_budget", "answer": None, "isUnknown": True},  # Unknown budget
        {"questionId": "q_preferred_areas", "answer": None, "isUnknown": True},  # Unknown areas
        
        # School with unknowns
        {"questionId": "q_child1_name", "answer": "Child1"},
        {"questionId": "q_child1_dob", "answer": (date.today() - timedelta(days=365*7)).isoformat()},
        {"questionId": "q_child2_name", "answer": "Child2"},
        {"questionId": "q_child2_dob", "answer": (date.today() - timedelta(days=365*5)).isoformat()},
        {"questionId": "q_school_start_date", "answer": arrival_date},
        {"questionId": "q_curriculum_preference", "answer": None, "isUnknown": True},  # Unknown
        
        # Moving
        {"questionId": "q_inventory_size", "answer": "medium"},
        
        # Docs
        {"questionId": "q_has_passport_scans", "answer": False},  # Missing doc
        {"questionId": "q_has_employment_letter", "answer": True},
    ]
    
    for answer_data in answers:
        response = test_client.post(
            "/api/profile/answer",
            headers=headers,
            json=answer_data
        )
        assert response.status_code == 200
    
    # Get dashboard - should still work with unknowns
    response = test_client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    dashboard = response.json()
    
    # Should still get recommendations even with unknowns
    assert len(dashboard["recommendations"]["housing"]) > 0
    assert len(dashboard["recommendations"]["schools"]) > 0
    
    # Readiness should be lower due to missing docs
    assert dashboard["immigrationReadiness"]["score"] < 100
    assert len(dashboard["immigrationReadiness"]["missingDocs"]) > 0
    
    # Should have next actions including unknowns
    assert len(dashboard["nextActions"]) > 0
    
    print("\n✅ Partial journey with unknowns test passed!")
    print(f"   Profile completeness: {dashboard['profileCompleteness']}%")
    print(f"   Readiness score: {dashboard['immigrationReadiness']['score']}/100")
    print(f"   Missing docs: {len(dashboard['immigrationReadiness']['missingDocs'])}")
