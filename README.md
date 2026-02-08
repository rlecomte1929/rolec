# ReloPass MVP

**Guided relocation journeys for HR teams**

ReloPass is a multi-agent guided intake system that helps HR teams manage relocations across multiple scenarios. This MVP collects the minimum viable data needed to:

1. Start/prepare the immigration journey (informational readiness rating)
2. Request quotes from moving companies
3. Apply for temporary apartments
4. Shortlist schools for children

---

## 🏗️ Architecture

### Backend
- **Framework**: FastAPI (Python)
- **Database**: SQLite
- **Multi-Agent System**:
  - **Agent A**: Intake Orchestrator (manages question flow)
  - **Agent B**: Profile Validator & Normalizer
  - **Agent C**: Immigration Readiness Rater (informational only)
  - **Agent D**: Recommendation Engine (housing, schools, movers)

### Frontend
- **Framework**: React + TypeScript
- **Build Tool**: Vite
- **Component Library**: Antigravity (custom modern UI components)
- **Routing**: React Router
- **API Client**: Axios

---

## 📋 Features

### ✅ Guided Intake
- Progressive disclosure: one question at a time
- Contextual "why we ask this" microcopy
- Support for "I don't know yet" answers
- Auto-save progress
- Visual progress tracking

### 🎯 Multi-Agent Intelligence
- Deterministic question flow based on previous answers
- Input validation and normalization (dates, formats)
- Immigration readiness scoring (0-100) with status (GREEN/AMBER/RED)
- Personalized recommendations based on profile

### 🏠 Recommendations
- **Housing**: 10+ serviced apartments with filtering by budget, bedrooms, area
- **Schools**: 10+ international schools with curriculum filtering
- **Movers**: 5 international moving companies with RFQ templates

### 📊 Status Dashboard
- Profile completeness tracking
- Immigration readiness with detailed reasons
- Timeline with task phases
- Next actions queue
- Document checklist

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm or yarn

### Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

---


The backend will start at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
```

The frontend will start at `http://localhost:3000`

---

## 🔑 Usage

1. **Open** `http://localhost:3000` in your browser
2. **Sign in** with any email (mock authentication)
3. **Answer questions** in the guided journey
4. **View your dashboard** with recommendations and status

---

## 📁 Project Structure

```
/workspace
├── backend/
│   ├── main.py                 # FastAPI app with all endpoints
│   ├── schemas.py              # Pydantic models
│   ├── database.py             # SQLite operations
│   ├── question_bank.py        # Question definitions
│   ├── seed_data.py            # Housing, schools, movers data
│   ├── agents/
│   │   ├── orchestrator.py     # Agent A: Question flow
│   │   ├── validator.py        # Agent B: Validation
│   │   ├── readiness_rater.py  # Agent C: Readiness scoring
│   │   └── recommendation_engine.py  # Agent D: Recommendations
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts       # API client
│   │   ├── components/
│   │   │   ├── antigravity/    # UI component library
│   │   │   ├── ProgressHeader.tsx
│   │   │   ├── GuidedQuestionCard.tsx
│   │   │   ├── ProfileSidebar.tsx
│   │   │   └── RecommendationPanel.tsx
│   │   ├── pages/
│   │   │   ├── Auth.tsx        # Login page
│   │   │   ├── Journey.tsx     # Guided intake
│   │   │   └── Dashboard.tsx   # Status dashboard
│   │   ├── types.ts            # TypeScript types
│   │   ├── App.tsx             # Main app with routing
│   │   └── main.tsx            # Entry point
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

---

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/login` - Mock login

### Profile
- `GET /api/profile/current` - Get current profile
- `GET /api/profile/next-question` - Get next question
- `POST /api/profile/answer` - Submit answer
- `POST /api/profile/complete` - Finalize profile

### Recommendations
- `GET /api/recommendations/housing` - Get housing options
- `GET /api/recommendations/schools` - Get school options
- `GET /api/recommendations/movers` - Get mover options

### Dashboard
- `GET /api/dashboard` - Get complete dashboard data

---

## 🎨 Design Principles

1. **Low friction**: Ask only what's necessary
2. **Progressive disclosure**: One question at a time
3. **Transparent**: Always explain why we ask
4. **Flexible**: Support "unknown" answers
5. **Clear outcomes**: Status dashboard, not form pile

---

## ⚠️ Important Notes

### Scope Limitations
- **No payments** - MVP doesn't handle transactions
- **No external integrations** - Google login is mocked
- **Informational only** - Not legal advice (disclaimer shown)
- **Single use case** - Oslo → Singapore, family of four only
- **Mock data** - Recommendations use seeded datasets

### Data Model
The system tracks:
- **Household**: Family size, spouse, 2 children
- **Primary Applicant**: Passport, employer (Norwegian Investment), assignment
- **Move Plan**: Housing, schooling, moving preferences
- **Compliance**: Document checklist

---

## 🧪 Testing the Flow

1. **Login** with `test@example.com`
2. **Answer core questions**:
   - Arrival date
   - Assignment start date
   - Personal details (names, nationalities)
   - Housing preferences (budget, areas, bedrooms)
   - School preferences (curriculum, budget)
   - Moving details (inventory size)
   - Document availability
3. **View Dashboard** to see:
   - Readiness score
   - Recommendations
   - Timeline with tasks
   - Next actions

---

## 🔒 Security Notes

- Mock authentication (production would use OAuth2)
- No password storage
- Token-based session management
- CORS enabled for local development

---

## 📝 License

This is an MVP for demonstration purposes.

---

## 🤝 Support

For questions or issues, please check the code comments or reach out to the development team.

---

**Built with ❤️ for smooth relocations**
