# ReloPass

**International relocation operations platform for HR teams**

ReloPass helps HR leaders at SMEs manage employee relocations end-to-end: structured intake, compliance checks, policy enforcement, and clear decision workflows. Built for live B2B demos with HR and Employee personas running side-by-side.

**Live**: [https://relopass.com](https://relopass.com) | **API**: [https://api.relopass.com](https://api.relopass.com)

---

## Architecture Overview

```
                    ┌──────────────────┐
                    │   Cloudflare /   │
                    │   Render Static  │
                    │   (Frontend)     │
                    │   relopass.com   │
                    └────────┬─────────┘
                             │ HTTPS
                             ▼
                    ┌──────────────────┐
                    │   Render Web     │
                    │   Service        │
                    │   (Backend)      │
                    │api.relopass.com  │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    │   SQLite DB      │
                    │   (ephemeral)    │
                    └──────────────────┘
```

| Layer    | Technology                            | Hosted On              |
| -------- | ------------------------------------- | ---------------------- |
| Frontend | React 18 + TypeScript + Vite + Tailwind | Render Static Site   |
| Backend  | FastAPI + Uvicorn (Python 3.11)       | Render Web Service     |
| Database | SQLite (file-based)                   | Render ephemeral disk  |
| DNS      | Cloudflare                            | relopass.com           |

---

## Tech Stack

### Backend

- **Framework**: FastAPI 0.104
- **Server**: Uvicorn 0.24
- **ORM**: SQLAlchemy 2.0 (wizard/admin features) + raw SQLite (legacy features)
- **Validation**: Pydantic 2.5
- **Auth**: Token-based sessions, PBKDF2-SHA256 password hashing (passlib)
- **Multi-Agent System**:
  - Agent A — Intake Orchestrator (question flow and state machine)
  - Agent B — Profile Validator & Normalizer
  - Agent C — Immigration Readiness Rater (informational scoring)
  - Agent D — Recommendation Engine (housing, schools, movers)
- **Additional Engines**:
  - Compliance Engine — deterministic HR compliance checks
  - Policy Engine — configurable policy rules and limits
  - Rules Engine — adaptive required-field logic per destination
  - Research Service — country requirements with citations (stubbed)
  - Requirements Builder — per-case requirements computation

### Frontend

- **Framework**: React 18 + TypeScript 5.3
- **Build**: Vite 5
- **Styling**: Tailwind CSS 3.3
- **Routing**: React Router 6
- **HTTP**: Axios (legacy) + fetch wrappers (wizard/admin)
- **Component Library**: Antigravity (custom UI library)

---

## Project Structure

```
rolec/
├── backend/
│   ├── main.py                          # FastAPI app — all legacy endpoints + CORS + auth
│   ├── schemas.py                       # Pydantic models (profiles, requests, responses)
│   ├── database.py                      # SQLite database class (users, assignments, profiles)
│   ├── question_bank.py                 # Question definitions for guided intake
│   ├── seed_data.py                     # Housing, schools, movers seed datasets
│   ├── policy_engine.py                 # HR policy rules engine
│   ├── agents/
│   │   ├── orchestrator.py              # Agent A: question flow orchestration
│   │   ├── validator.py                 # Agent B: profile validation & normalization
│   │   ├── readiness_rater.py           # Agent C: immigration readiness scoring
│   │   ├── compliance_engine.py         # Compliance checks for HR review
│   │   └── recommendation_engine.py     # Agent D: housing/schools/movers recommendations
│   ├── app/                             # New modular backend (wizard + admin)
│   │   ├── main.py                      # Sub-application factory
│   │   ├── db.py                        # SQLAlchemy engine + session
│   │   ├── models.py                    # SQLAlchemy models (Case, CountryProfile, etc.)
│   │   ├── schemas.py                   # Pydantic DTOs for wizard/admin APIs
│   │   ├── crud.py                      # Database CRUD operations
│   │   ├── seed.py                      # Demo case seeding
│   │   ├── routers/
│   │   │   ├── cases.py                 # /api/cases/* endpoints
│   │   │   └── admin.py                 # /api/admin/* endpoints
│   │   └── services/
│   │       ├── research.py              # Country research provider
│   │       ├── rules_engine.py          # Adaptive field requirements
│   │       └── requirements_builder.py  # Per-case requirements computation
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts               # Axios instance + fetch wrappers + API_BASE_URL
│   │   │   ├── cases.ts                # Case wizard API functions
│   │   │   └── admin.ts                # Admin API functions
│   │   ├── components/
│   │   │   ├── antigravity/            # UI component library (Button, Card, Badge, etc.)
│   │   │   ├── AppShell.tsx            # Global layout wrapper with navigation
│   │   │   ├── case/
│   │   │   │   ├── CaseContextBar.tsx  # Case status strip
│   │   │   │   └── WizardSidebar.tsx   # 5-step wizard navigation
│   │   │   ├── requirements/
│   │   │   │   ├── RequirementList.tsx  # Requirements with status pills
│   │   │   │   └── Citations.tsx        # Source citations display
│   │   │   └── admin/
│   │   │       ├── CountryTable.tsx     # Country requirements table
│   │   │       └── CountryDetail.tsx    # Country detail view
│   │   ├── pages/
│   │   │   ├── Landing.tsx              # Public landing page + connection test
│   │   │   ├── Auth.tsx                 # Login / registration
│   │   │   ├── EmployeeJourney.tsx      # Employee dashboard (post-submission)
│   │   │   ├── HrDashboard.tsx          # HR dashboard with KPI tiles
│   │   │   ├── HrCaseSummary.tsx        # HR case detail + decision panel
│   │   │   ├── HrAssignmentReview.tsx   # HR employee review (Stitch layout)
│   │   │   ├── HrComplianceCheck.tsx    # HR compliance checks by pillar
│   │   │   ├── HrAssignmentPackageReview.tsx  # HR package review
│   │   │   ├── HrPolicy.tsx             # HR policy configuration
│   │   │   ├── employee/
│   │   │   │   ├── CaseWizardPage.tsx   # 5-step wizard orchestrator
│   │   │   │   └── wizard/
│   │   │   │       ├── Step1RelocationBasics.tsx
│   │   │   │       ├── Step2EmployeeProfile.tsx
│   │   │   │       ├── Step3FamilyMembers.tsx
│   │   │   │       ├── Step4AssignmentContext.tsx
│   │   │   │       └── Step5ReviewCreate.tsx
│   │   │   └── admin/
│   │   │       ├── CountriesPage.tsx    # Country requirements browser
│   │   │       └── CountryDetailPage.tsx
│   │   ├── navigation/
│   │   │   ├── routes.ts               # Route definitions + role guards
│   │   │   ├── registry.ts             # Navigation audit registry
│   │   │   └── safeNavigate.ts         # Safe navigation helper
│   │   ├── routes.ts                   # Wizard route constants
│   │   ├── types.ts                    # TypeScript type definitions
│   │   ├── App.tsx                     # Root component with router
│   │   └── main.tsx                    # Vite entry point
│   ├── .env.production                 # VITE_API_URL for production builds
│   ├── .env.development                # VITE_API_URL for local dev
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── scripts/
│   └── verify-build.sh                # CI build verification script
│
├── .nvmrc                              # Node.js 20.18.1
├── .python-version                     # Python 3.11.7
├── .env.example                        # Environment variable reference
├── .gitignore
├── package.json                        # Root build scripts (delegates to frontend)
├── wrangler.jsonc                      # Cloudflare Workers config (optional)
├── README.md
├── README_DEPLOY_CLOUDFLARE.md
└── README_DEPLOY_RENDER.md
```

---

## User Roles & Workflows

### HR Workflow

1. **Login** as HR user
2. **Dashboard** — view KPI tiles (active cases, action required, departing soon, completed)
3. **Create case** — create a relocation case and assign an employee
4. **Monitor** — track employee intake progress
5. **Review** — view employee submission, run compliance checks
6. **Decide** — approve or request changes with section-specific feedback
7. **Policy** — configure policy rules, request exceptions

### Employee Workflow

1. **Login** as Employee user (or claim assignment via invite)
2. **5-Step Wizard**:
   - Step 1: Relocation basics (origin, destination, purpose, dates)
   - Step 2: Employee profile (identity, passport, nationality)
   - Step 3: Family members (spouse, children, dependents)
   - Step 4: Assignment context (employer, contract, salary)
   - Step 5: Review & submit
3. **Dashboard** — read-only view after submission
4. **Changes requested** — if HR requests changes, wizard reopens with targeted feedback

### Case State Machine

```
DRAFT → IN_PROGRESS → EMPLOYEE_SUBMITTED → HR_REVIEW → HR_APPROVED
                                                    ↓
                                          CHANGES_REQUESTED → (back to wizard)
```

---

## API Endpoints

### Health & Root

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Health check (status, version, timestamp) |
| GET | `/` | Service info |

### Authentication

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/api/auth/register` | Register user (username, email, password, role) |
| POST | `/api/auth/login` | Login (returns token) |

### Employee Journey

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/employee/assignments/current` | Get current employee assignment |
| POST | `/api/employee/assignments/:id/claim` | Claim assignment by invite |
| POST | `/api/employee/assignments/:id/submit` | Submit to HR |
| POST | `/api/employee/assignments/:id/photo` | Upload profile photo |
| GET | `/api/employee/journey/next-question` | Next guided question |
| POST | `/api/employee/journey/answer` | Submit answer |

### HR Management

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/api/hr/cases` | Create new relocation case |
| POST | `/api/hr/cases/:id/assign` | Assign employee to case |
| GET | `/api/hr/assignments` | List all assignments |
| GET | `/api/hr/assignments/:id` | Get assignment detail |
| POST | `/api/hr/assignments/:id/decision` | Approve / request changes |
| POST | `/api/hr/assignments/:id/run-compliance` | Run compliance checks |
| GET | `/api/hr/policy` | Get policy configuration |
| POST | `/api/hr/cases/:id/policy/exceptions` | Request policy exception |
| GET | `/api/hr/cases/:id/compliance` | Get compliance report |
| POST | `/api/hr/cases/:id/compliance/run` | Run compliance analysis |

### Case Wizard (New)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/cases/:id` | Get case draft |
| PATCH | `/api/cases/:id` | Update case draft |
| POST | `/api/cases/:id/research/start` | Trigger destination research |
| GET | `/api/cases/:id/requirements` | Get computed requirements |
| POST | `/api/cases/:id/create` | Finalize case + snapshot requirements |

### Admin

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/admin/countries` | List country profiles |
| GET | `/api/admin/countries/:code` | Get country detail + requirements |
| POST | `/api/admin/countries/:code/research/rerun` | Re-run country research |

---

## Local Development

### Prerequisites

- Python 3.11+ (check with `python --version`)
- Node.js 20+ (check with `node --version`)
- npm 9+

### Backend

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows PowerShell:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run the server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Environment Variables

Local dev uses `frontend/.env.development` (auto-loaded by Vite):

```
VITE_API_URL=http://localhost:8000
```

No backend env vars are needed for local development — CORS defaults include localhost origins.

---

## Production Deployment

### Frontend — Render Static Site

| Setting          | Value |
| ---------------- | ----- |
| Root Directory   | (blank — repo root) |
| Build Command    | `npm --prefix frontend ci && npm --prefix frontend run build` |
| Publish Directory | `frontend/dist` |
| Node Version     | Controlled by `.nvmrc` (20.18.1) |

**Environment variable:**

```
VITE_API_URL = https://api.relopass.com
```

### Backend — Render Web Service

| Setting        | Value |
| -------------- | ----- |
| Runtime        | Python |
| Build Command  | `pip install -r backend/requirements.txt` |
| Start Command  | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Python Version | Controlled by `.python-version` (3.11.7) |

**Environment variable:**

```
CORS_ORIGINS = https://relopass.com,https://www.relopass.com
```

### Verify Deployment

```bash
# Backend health
curl https://api.relopass.com/health

# CORS headers
curl -X OPTIONS https://api.relopass.com/health \
  -H "Origin: https://relopass.com" \
  -H "Access-Control-Request-Method: GET" \
  -v 2>&1 | grep -i "access-control"

# Frontend connection test
# Open https://relopass.com → scroll to bottom → click "Test connection"
```

---

## Demo Scenarios (Seeded Data)

The backend seeds three demo relocation cases on startup:

| Route | Scenario | Profile |
| ----- | -------- | ------- |
| Oslo → Singapore | Family of 4, spouse wants to work, kids school-age | Employment |
| Singapore → New York | Single employee | Employment |
| EU → Singapore | Couple, no kids | Employment |

---

## Key Design Decisions

- **Wizard-first UX**: Employees see only the 5-step wizard until submission. No dashboard mixing.
- **Linear progression**: Wizard steps enforce required field completion before advancing.
- **HR correction loop**: HR can request changes on specific sections; employee sees targeted feedback.
- **Deterministic compliance**: All compliance checks are rule-based, not AI-generated.
- **Progress capped at 100%**: Completion percentage is computed from required fields only.
- **Relative imports**: All backend modules use Python package-relative imports for deployment compatibility.
- **Env-based API URL**: Frontend uses `VITE_API_URL` — no hardcoded production URLs in source code.
- **CORS safety**: Production domains are always in the allow-list; `CORS_ORIGINS` env var extends (not replaces) defaults.

---

## Security Notes

- Password hashing: PBKDF2-SHA256 via passlib
- Token-based session management (Bearer tokens)
- Role-based route guards (HR / Employee)
- CORS restricted to known origins
- No secrets in committed env files (only public API URLs)
- SQLite database is ephemeral on Render (resets on redeploy)

---

## License

This is an MVP for demonstration purposes.

---

**Built for smooth international relocations.**
