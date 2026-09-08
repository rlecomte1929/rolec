# Claude Code Launch Prompt — Supplier Catalog Build
_Use this as your opening message in a Claude Code plan-mode session._
_Paste everything between the dashes into Claude Code._

---

## HOW TO USE

1. Open Claude Code in the repo root: `claude` (or via your IDE)
2. Enter plan mode: type `/plan` before sending, or prefix the message with "Plan:"
3. Paste the prompt below
4. Review the plan Claude Code produces — approve or request changes
5. Once approved, Claude Code executes gap by gap

Run **one session per gap** (GAP 0 + GAP 1 can be one session since they're parallel).
Use `claude-sonnet-5` for GAP 0–4, switch to `claude-opus-4-8` for GAP 5–6.

---

## THE PROMPT

```
Read the following files before doing anything else — in this order:

1. CLAUDE.md (project instructions — mandatory, contains hard rules)
2. docs/supplier-catalog-spec.md (the full build spec with audit findings and gap definitions)

Do not write any code until I approve your plan.

---

CONTEXT

You are working on ReloPass — a corporate relocation SaaS (TypeScript/React frontend + Python/FastAPI backend + Supabase/Postgres). The repo layout, architecture, and hard rules are all in CLAUDE.md. Read it fully before planning.

The spec at docs/supplier-catalog-spec.md documents:
- An audit of what already exists in the codebase (Part 1)
- Six numbered gaps to build (GAP 0 through GAP 6, Part 2)
- Build order, tool recommendations, and validation checklists (Parts 3 and 4)

---

YOUR TASK FOR THIS SESSION

Plan the implementation of [INSERT: "GAP 0 and GAP 1" OR "GAP 2 and GAP 3" OR "GAP 4" OR "GAP 5" OR "GAP 6"].

Read the spec's description of those gaps carefully. Then produce a plan that covers:

1. EVERY file you will create or modify — full path, one line saying what changes
2. The exact migration filename (with timestamp) and the DDL it will contain
3. Which functions/endpoints are new vs modified, and what their signatures look like
4. The dual-router registration steps (backend/main.py AND backend/app/main.py) for any new router
5. The TypeScript types that need updating in the frontend
6. The test cases you will write to satisfy the gap's acceptance criteria
7. The verification commands you will run at the end

Do not produce any code in the plan — file paths, function signatures, and SQL column names only.

---

NON-NEGOTIABLE CONSTRAINTS (from CLAUDE.md — do not skip any)

DUAL ROUTER REGISTRATION (hardest rule):
Every new or updated router must be registered in BOTH:
  - backend/app/main.py  (modular app — for tests and future prod)
  - backend/main.py      (primary entry point — what Render actually boots)
After registration, verify with:
  python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<your-prefix>' in r.path))"
If the route does not appear in that output, prod will 404/405. This has caused three production incidents.

RLS HARD GATE:
Every new table must have ALL THREE:
  1. ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;
  2. At least one CREATE POLICY (scoped to the correct tenant boundary)
  3. REVOKE ALL ON public.<table> FROM anon;
Missing any of these fails review — do not merge without them.

TYPE SAFETY:
Run `cd frontend && npx tsc --noEmit` after every frontend change.
Zero type errors required before marking any task complete.

TESTS:
Run `cd backend && pytest` after every backend change.
New behavior requires new tests. Specifically:
  - A pending capability must NOT appear in recommendation output (test required)
  - An approved capability MUST appear in recommendation output (test required)

DATABASE MIGRATIONS:
Never apply migrations via MCP apply_migration during implementation.
Create the .sql file in supabase/migrations/<timestamp>_<name>.sql.
Use idempotent DDL (IF NOT EXISTS, ON CONFLICT DO NOTHING).
Timestamp format: YYYYMMDDHHMMSS

EXISTING PATTERNS TO FOLLOW:
- New suppliers router patterns: backend/app/routers/suppliers.py
- New catalog admin patterns: backend/app/routers/admin_catalog.py
- Migration RLS pattern: supabase/migrations/20260312100000_supplier_registry.sql
- Seeding pattern: supabase/migrations/20260518100000_vendor_directory_extension.sql
- Frontend admin page pattern: frontend/src/pages/admin/AdminSupplierDetail.tsx
- Audit logging pattern: backend/app/services/audit_log_service.py

---

WHAT NOT TO DO

- Do not write any code, SQL, or TypeScript in the plan — names and paths only
- Do not modify any file outside the scope of the gap being planned
- Do not "improve" adjacent code that isn't broken
- Do not add abstractions, flexibility, or error handling beyond what the spec requires
- Do not register a router in only one of the two required files
- Do not create a new table without RLS

---

PLAN OUTPUT FORMAT

Produce your plan in this structure:

## Summary
One paragraph: what this gap achieves and why the order matters.

## Files to create
- `path/to/file.py` — what it contains

## Files to modify
- `path/to/file.py` — what changes (existing function names affected)

## Migration
- Filename: `supabase/migrations/<timestamp>_<name>.sql`
- Tables: list new columns / tables
- RLS policies: list each policy and which role it applies to
- Backfill: any UPDATE statements needed for existing rows

## API surface
- New endpoints: METHOD /path — auth requirement — request/response shape
- Modified endpoints: what changes in existing response shapes

## Frontend changes
- Components created or modified
- Route additions to App.tsx / routes.ts
- TypeScript types added or changed

## Tests
- List each test case by name and what it asserts

## Verification sequence
- The exact commands to run in order to confirm the gap is complete

---

Begin by confirming you have read both files, then produce the plan.
```

---

## NOTES FOR ROMAIN

**Adjusting the scope line:**
Change `[INSERT: ...]` to the gap(s) for this session. Suggested sessions:

| Session | Gaps | Model |
|---|---|---|
| 1 | GAP 0 and GAP 1 | claude-sonnet-5 |
| 2 | GAP 2 and GAP 3 | claude-sonnet-5 |
| 3 | GAP 4 | claude-sonnet-5 |
| 4 | GAP 6 | claude-opus-4-8 |
| 5 | GAP 5 | claude-opus-4-8 |

**Switching models in Claude Code:**
```bash
# Start a session with a specific model
claude --model claude-sonnet-5
claude --model claude-opus-4-8
```

**If Claude Code tries to write code during plan mode:**
Interrupt and remind it: "Plan only — no code. List file paths and function signatures only."

**After plan approval:**
Type `go` or `proceed` to start implementation. Claude Code will execute gap by gap and pause at each verification step.
