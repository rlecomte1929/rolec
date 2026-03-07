"""
Tests for database operations.
"""
import pytest
import os
import tempfile
from database import Database


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    db = Database(db_path=path)
    yield db
    
    # Cleanup
    try:
        os.unlink(path)
    except:
        pass


def test_create_user(test_db):
    """Test creating a user."""
    user_id = "test-user-123"
    email = "test@example.com"
    
    success = test_db.create_user(user_id, email)
    assert success is True
    
    # Try creating again with same email - should fail
    success = test_db.create_user("different-id", email)
    assert success is False


def test_get_user_by_email(test_db):
    """Test retrieving user by email."""
    user_id = "test-user-456"
    email = "user@test.com"
    
    test_db.create_user(user_id, email)
    
    user = test_db.get_user_by_email(email)
    assert user is not None
    assert user["id"] == user_id
    assert user["email"] == email
    
    # Non-existent user
    user = test_db.get_user_by_email("nobody@test.com")
    assert user is None


def test_session_operations(test_db):
    """Test session creation and retrieval."""
    user_id = "test-user-789"
    email = "session@test.com"
    token = "test-token-abc"
    
    test_db.create_user(user_id, email)
    test_db.create_session(token, user_id)
    
    retrieved_user_id = test_db.get_user_by_token(token)
    assert retrieved_user_id == user_id
    
    # Invalid token
    retrieved_user_id = test_db.get_user_by_token("invalid-token")
    assert retrieved_user_id is None


def test_profile_operations(test_db):
    """Test saving and retrieving profiles."""
    user_id = "test-user-profile"
    email = "profile@test.com"
    
    test_db.create_user(user_id, email)
    
    # Save profile
    profile = {
        "userId": user_id,
        "primaryApplicant": {
            "fullName": "John Doe",
            "nationality": "Norwegian"
        }
    }
    
    success = test_db.save_profile(user_id, profile)
    assert success is True
    
    # Retrieve profile
    retrieved = test_db.get_profile(user_id)
    assert retrieved is not None
    assert retrieved["userId"] == user_id
    assert retrieved["primaryApplicant"]["fullName"] == "John Doe"
    
    # Non-existent profile
    retrieved = test_db.get_profile("non-existent-user")
    assert retrieved is None


def test_answer_operations(test_db):
    """Test saving and retrieving answers."""
    user_id = "test-user-answers"
    email = "answers@test.com"
    
    test_db.create_user(user_id, email)
    
    # Save answers
    test_db.save_answer(user_id, "q1", "answer1", False)
    test_db.save_answer(user_id, "q2", "answer2", True)
    
    # Retrieve answers
    answers = test_db.get_answers(user_id)
    assert len(answers) == 2
    assert answers[0]["question_id"] == "q1"
    assert answers[1]["question_id"] == "q2"
    assert answers[1]["is_unknown"] == 1
