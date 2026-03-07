"""
Tests for agent functionality.
"""
import pytest
from datetime import date, timedelta
from agents.validator import ProfileValidator
from agents.readiness_rater import ReadinessRater
from agents.recommendation_engine import RecommendationEngine
from agents.orchestrator import IntakeOrchestrator


def test_validator_passport_expiry():
    """Test passport expiry validation."""
    validator = ProfileValidator()
    
    # Valid passport (expires 1 year after arrival)
    arrival = date.today() + timedelta(days=30)
    expiry = arrival + timedelta(days=365)
    
    profile = {
        "movePlan": {"targetArrivalDate": arrival.isoformat()},
        "primaryApplicant": {"passport": {"expiryDate": expiry.isoformat()}}
    }
    
    normalized, errors = validator.validate_and_normalize(profile)
    assert len(errors) == 0
    
    # Invalid passport (expires too soon)
    expiry_soon = arrival + timedelta(days=30)
    profile["primaryApplicant"]["passport"]["expiryDate"] = expiry_soon.isoformat()
    
    normalized, errors = validator.validate_and_normalize(profile)
    assert len(errors) > 0
    assert any("6 months" in err.message for err in errors)


def test_validator_children_ages():
    """Test children age validation."""
    validator = ProfileValidator()
    
    # Valid children (under 10)
    child_dob = date.today() - timedelta(days=365 * 7)  # 7 years old
    
    profile = {
        "dependents": [
            {"dateOfBirth": child_dob.isoformat()}
        ]
    }
    
    normalized, errors = validator.validate_and_normalize(profile)
    assert len(errors) == 0
    
    # Invalid child (over 10)
    old_child_dob = date.today() - timedelta(days=365 * 12)
    profile["dependents"][0]["dateOfBirth"] = old_child_dob.isoformat()
    
    normalized, errors = validator.validate_and_normalize(profile)
    assert len(errors) > 0
    assert any("over 10" in err.message for err in errors)


def test_validator_completeness_checks():
    """Test completeness checks for recommendations."""
    validator = ProfileValidator()
    
    # Housing minimum
    profile = {
        "movePlan": {
            "housing": {
                "desiredMoveInDate": date.today().isoformat(),
                "bedroomsMin": 3
            }
        }
    }
    
    completeness = validator.is_profile_complete_for_recommendations(profile)
    assert completeness["housing"] is True
    
    # Schools minimum
    profile = {
        "movePlan": {
            "schooling": {
                "schoolingStartDate": date.today().isoformat()
            }
        },
        "dependents": [
            {"dateOfBirth": (date.today() - timedelta(days=365*8)).isoformat()}
        ]
    }
    
    completeness = validator.is_profile_complete_for_recommendations(profile)
    assert completeness["schools"] is True


def test_readiness_rater_scoring():
    """Test immigration readiness scoring."""
    rater = ReadinessRater()
    
    # Minimal profile - should score low
    profile = {
        "complianceDocs": {},
        "primaryApplicant": {"passport": {}, "assignment": {}},
        "movePlan": {}
    }
    
    readiness = rater.compute_readiness(profile)
    assert readiness.score < 50
    assert readiness.status == "RED" or readiness.status == "AMBER"
    assert len(readiness.missingDocs) > 0
    
    # Complete profile - should score high
    arrival = date.today() + timedelta(days=90)
    expiry = arrival + timedelta(days=365)
    
    complete_profile = {
        "complianceDocs": {
            "hasPassportScans": True,
            "hasEmploymentLetter": True,
            "hasMarriageCertificate": True,
            "hasBirthCertificates": True
        },
        "primaryApplicant": {
            "passport": {"expiryDate": expiry.isoformat()},
            "employer": {"roleTitle": "Manager", "salaryBand": "100000-150000"},
            "assignment": {"startDate": arrival.isoformat(), "relocationPackage": True}
        },
        "movePlan": {"targetArrivalDate": arrival.isoformat()},
        "spouse": {"fullName": "Jane Doe", "nationality": "Norwegian"},
        "dependents": [
            {"firstName": "Child 1", "dateOfBirth": (date.today() - timedelta(days=365*8)).isoformat()},
            {"firstName": "Child 2", "dateOfBirth": (date.today() - timedelta(days=365*6)).isoformat()}
        ]
    }
    
    readiness = rater.compute_readiness(complete_profile)
    assert readiness.score >= 80
    assert readiness.status == "GREEN"
    assert len(readiness.missingDocs) == 0


def test_recommendation_engine_housing():
    """Test housing recommendations."""
    engine = RecommendationEngine()
    
    # Profile with specific preferences
    profile = {
        "movePlan": {
            "housing": {
                "desiredMoveInDate": date.today().isoformat(),
                "budgetMonthlySGD": "7000-10000",
                "bedroomsMin": 3,
                "preferredAreas": ["Tanglin", "Holland Village"],
                "mustHave": ["Furnished", "Near MRT"]
            }
        }
    }
    
    recommendations = engine.get_housing_recommendations(profile)
    assert len(recommendations) > 0
    
    # Check that recommendations match criteria
    for rec in recommendations:
        assert rec.bedrooms >= 3
        assert rec.furnished is True
        assert rec.estMonthlySGDMin <= 10000 or rec.estMonthlySGDMax >= 7000


def test_recommendation_engine_schools():
    """Test school recommendations."""
    engine = RecommendationEngine()
    
    # Profile with curriculum preference
    profile = {
        "movePlan": {
            "schooling": {
                "schoolingStartDate": date.today().isoformat(),
                "curriculumPreference": "IB",
                "budgetAnnualSGD": "30000-40000"
            }
        },
        "dependents": [
            {"dateOfBirth": (date.today() - timedelta(days=365*8)).isoformat()}
        ]
    }
    
    recommendations = engine.get_school_recommendations(profile)
    assert len(recommendations) > 0
    
    # Check that IB schools are included
    ib_schools = [rec for rec in recommendations if "IB" in rec.curriculumTags]
    assert len(ib_schools) > 0


def test_recommendation_engine_movers():
    """Test mover recommendations."""
    engine = RecommendationEngine()
    
    # Profile with moving preferences
    profile = {
        "movePlan": {
            "targetArrivalDate": date.today().isoformat(),
            "movers": {
                "inventoryRough": "medium",
                "specialItems": ["Piano", "Bicycles"],
                "storageNeeded": True,
                "insuranceNeeded": True
            }
        }
    }
    
    recommendations = engine.get_mover_recommendations(profile)
    assert len(recommendations) == 5  # All movers returned
    
    # Check RFQ template is populated
    for rec in recommendations:
        assert "medium" in rec.rfqTemplate
        assert "2" in rec.rfqTemplate  # 2 special items


def test_orchestrator_question_flow():
    """Test orchestrator question flow."""
    orchestrator = IntakeOrchestrator()
    
    # Empty profile should return first question
    profile = {
        "userId": "test-user",
        "dependents": [{}, {}],
        "spouse": {},
        "primaryApplicant": {"passport": {}, "employer": {}, "assignment": {}},
        "movePlan": {"housing": {}, "schooling": {}, "movers": {}},
        "complianceDocs": {}
    }
    
    answered = set()
    response = orchestrator.get_next_question(profile, answered)
    
    assert response.isComplete is False
    assert response.question is not None
    assert response.progress["answeredCount"] == 0


def test_orchestrator_apply_answer():
    """Test applying answers to profile."""
    orchestrator = IntakeOrchestrator()
    
    profile = {
        "primaryApplicant": {"fullName": None},
        "movePlan": {"housing": {"budgetMonthlySGD": None}}
    }
    
    # Apply simple answer
    updated = orchestrator.apply_answer(profile, "q_primary_name", "John Smith", False)
    assert updated["primaryApplicant"]["fullName"] == "John Smith"
    
    # Apply unknown answer
    updated = orchestrator.apply_answer(profile, "q_housing_budget", None, True)
    assert updated["movePlan"]["housing"]["budgetMonthlySGD"] == "unknown"


def test_orchestrator_completion_state():
    """Test computing completion state."""
    orchestrator = IntakeOrchestrator()
    
    # Complete profile
    arrival = date.today() + timedelta(days=90)
    expiry = arrival + timedelta(days=365)
    
    profile = {
        "userId": "test-user",
        "primaryApplicant": {
            "fullName": "John Smith",
            "nationality": "Norwegian",
            "dateOfBirth": "1985-01-01",
            "passport": {"expiryDate": expiry.isoformat()},
            "employer": {"name": "Norwegian Investment", "roleTitle": "Manager"},
            "assignment": {"startDate": arrival.isoformat()}
        },
        "spouse": {"fullName": "Jane Smith", "nationality": "Norwegian"},
        "dependents": [
            {"firstName": "Child1", "dateOfBirth": (date.today() - timedelta(days=365*8)).isoformat()},
            {"firstName": "Child2", "dateOfBirth": (date.today() - timedelta(days=365*6)).isoformat()}
        ],
        "movePlan": {
            "targetArrivalDate": arrival.isoformat(),
            "housing": {
                "desiredMoveInDate": arrival.isoformat(),
                "bedroomsMin": 3,
                "budgetMonthlySGD": "7000-10000"
            },
            "schooling": {
                "schoolingStartDate": arrival.isoformat(),
                "curriculumPreference": "IB"
            },
            "movers": {
                "inventoryRough": "medium"
            }
        },
        "complianceDocs": {
            "hasPassportScans": True,
            "hasEmploymentLetter": True,
            "hasMarriageCertificate": True,
            "hasBirthCertificates": True
        }
    }
    
    completion = orchestrator.compute_completion_state(profile)
    
    assert completion["profileCompleteness"] > 0
    assert completion["immigrationReadiness"] is not None
    assert completion["immigrationReadiness"].score > 50
    assert "housing" in completion["recommendations"]
    assert "schools" in completion["recommendations"]
    assert "movers" in completion["recommendations"]
