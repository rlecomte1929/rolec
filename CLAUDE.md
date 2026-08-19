# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What ReloPass is

ReloPass turns a cross-border corporate relocation into a guided, compliant journey. It serves
three personas: **Employee** (the relocating person — intake → services & policy → roadmap),
**HR** (company command center), and **Admin** (CMS: countries, policies, suppliers, catalog).
Stack: TypeScript + React (Vite) SPA frontend + Python FastAPI backend, Supabase/Postgres, on Render.

> Full project overview: see [README.md](README.md).

## Commands

```bash
# Frontend
npm run dev                          # Start frontend dev server (port 3000, proxies /api → :8000)
npm run build                        # tsc + vite build → frontend/dist
cd frontend && npx tsc --noEmit      # Type-check only (run before every PR)
cd frontend && npx vitest            # Run all frontend tests
cd frontend && npx vitest path/to/test.ts  # Run a single test file

# Backend
uvicorn backend.main:app --reload --port 8000        # Dev server (run from repo root — relative imports require package path)
cd backend && pytest                 # All tests
cd backend && pytest path/to/test.py::test_function   # Single test
RELOPASS_DISABLE_RATE_LIMITS=1 pytest  # Bypass slowapi limits in tests

# Supabase (run from repo root)
supabase migration new <name>        # Create a new migration file
supabase migration list --db-url "$DATABASE_URL"   # Compare repo files vs prod ledger

# ⛔ NEVER run `supabase db push` against prod — see "Migration discipline" below.
#    It applies ALL pending migrations: 147 of them as of 2026-08-03, back to April.
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
- `backend/app/` is the modular layer. New routes go here as `app/routers/<domain>.py`, registered in `app/main.py`. Note: `backend/main.py` does **not** sub-mount the `app/` app — it re-imports each `app/routers/` module individually and re-registers it via its own `include_router()` call. That is why a router needs registering in *both* places (see below).

**⚠️ Routers must be registered in BOTH `backend/main.py` AND `backend/app/main.py`.** Render boots `uvicorn backend.main:app`, so a router registered only in `backend/app/main.py` will return 405 in production — the modular app instance is never the one serving traffic. This has bitten us three times now (AI-002 v2 → hotfix `5d796c2`; AIQ-567 → rejected pre-merge; AIQ-568 → rejected pre-merge), so it's a hard rule until the modular cutover described in `backend/MIGRATION_PLAN.md` lands. When you add a new router:
  1. Create `backend/app/routers/<name>.py`.
  2. Register it in `backend/app/main.py` (the modular sub-app, where future-prod will live).
  3. **Also** register it in `backend/main.py` alongside the existing `auth_router`, `cases_read_router`, `ai_decisions_router`, etc. block (~line 580) — the literal import + `include_router` lines belong here too:
     ```python
     # backend/main.py — match the existing pattern (imports ~line 130, registrations ~line 710)
     from .app.routers import <name> as <name>_router   # import the module, aliased
     app.include_router(<name>_router.router)            # register its .router
     ```
     This is an **AND, not an OR**: step 2 (`backend/app/main.py`) is still required for tests and the modular app; step 3 (`backend/main.py`) is what actually serves prod traffic. Skip step 3 and the route 405s in production — that is exactly the AI-002 v2 incident: the `/api/ai/decisions` router was registered in `backend/app/main.py` only, shipped a 405, and needed hotfix `5d796c2` to resolve.
  4. Verify both registrations with `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<your-prefix>' in r.path))"` before pushing — if the route doesn't show up here, prod is dead on arrival.

  This duplication is temporary: once the modular cutover in `backend/MIGRATION_PLAN.md` lands and prod boots the `app/` app directly, the `backend/main.py` re-registration step goes away. Until then, both are mandatory.

  Tests that mount the prod app (`from backend.main import app`) must import auth dependencies (`get_current_user`, `require_admin_or_hr`) from `backend.app.auth_deps` — there's a second `get_current_user` in `backend/main.py` that's a different function, and `dependency_overrides` keyed to the wrong reference silently never fires. AIQ-567's tests had this bug on top of the wiring bug.

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
- **Database changes**: Commit a migration file for every schema change. **There is no automated apply-on-merge** — migrations are applied to production manually/out-of-band (operator-run: MCP `apply_migration`/`execute_sql` DDL — **not** `supabase db push`, see the hazard note in *Migration discipline* below), and the ledger is then reconciled by committing the matching file at the applied version. The PR CI only *validates* ledger consistency (the read-only `migration-drift` check); it never applies. See **Migration discipline (MANDATORY)** and **Ledger reconciliation** below.
- **Deploy trigger**: Push to `main` on GitHub → Render auto-deploys both services. Health check endpoint: `GET /health`.

## Database Migrations — Security Rules (Hard Gates)

Every migration that creates a new table in the `public` schema **must** include all three of the following, or it fails review and must not be merged:

1. **Enable RLS**
   ```sql
   ALTER TABLE public.<table_name> ENABLE ROW LEVEL SECURITY;
   ```

2. **At least one policy** (read + write, scoped to the correct tenant boundary)
   ```sql
   CREATE POLICY "<descriptive name>" ON public.<table_name>
     FOR SELECT USING (/* tenant-scoping expression */);
   ```
   Use the existing `case_milestones` RLS policies as the canonical pattern reference. The `support_tickets` and `ai_decisions` migrations are also recent in-repo references.

3. **Revoke anon access** (defense-in-depth)
   ```sql
   REVOKE ALL ON public.<table_name> FROM anon;
   ```

> **Why this matters:** Supabase exposes the `public` schema via PostgREST and the anon key is shipped in the frontend bundle. A table without RLS is readable by any unauthenticated visitor. This caused SEC-002 (8 tables, GDPR-scope PII exposure). Don't repeat it.

**If you are writing or reviewing a migration and a new table is missing any of the above, stop and add it before proceeding.** This is a hard review gate, not a soft suggestion.

## Compliance claims in customer-facing copy (HARD GATE)

**Never claim an EU AI Act status in shipped copy.** No "EU AI Act Ready", "compliant",
"certified", or "conformant" — and never describe ReloPass as a **high-risk** AI system.

`docs/compliance/AIQ-1487_eu_ai_act_assessment.md` is the source of truth. It found our AI is
**limited-risk, not high-risk**, and it is explicit:

> "Do not ship an 'EU AI Act Ready' / 'Compliant' badge. For a limited-risk system there is no
> certification to be 'ready' for, and the phrasing implies a formal status we don't hold."
> "A false or premature compliance claim is itself a legal liability."

This is not hypothetical: relopass.com shipped an "EU AI Act Ready" badge, a page `<title>` and
meta description saying the same, and a **downloadable PDF aimed at compliance and procurement
teams** — all contradicting our own assessment. Removed in AIQ-1513.

**What you MAY say** — describe what the controls *do*, because those are verifiable product
facts: a human reviews every AI recommendation; each decision is logged with the AI output that
informed it; answers are grounded in the customer's own policy and cited; PII is masked before any
LLM call (`pii_masker.py`). **Describe the controls; claim no status.**

Any *new* compliance claim needs legal sign-off **before** it ships — the assessment itself is
still `DRAFT — legal review required`. Removing a false claim needs no review; adding one does.

CI enforces this: **`scripts/check_compliance_claims.py`** (job: *Compliance claim guard*) scans
`frontend/src`, `frontend/public`, `docs/marketing`, and `content/` and fails the PR on a
prohibited claim. Don't delete the rule to make it pass.

## Data minimisation — PII in AI prompts (GDPR Art. 28/44)

The product sends user-supplied text to third-party LLM sub-processors (OpenAI and Anthropic, both US-based). Under GDPR these are sub-processors of any personal data included in a prompt, so **raw PII must never leave the platform in an LLM payload**.

**Hard rule — mask before the prompt:** Any text that may contain user PII MUST pass through `backend/app/services/pii_masker.py` (`mask_pii()`) before it is placed in a prompt sent to OpenAI or Anthropic. `mask_pii` redacts phone, IBAN, passport, SSN/D-number, national ID, and email. Prefer passing anonymised identifiers or summaries over raw fields.

- The Policy Assistant path (`policy_assistant_llm_client.py`) already masks the user message — follow that pattern.
- When adding a **new** LLM call (anything that reaches `llm_client.py` `complete()`/`complete_text()`, `roadmap_generator`, `entity_resolution`, `policy_extractor`, etc.), mask any free-text user input first. Do not pass raw case details, names, or document contents unless they have been through `mask_pii` or are demonstrably non-personal (e.g. published policy document text).
- Never log raw user input — use `safe_log_text()` from the same module.

Sub-processor DPA coverage and EU-residency status are tracked in `docs/security/PRIV-004_sub-processor_register.md` (GDPR Art. 28 register). Update it whenever a new sub-processor (LLM, email, analytics, hosting, CDN) is added to the stack.

## Generation/serving split (HARD GATE)

**The deterministic requirement-serving path must NEVER be able to call an LLM at
request time.** Served requirements come from rule engines over curated, cited catalog
data; LLMs live only in the authoring/drafting layer, whose output is human-reviewed
before it becomes served data. This is the trust architecture the whole "why not just
use ChatGPT" story rests on.

CI enforces it: **`scripts/check_serving_llm_isolation.py`** (job: *Serving/LLM
isolation guard*; also asserted from pytest via
`scripts/tests/test_check_serving_llm_isolation.py` in the backend-tests job) builds
the full backend import graph via AST — lazy function-local imports included — and
fails the PR with the exact import chain if any serving engine
(`requirements_builder`, `rules_engine`, `requirement_evaluation_service`,
`immigration_requirement_service`, `hr_policy_resolver`) can reach an LLM gateway
module or an LLM SDK import. There is no allowlist. Fix a violation by breaking the
import (move the LLM use into authoring; serve reviewed data), never by editing the
guard's lists. New serving engines must be registered in `SERVING_ROOTS`; a renamed
root fails the build (exit 2) until re-registered, as does any module inside the serving
closure that fails to parse — an unparsed module hides whatever it imports. See
`docs/specs/serving-llm-isolation.md`.

## Corridor requirement data

A corridor's requirement records are the product's core asset. Two rules, both learned by
nearly getting them wrong on IE→ES (`docs/corridors/README.md` has the full set):

**`requirement_items.review_status` DEFAULTS to `'approved'`, and `requirements_builder`
serves only approved rows.** A corridor load that omits the column therefore publishes
unreviewed, representative facts to real users the moment it applies. Set `'pending'`
explicitly, and never let an `ON CONFLICT` update overwrite it — re-running a load must not
un-approve what a reviewer has since approved.

**Verify the live table before writing the load.** A batch manifest names a target table and
key; that is a claim, not a schema. The IE→ES manifest named `requirement_facts` keyed on
`fact_uid` — a table with no `fact_uid` column and two NOT NULL uuid FKs the batch could not
supply. Corridor requirement data lands in `public.requirement_items`, whose varchar `id`
carries the batch's own uid verbatim.

Corridor registry profiles and pathway step graphs live in `corridors/<ID>/`; docs, metrics
and the Case Verification Report live in `docs/corridors/<id>/`.

## Migration discipline (MANDATORY)

NEVER apply a migration to production via MCP `apply_migration` or by manually
inserting into `supabase_migrations.schema_migrations`.

The ONLY permitted workflow for schema changes:
  1. Create `supabase/migrations/<timestamp>_<name>.sql` with idempotent DDL.
  2. Commit and push to a feature branch.
  3. Open a PR. CI's read-only `migration-drift` check validates ledger
     consistency — it does NOT apply the migration. Applying to production is a
     manual/out-of-band step (operator-run; MCP `apply_migration`/`execute_sql`
     DDL), after which the ledger is reconciled by recording
     the repo file's timestamp as the applied version (see **Ledger reconciliation**).

### ⛔ Never run `supabase db push` against prod

`db push` applies **every** pending migration, and the repo/prod ledgers have drifted far
apart. Measured 2026-08-03: 572 distinct repo versions vs 425 in the prod ledger —
**147 pending versions (153 files), reaching back to 2026-04-27**. Two confirmed landmines
in that set:

- `20261004000000_cleanup_living_areas_supplier_shells.sql` — destructive `DELETE`s against
  `company_vendor_selections` and `service_catalog_items`.
- `20260605950000_rfq_requests.sql` — creates `public.rfq_requests`, a **superseded** design.
  Prod renamed that table to `rfq_requests_legacy`; the live RFQ system is `rfqs` /
  `rfq_items` / `rfq_recipients`. Applying it resurrects dead schema beside the live tables.

Most of the drift is bookkeeping (the migration was applied out-of-band and the ledger never
recorded it), but it is **not uniformly so**, which is why there is no safe bulk action.
A full triage — classify each pending migration as applied / superseded / genuinely-missing —
is parked until the pre-launch data reset, when migrations must become authoritative.

**To record an out-of-band apply, reconcile the ledger instead:**

```bash
supabase migration repair --status applied <version> --db-url "$DATABASE_URL"
```

Two gotchas, both hit on AIQ-1744:
- Run it from a checkout that **actually contains the file** — `repair` globs
  `supabase/migrations/<version>_*.sql` and fails with "file does not exist" otherwise. A stale
  local `main` is the usual cause; use a worktree at `origin/main`.
- `supabase migration list` fails against the transaction pooler (port 6543) with
  `prepared statement "lrupsc_1_0" already exists`. Use session mode — swap the port to 5432.

If several files share one timestamp, the ledger (keyed by `version`) can track only **one** of
them, and `repair` records whichever sorts first alphabetically.

### Choosing a migration timestamp

Stamp every migration above **BOTH** the highest repo file version **and** the prod ledger max:

```bash
# the number to beat — take the max of these two, then go above it
git ls-tree origin/main --name-only supabase/migrations/ | sed 's|.*/||' | cut -c1-14 | sort | tail -1
psql "$DATABASE_URL" -tAc "SELECT max(version) FROM supabase_migrations.schema_migrations"
```

**"Above the ledger max" alone is not enough.** The repo max routinely exceeds the ledger max —
that is the normal state whenever migrations are merged but not yet applied, which is most of
the time here. On 2026-08-04 the ledger max was `20261010000000` while the repo max was already
`20261014000000`; three PRs each followed the ledger-only rule, all picked `20261011000000`, and
landed **three files on one version** — below the repo max and colliding with each other. Each
PR was individually valid, which is exactly why the rule has to be the max of both.

Three guards cover this, in order of when they fire:

| guard | catches | blind to |
|---|---|---|
| `migration-duplicate-versions` (ci.yml, PR) | a version already used elsewhere in the PR's own tree | versions added by *other* open PRs |
| its "check added versions against live main" step | a parallel PR that merged first — compares against live `origin/main` | PRs merged without CI re-running in between |
| `migration-duplicate-main.yml` (push to `main`) | anything the above two missed, whole-tree | nothing — it is the backstop |

That last row was **false until 2026-08-11**. The job ran `check_migration_drift.py --no-db`
with no `--added`, which is the script's audit mode: duplicates print a warning and the
process exits 0. It was structurally incapable of failing, including for the
#1716/#1717/#1718 collision it names as its reason to exist. It now passes
`--strict-duplicates`, which is what makes a whole-tree run able to fail — verified by
planting a duplicate and watching the old invocation exit 0 and the new one exit 1. If you
add another whole-tree invocation, it needs that flag or it is decoration.

**Do not batch-merge two migration PRs back to back.** GitHub does not re-run a PR when its base
moves, so both stay green from before either landed, and the live-main comparison never sees the
first merge. Merge one, let the second's CI re-run, then merge it.

Legitimate use of `execute_sql` (MCP): read-only queries and one-time data
backfills that carry no schema change. If you run a hotfix DDL via `execute_sql`,
you MUST immediately commit a matching migration file with the same timestamp
to reconcile the ledger — see "Ledger reconciliation" below.

CI enforces this: the **Migration ledger drift check** job (`scripts/check_migration_drift.py`)
fails a PR when prod has an applied version with no repo file (gated on the read-only
`RLS_COVERAGE_DATABASE_URL` secret; a no-op where that secret isn't configured).

## Ledger reconciliation (hotfix only)
If a migration was applied to prod out-of-band:
  1. Note the exact version string recorded in `supabase_migrations.schema_migrations`.
  2. Check for a duplicate/orphan row:
       SELECT version, name FROM supabase_migrations.schema_migrations
       WHERE name = '<migration_name>'
       ORDER BY version;
  3. If two rows exist for the same name, DELETE the older/mismatched one.
  4. Create `supabase/migrations/<version>_<name>.sql` in the repo that matches
     exactly what was applied (idempotent DDL).
  5. Commit as:  chore(migrations): reconcile ledger for <name>

## Supabase tooling (MCP + agent skills)

Database work goes through the **Supabase MCP** — in this environment that is the
claude.ai "Supabase" connector, whose tools are namespaced `mcp__claude_ai_Supabase__*`
(`list_tables`, `list_migrations`, `apply_migration`, `execute_sql`, `get_advisors`,
`deploy_edge_function`, …). It is a per-user OAuth connector, not defined in any
`.mcp.json`/`settings.json`. **Do not add a second, standalone Supabase MCP server**: it
would duplicate every tool and hand you a fresh `apply_migration` path that bypasses the
gates below.

Two Supabase **agent skills** add procedural guidance. Install them locally with
`npx skills add supabase/agent-skills`; they land in the git-ignored `.agents/skills/`
(tracked in the untracked `skills-lock.json`), so each contributor installs their own —
they are not committed:
- `supabase` — Database, Auth, Edge Functions, Storage, Realtime guidance.
- `supabase-postgres-best-practices` — query optimization, schema design, RLS patterns.

**Whatever a tool or skill suggests, the rules above still bind.** No `apply_migration`
to production (migrations are applied out-of-band and reconciled — see *Migration
discipline (MANDATORY)* and *Ledger reconciliation*); `execute_sql` only for read-only
queries or non-schema backfills; every new `public` table needs RLS + a policy +
`REVOKE ALL ... FROM anon` (see *Database Migrations — Security Rules*).

## Build hygiene (pre-push hook + CI)

Render auto-deploys `main` on every push, so **every commit on `main` must build cleanly** — a broken build is a user-visible deploy failure.

**Activate the local pre-push hook (one-time, per clone):**

```bash
git config core.hooksPath .githooks
```

`.githooks/pre-push` runs `npm run build` in `frontend/` before any push that touches frontend files. If the build fails, the push is aborted. Skips automatically when the push contains no frontend changes.

**Preferred workflow:** feature branch → PR → CI (`.github/workflows/ci.yml` runs `frontend-build` + `backend-tests`) → merge → Render deploys. Pushing directly to `main` still works but bypasses PR review, so the pre-push hook is the only local safety net.

**Emergency bypass:** `git push --no-verify` skips the hook. Use sparingly — every avoided round-trip with Render is faster than every emergency bypass.

## Audit remediation workflow

A multi-stage remediation plan lives at `audit/REMEDIATION_PLAN.md` with a rolling log at `audit/STAGES.md` and per-stage re-audit docs at `audit/re-audit-stage-N-*.md`.

**Branch naming convention for audit remediation:** `audit/stage-N-<slug>` (e.g. `audit/stage-1-security`, `audit/stage-2-copy`). One branch per stage; one PR per stage; one re-audit doc per stage. Sub-stages use `audit/stage-Na-<slug>` (e.g. `audit/stage-8a-route-auth-ci`).

**System of record:** Each finding has a Notion AI Work Queue entry (DB id `7adc643a-c448-4a1a-ba80-e27e417f42d6`) with Priority + Complexity + Validation Criteria + Context Links back to the originating `audit/02-expert-*.md` file. Update Status as the work moves through `Ready for AI → AI in Progress → Human Review → Done`.

**Gate discipline:** No stage starts until the previous stage's PR is merged + canary clean. See `audit/REMEDIATION_PLAN.md` §"Universal stage protocol" for the per-stage checklist.

## Work Queue hygiene (two rules that keep the queue honest)

Audited 2026-08-12: of 26 items in **Human Review**, only 4 were finished work awaiting sign-off.
15 had no implementing commit at all. A status lane that is 58% phantom cannot be used to decide
what to work on, and every agent that reads it pays the cost.

**1. `Human Review` means the work SHIPPED and needs a human to check it. Nothing else.**

The lane filled up because it was being set when an Otto draft was *staged* — notes ending
*"Draft STAGED in Otto — not run, not published."* A staged draft is `Ready for AI`. A blocked one
is `Blocked`. Neither is a review state, because there is nothing to review.

Before moving anything to `Human Review`, name the artifact: a commit on `origin/main`, a merged
PR, or a file that exists. If you cannot, it is not ready for review.

**2. Never reuse the `[AIQ-nnnn]` subject-tag form for a cross-reference in a commit body.**

Three commits carry a tag whose diff is about something else entirely — `91a99eed` `[AIQ-1807]`,
`6b49d1a2` `[AIQ-1806]`, `85fac265` `[AIQ-1794]`. A `git log --grep` closure sweep marks all three
as shipped; two of the three tickets have no code at all.

The subject tag is a *claim of authorship over that ticket's deliverable*. In a body, refer to
other work as `AIQ-1807` or "see AIQ-1807" — plain, no brackets. Reserve the bracketed form for
the subject line of the commit that actually implements it.

**Corollary, learned the same day:** a docs-only commit bearing a ticket's id reads as progress in
the log and ships nothing. If a ticket's only commit is documentation, its status is not `Done` —
`AIQ-1794`'s merged document concludes that the fix the ticket prescribes *cannot work*, which is
a genuine and useful outcome, but it is not the ticket being finished.

**Verifying a closure:** check the file or the diff, never the commit subject alone. Tests are
often `unittest` classes, so `grep "^def test_"` returns 0 for a file full of them — use
`grep -nE "^class |    def test_"`.

## Behavioral Guidelines (Karpathy)

Source: https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. These bias toward caution over speed — use judgment for trivial tasks.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Design System

Read `DESIGN.md` (repo root) before any visual or UI change. It documents the shipped
system: navy `#0b2b43` (primary) + teal `#1f8e8b` (accent, used sparingly), Inter (UI/body)
+ JetBrains Mono (code/data), 8px spacing grid, the `frontend/src/components/antigravity/`
component library, and light/`[data-theme='dark']` theming. There is no purple/violet in
the brand. Prefer the `navy-*` / `accent-*` Tailwind classes or `--rp-*` CSS vars over
hardcoded hex literals. In QA mode, flag code that deviates from DESIGN.md.
