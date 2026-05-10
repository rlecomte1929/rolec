# ReloPass

**International relocation operations platform for HR teams**

ReloPass helps HR leaders at SMEs manage employee relocations end-to-end: structured intake, compliance checks, policy enforcement, and clear decision workflows.

**Live**: https://relopass.com · **API**: https://api.relopass.com

---

## Stack

| Layer      | Technology                                                       | Hosted on            |
| ---------- | ---------------------------------------------------------------- | -------------------- |
| Frontend   | React 18 + TypeScript 5.3 + Vite 5 + Tailwind 3                  | Render Static Site   |
| Backend    | FastAPI 0.115 + Uvicorn 0.32 (Python 3.11)                       | Render Web Service   |
| Database   | **Postgres via Supabase** (SQLite only as a dev fallback)        | Supabase             |
| Auth       | Supabase Auth + legacy PBKDF2 token layer (hybrid, see below)    | Supabase             |
| Storage    | Supabase Storage (policy PDFs, logos)                            | Supabase             |
| Realtime   | Supabase Realtime (notifications)                                | Supabase             |
| LLM        | OpenAI (`openai==1.51`) — policy PDF extraction + policy Q&A      | OpenAI               |
| DNS / CDN  | Cloudflare                                                       | Cloudflare           |

Authoritative schema lives in `supabase/migrations/` (92+ migrations as of 2026-04). `backend/database.py` includes idempotent DDL so SQLite-backed local dev works without running migrations.

---

## Product surface (what's actually shipped)

- **HR persona** — Command Center, case summary, assignment review, compliance check, policy upload + assistant, preferred suppliers, company profile, messages, services RFQ inbox
- **Employee persona** — 5-step relocation wizard, case summary, relocation plan, policy page, services flow (questions → estimate → recommendations → RFQ)
- **Admin persona** — countries + resources CMS, policies, tags, categories, events, sources, research, mobility case inspect, ops/freshness dashboards, staging, review queue, suppliers, support

> Three pages are intentionally placeholders (Resources HR view, Submission Center): wired into the router but not yet built. See `frontend/src/pages/PlaceholderPage.tsx`.

---

## Architecture, at a glance

```
                      Cloudflare DNS
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
          Render static site   Render web service
           (React/Vite)          (FastAPI)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            Supabase Postgres   Supabase Auth    Supabase Storage
                    │
                    └── Supabase Realtime (notifications)

                    FastAPI also calls:
                    • OpenAI (policy extraction + Q&A)
                    • Supabase service-role for admin ops
```

The backend is a single FastAPI app. The legacy surface lives in `backend/main.py` (large, being decomposed). Newer work sits under `backend/app/routers/` with SQLAlchemy + Pydantic. Both are mounted on the same app — see `backend/main.py` for the router registration.

### "Agents" — rule-based, not LLM

You'll see `backend/agents/` (orchestrator, validator, readiness_rater, compliance_engine, recommendation_engine). These are **deterministic rule engines**, not LLM agents. The only LLM calls in production are in `backend/services/policy_canonical_extraction.py` and `backend/services/policy_query_answering.py`.

### Hybrid auth — what this means

Accounts are stored in **both** the legacy `public.users` table (PBKDF2 via `passlib`) and Supabase Auth (mirrored via `backend/services/supabase_auth_sync.py`). `POST /api/auth/login` returns a ReloPass session token. Supabase JWTs are used for RLS-enforced Postgres access. Logout invalidates the ReloPass session but not the Supabase JWT — a migration to a single source of truth is tracked as a follow-up.

---

## Repo layout

```
rolec/
├── backend/            FastAPI backend (main.py monolith + app/ modular subsystem)
│   ├── main.py         ~12k lines of routes; being decomposed into backend/app/routers/
│   ├── database.py     SQLAlchemy engine + CRUD class (cross-DB SQLite/Postgres)
│   ├── app/            New modular backend (routers/, services/, models, crud)
│   ├── agents/         Rule-based orchestrators (NOT LLM agents)
│   ├── services/       ~110 service modules — policy pipeline is the biggest cluster
│   ├── routes/         Legacy routers (being retired in favor of app/routers)
│   ├── crawler/        Country-requirements research crawler
│   ├── scripts/        Dev bootstrap, audit harnesses, verification scripts
│   ├── tests/          pytest suite (~90 files)
│   └── requirements.txt
├── frontend/           React + Vite + Tailwind
│   ├── src/
│   │   ├── pages/      Top-level screens (HR, Employee, Admin, Services, Public)
│   │   ├── features/   Feature-folder modules (policy, services, relocation-plan, …)
│   │   ├── components/ Shared UI (antigravity is the in-house component lib)
│   │   ├── api/        Axios client + typed service wrappers
│   │   └── navigation/ Route table + role guards
│   └── package.json
├── supabase/
│   ├── migrations/     Authoritative schema (92+ files)
│   ├── functions/      Edge functions (currently: send-notification-email)
│   └── seed_resources_cms.sql
├── docs/               See docs/INDEX.md for the curated list
└── scripts/            Root build/verify scripts
```

---

## Quick start (local dev)

Prerequisites: Python 3.11, Node 20.18+, a Supabase project for anything that touches policy upload, notifications, or storage.

```bash
# 1. Clone and enter the repo
git clone <repo-url> rolec && cd rolec

# 2. Backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. Environment — copy templates and fill in
cp .env.example .env                                        # backend
cp frontend/.env.development.example frontend/.env.development   # frontend
# Edit frontend/.env.development and set VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY
# Backend .env only needed for features that touch Supabase storage / auth sync

# 4. Run backend (SQLite fallback — tables created on first boot)
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000

# 5. Frontend (new terminal)
cd frontend
npm install
npm run dev          # runs on http://localhost:5173
```

### Tests

```bash
# Backend tests (run from repo root)
cd backend && PYTHONPATH=. pytest tests/ -q
# Rate limits are disabled in tests via RELOPASS_DISABLE_RATE_LIMITS=1 (set in conftest.py)

# Frontend tests
cd frontend && npm test
```

### Policy assistant audit (opt-in)

```bash
PYTHONPATH=. python backend/scripts/bootstrap_backend_database.py
export RELOPASS_AUDIT_POLICY_GOPS="/absolute/path/GOPS 12102.pdf"
export RELOPASS_AUDIT_POLICY_LTA="/absolute/path/Long Term Assignment Policy Summary.pdf"
PYTHONPATH=. python backend/scripts/audit_policy_assistant.py
```

---

## Deployment

### Backend — Render Web Service

| Setting       | Value                                                                  |
| ------------- | ---------------------------------------------------------------------- |
| Runtime       | Python 3.11 (`.python-version`)                                         |
| Build Command | `pip install -r backend/requirements.txt`                              |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers ${WEB_CONCURRENCY:-4} --proxy-headers` |

Required env vars:

```
DATABASE_URL=postgresql://...@aws-0-region.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<legacy-service-role-jwt>
CORS_ORIGINS=https://relopass.com,https://www.relopass.com
OPENAI_API_KEY=<if policy assistant is enabled>
```

### Frontend — Render Static Site

| Setting           | Value                                                              |
| ----------------- | ------------------------------------------------------------------ |
| Build Command     | `npm --prefix frontend ci && npm --prefix frontend run build`      |
| Publish Directory | `frontend/dist`                                                    |
| Node Version      | Pinned by `.nvmrc` (20.18.1)                                        |

Required env vars (both are safe in client bundles; anon key must rely on RLS):

```
VITE_API_URL=https://api.relopass.com
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon jwt>
```

### Health check

```bash
curl https://api.relopass.com/health
```

---

## Security notes

- Password hashing: PBKDF2-SHA256 via `passlib` (pinned at 1.7.4 — latest release; argon2 migration is a tracked follow-up)
- Rate limiting: `slowapi` on `/api/auth/login` (10/min), `/api/auth/register` (5/hour), `/api/employee/assignments/:id/claim` (10/hour). Disable for tests via `RELOPASS_DISABLE_RATE_LIMITS=1`
- CORS origins pinned to `*.relopass.com` + `localhost` dev ports
- Supabase anon key is intentionally public; RLS is the real boundary
- `frontend/.env.development` is git-ignored; use the `.example` template
- Legacy service-role key has never been committed; if it ever is, rotate via Supabase → JWT Keys → rotate standby

Full security context and open items: see [docs/INDEX.md](docs/INDEX.md).

---

## Contributing

- Treat `backend/main.py` as a live monolith being decomposed. New routes should go into `backend/app/routers/` when possible.
- Frontend components with `:any` are technical debt — prefer typed props.
- Test the golden path before opening a PR. CI is not yet in place (see docs/INDEX.md open items).

---

## License

Proprietary. MVP stage.
