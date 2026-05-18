# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Frontend
npm run dev                          # Start frontend dev server (port 3000, proxies /api → :8000)
npm run build                        # tsc + vite build → frontend/dist
cd frontend && npx tsc --noEmit      # Type-check only (run before every PR)
cd frontend && npx vitest            # Run all frontend tests
cd frontend && npx vitest path/to/test.ts  # Run a single test file

# Backend
cd backend && uvicorn main:app --reload --port 8000   # Dev server
cd backend && pytest                 # All tests
cd backend && pytest path/to/test.py::test_function   # Single test
RELOPASS_DISABLE_RATE_LIMITS=1 pytest  # Bypass slowapi limits in tests

# Supabase (run from repo root)
supabase db push                     # Apply pending migrations to remote
supabase migration new <name>        # Create a new migration file
```

## Repo Layout

```
/
├── frontend/src/       React/TS SPA (Vite + Tailwind)
├── backend/
│   ├── main.py         Primary FastAPI entry point (large monolith, being decomposed)
│   ├── database.py     Cross-DB abstraction used by legacy routes
│   ├── db_config.py    Single source for DATABASE_URL + engine config
│   └── app/            Modular refactor layer
│       ├── main.py     create_app() — mounts all app/ routers
│       ├── db.py       SQLAlchemy SessionLocal + init_db()
│       ├── models.py   ORM models
│       ├── routers/    Domain-split FastAPI routers
│       ├── services/   Business logic (~110 modules)
│       ├── agents/     Rule-based orchestrators (NOT LLM)
│       └── recommendations/  Plugin system per service category
└── supabase/migrations/  Applied via supabase CLI
```

## Backend Architecture

**Dual-layer pattern — this is the most important thing to understand:**
- `backend/main.py` is the primary entry point and still owns the bulk of routes (auth, assignments, policies, HR command center, employee journey). It is large (~12k lines) and is being progressively decomposed.
- `backend/app/` is the modular layer. New routes go here as `app/routers/<domain>.py`, registered in `app/main.py`. The `app/` app is mounted into the root `main.py`.
- When adding a new router: create `backend/app/routers/<name>.py`, import and `include_router` it in `backend/app/main.py`. Do not add new routes directly to `backend/main.py`.

**Database access:**
- New code in `app/` uses `app/db.py` (SQLAlchemy `SessionLocal`) and `app/models.py` (ORM).
- Legacy routes in `main.py` use `backend/database.py` (raw psycopg2-style abstraction). Do not mix these in the same module.
- `db_config.py` handles the `postgres://` → `postgresql://` rewrite, auto-appends `sslmode=require` for Supabase, and sets pool params (size=5, overflow=10, recycle=280s). Don't touch engine config anywhere else.
- Production env detection: `if os.environ.get("RENDER") or os.environ.get("ENV") == "production"` skips `.env` loading. Don't rely on `python-dotenv` in production code paths.

**Services layer (`backend/app/services/`):**
Large policy pipeline lives here. Key modules: `hr_policy_resolver.py`, `requirement_evaluation_service.py`, `rules_engine.py`, `question_engine.py`, `requirements_builder.py`. The agents in `backend/agents/` orchestrate these services deterministically — they are not LLM agents.

**Recommendation engine (`backend/app/recommendations/`):**
Plugin-based. Each service category (banks, movers, insurance, etc.) has a plugin subclass. Plugins self-register into a registry. To add a new category, subclass the base plugin and register it.

## Frontend Architecture

**Routing:** React Router 6 SPA. Route definitions and role guards live in `frontend/src/navigation/`. Pages are lazy-loaded in `App.tsx`.

**Three personas, three route trees:**
- Employee: wizard (`/journey`) + case pages
- HR: command center (`/hr`) + company-scoped views
- Admin: full CMS (`/admin`) — countries, policies, suppliers, prospects, catalog, ops dashboards

**State and data fetching:**
- No global state manager. Context is scoped per feature: `SelectedCaseContext`, `EmployeeAssignmentContext`, `HrCompanyContext`, `ServicesFlowContext`.
- HTTP calls go through `frontend/src/api/` wrappers (Axios, base URL = `VITE_API_URL`). Never call the backend directly from components.
- Supabase client is a singleton at `frontend/src/api/supabase.ts` — used for auth, real-time subscriptions, and document queries (not for general data fetching, which goes through the FastAPI API).

**Component system:**
- `frontend/src/components/antigravity/` is the in-house design system (Button, Card, Input, Badge, Alert, etc.). Use these before reaching for anything else.
- Feature-specific components live inside `frontend/src/features/<domain>/`. Shared cross-feature components go in `frontend/src/components/`.

**Build:**
- Vite splits vendors: React, Supabase, Axios are separate chunks.
- Dev proxy: `/api/*` → `http://localhost:8000` (configured in `vite.config.ts`). No CORS headers needed locally.
- Type-check is strict (`strict: true`, `noUnusedLocals`, `noUnusedParameters`). Run `tsc --noEmit` before flagging any task complete.

## Authentication

**Hybrid model — two auth systems in parallel (migration in progress):**
1. ReloPass session tokens: issued at `POST /api/auth/login`, stored in legacy `public.users` table, PBKDF2 via passlib.
2. Supabase Auth JWTs: mirrored via `supabase_auth_sync.py`. Used for RLS enforcement.

Login returns both tokens. The frontend sends the ReloPass token as `Authorization: Bearer <token>` to the FastAPI backend. The Supabase anon key is used by the frontend directly for Supabase operations (subject to RLS).

**RLS pattern:** The Supabase service role key (`SUPABASE_SERVICE_ROLE_KEY`) bypasses RLS — only used in backend Edge Functions and admin migrations. The anon key (`VITE_SUPABASE_ANON_KEY`) is public and subject to RLS policies. Every table exposed to the frontend must have explicit RLS policies.

**Admin access:** Controlled by `public.admin_allowlist` table. `is_admin()` checks `user_id` against this table — the UUID must match the Supabase auth UUID, not the legacy `users.id`.

## Environment Variables

Frontend (prefix `VITE_`):
- `VITE_API_URL` — Backend base URL (default: `https://api.relopass.com`)
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

Backend:
- `DATABASE_URL` — Supabase pooler URL (Transaction mode, port 6543)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — For server-side Supabase ops
- `CORS_ORIGINS` — Comma-separated allowed origins
- `OPENAI_API_KEY` — Policy assistant and document extraction features
- `RELOPASS_DISABLE_RATE_LIMITS=1` — Disable slowapi in test environments

## Deployment

- **Frontend**: Render Static Site. Build: `npm --prefix frontend ci && npm --prefix frontend run build`. Publish dir: `frontend/dist`.
- **Backend**: Render Web Service. Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 4 --proxy-headers`. Python 3.11.
- **Database changes**: Apply Supabase migrations via `supabase db push` or the MCP (`apply_migration`). Never alter schema through the Supabase dashboard SQL editor directly — always commit migration files.
- **Deploy trigger**: Push to `main` on GitHub → Render auto-deploys both services. Health check endpoint: `GET /health`.
