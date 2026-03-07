# Testing Documentation

This document describes the comprehensive test suite for the ReloPass MVP.

## 📊 Test Coverage Summary

### Backend Tests
- **Total Tests**: 26 tests
- **Coverage**: 94%
- **Framework**: pytest + pytest-cov
- **Status**: ✅ All passing

### Frontend Tests
- **Total Tests**: 18 tests
- **Framework**: Vitest + React Testing Library
- **Status**: ✅ All passing

---

## 🧪 Backend Tests

### Test Categories

#### 1. Database Tests (`tests/test_database.py`)
Tests SQLite database operations:
- ✅ User creation and retrieval
- ✅ Session management
- ✅ Profile storage and retrieval
- ✅ Answer audit trail

**Run**: `python3 -m pytest tests/test_database.py -v`

#### 2. Agent Tests (`tests/test_agents.py`)
Tests the 4-agent system:

**Agent B - Validator**:
- ✅ Passport expiry validation (must be 6+ months after arrival)
- ✅ Children age validation (must be under 10)
- ✅ Timeline validation
- ✅ Completeness checks for recommendations

**Agent C - Readiness Rater**:
- ✅ Scoring algorithm (0-100)
- ✅ Status determination (GREEN/AMBER/RED)
- ✅ Missing documents detection
- ✅ Timeline feasibility checks

**Agent D - Recommendation Engine**:
- ✅ Housing filtering by budget, bedrooms, areas
- ✅ School filtering by curriculum, budget
- ✅ Mover recommendations with RFQ templates
- ✅ Rationale generation

**Agent A - Orchestrator**:
- ✅ Question flow logic
- ✅ Answer application to profile
- ✅ Completion state computation
- ✅ Next question determination

**Run**: `python3 -m pytest tests/test_agents.py -v`

#### 3. API Tests (`tests/test_api.py`)
Tests all FastAPI endpoints:
- ✅ Health check endpoint
- ✅ Login flow and authentication
- ✅ Profile creation on first login
- ✅ Unauthorized access protection
- ✅ Question retrieval
- ✅ Answer submission
- ✅ Multiple answer flow
- ✅ Housing recommendations endpoint
- ✅ Schools recommendations endpoint
- ✅ Movers recommendations endpoint
- ✅ Dashboard endpoint
- ✅ "Unknown" answer handling

**Run**: `python3 -m pytest tests/test_api.py -v`

#### 4. Integration Tests (`tests/test_integration.py`)
End-to-end user journey tests:

**Test 1: Complete Journey**
Simulates a family completing the entire profile:
- Login as Johnson family
- Answer all 34 questions
- Verify profile data stored correctly
- Verify readiness score = 100/100 (GREEN)
- Verify personalized recommendations generated
- Verify dashboard shows "On track" status

**Test 2: Partial Journey with Unknowns**
Tests system behavior with incomplete data:
- Answer minimum required questions
- Mark budget, areas, curriculum as "unknown"
- Verify system still generates recommendations
- Verify lower readiness score with missing docs
- Verify next actions include "decide budget" tasks

**Run**: `python3 -m pytest tests/test_integration.py -v -s`

---

## 🎨 Frontend Tests

### Test Categories

#### 1. Component Tests

**Button Component** (`__tests__/Button.test.tsx`):
- ✅ Renders with children
- ✅ Handles click events
- ✅ Disabled state works
- ✅ Variant styles applied

**ProgressHeader Component** (`__tests__/ProgressHeader.test.tsx`):
- ✅ Displays progress information
- ✅ Shows answered/total count
- ✅ Displays percentage
- ✅ Default step name

**GuidedQuestionCard Component** (`__tests__/GuidedQuestionCard.test.tsx`):
- ✅ Renders question title and explanation
- ✅ Renders correct input type (text, date, boolean, etc.)
- ✅ Handles answer submission
- ✅ Single select with options
- ✅ Multi-select with checkboxes
- ✅ "I don't know yet" button when allowed
- ✅ Boolean Yes/No buttons

#### 2. API Client Tests (`api/__tests__/client.test.ts`)
- ✅ authAPI methods exist
- ✅ profileAPI methods exist
- ✅ recommendationsAPI methods exist
- ✅ dashboardAPI methods exist

**Run**: `npm test -- --run`

---

## 🚀 Running All Tests

### Backend - Quick Run
```bash
cd backend
python3 -m pytest tests/ -v
```

### Backend - With Coverage
```bash
cd backend
python3 -m pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html
```

View coverage report: `backend/htmlcov/index.html`

### Backend - Single Test File
```bash
cd backend
python3 -m pytest tests/test_integration.py -v -s
```

### Frontend - All Tests
```bash
cd frontend
npm test -- --run
```

### Frontend - Watch Mode (for development)
```bash
cd frontend
npm test
```

### Frontend - With UI
```bash
cd frontend
npm run test:ui
```

---

## 🎯 Test Scenarios Covered

### ✅ Happy Path
- User logs in
- Completes all questions
- Receives high readiness score
- Gets personalized recommendations
- Views complete dashboard

### ✅ Partial Completion
- User answers minimum questions
- Marks some as "unknown"
- Still receives recommendations with explanations
- Gets actionable next steps

### ✅ Edge Cases
- Passport expiring too soon → Validation error
- Children over 10 years → Validation error
- School start before arrival → Validation error
- Invalid timeline → Validation error
- Unauthorized API access → 401 error

### ✅ Data Integrity
- Dates normalized to ISO format
- Profile auto-saves after each answer
- Audit trail maintained
- Session management

### ✅ Recommendation Logic
- Budget filtering (with "unknown" support)
- Area preferences applied
- Curriculum filtering
- Must-haves prioritized
- Rationale generated

---

## 📈 Key Metrics

### Backend Coverage by Module
- **database.py**: 100% ✅
- **schemas.py**: 100% ✅
- **seed_data.py**: 100% ✅
- **question_bank.py**: 93%
- **agents/validator.py**: 91%
- **main.py (API)**: 91%
- **agents/recommendation_engine.py**: 88%
- **agents/orchestrator.py**: 87%
- **agents/readiness_rater.py**: 85%

### Test Execution Times
- Backend: ~2-3 seconds (26 tests)
- Frontend: ~1-2 seconds (18 tests)
- **Total**: ~4-5 seconds (44 tests)

---

## 🐛 Known Issues / Warnings

### Deprecation Warnings
- `datetime.utcnow()` is deprecated in Python 3.12
- Not critical for MVP; can be fixed by using `datetime.now(timezone.utc)`

### Security Warnings (npm)
- Some moderate vulnerabilities in dev dependencies
- Not affecting production build
- Can be addressed with `npm audit fix` if needed

---

## 🔄 Continuous Integration

To set up CI/CD, add these commands to your pipeline:

```yaml
# Backend tests
- pip install -r backend/requirements.txt -r backend/test_requirements.txt
- cd backend && python3 -m pytest tests/ --cov=. --cov-report=xml

# Frontend tests
- cd frontend && npm ci
- cd frontend && npm test -- --run --coverage
```

---

## 🎓 Writing New Tests

### Backend Test Template
```python
import pytest
from fastapi.testclient import TestClient
from main import app

def test_new_feature(test_client):
    # Arrange
    token = login_test_user(test_client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Act
    response = test_client.get("/api/endpoint", headers=headers)
    
    # Assert
    assert response.status_code == 200
```

### Frontend Test Template
```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MyComponent } from '../MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

---

## ✅ Test Checklist

Use this checklist when adding new features:

- [ ] Unit tests for new agents/utilities
- [ ] API endpoint tests with auth
- [ ] Component render tests
- [ ] User interaction tests
- [ ] Integration test for complete flow
- [ ] Edge case validation
- [ ] Error handling
- [ ] "Unknown" answer support

---

## 🎉 Current Test Results

**Backend**: 26/26 tests passing ✅  
**Frontend**: 18/18 tests passing ✅  
**Total**: 44/44 tests passing ✅  
**Overall Coverage**: 94% (backend) ✅

All systems tested and operational!
