# ReloPass — Implementation Execution Guide
> Companion to `ReloPass_Implementation_Plan_for_Claude_Code.md`
> Written after codebase inspection. Corrects stack assumptions from the plan.
> Last updated: 2026-04-26

---

## Actual Stack (vs plan assumptions)

| Plan assumed | Reality |
|---|---|
| TypeScript / Next.js API routes (`src/pages/api/`) | **Python / FastAPI** — backend in `backend/app/` |
| Prisma schema (`prisma/schema.prisma`) | **Supabase migrations** — 97 SQL files in `supabase/migrations/` |
| BullMQ / Inngest scheduler | **PostgreSQL triggers** — task risk recalc via `trg_relocation_tasks_recalc_risk` |
| `src/lib/audit.ts` | `backend/services/audit_log_service.py` — already exists |
| REST guesses | FastAPI routers in `backend/app/routers/` |

The plan's logic is sound. The file paths just need translating. This guide does that.

---

## Pre-Flight: What the Spikes Already Know

Before you run a single prompt, the codebase inspection answered 3 of the 5 spikes partially:

### Spike 2 (due_date) — ANSWERED: EXISTS ✅
- `relocation_tasks` table has a `due_date` column (confirmed in migration `20260227000001_hr_command_center_risk_rpc.sql`)
- There is already a `trg_relocation_tasks_recalc_risk` PostgreSQL trigger that fires on task update
- The Command Center RPC already queries `due_date` and computes overdue days
- **Implication for T1.2:** Task.due_date is NOT a build — it's a verify-and-done. Run Spike 2 in ~30 min to confirm the trigger actually fires end-to-end, then close it.

### Spike 5 (Audit Log) — PARTIALLY ANSWERED
- `backend/services/audit_log_service.py` exists with `insert_audit_log()` function
- Tests exist: `test_audit_log_service.py` and `test_policy_assistant_audit.py`
- Postgres-level triggers via `relopass_audit_row()` cover `mobility_cases`, `case_people`, `case_documents`
- **What's unknown:** Whether every state-changing API endpoint calls `insert_audit_log()`. That's the verification Spike 5 needs to do. Likely 80%+ already covered.

### Spike 3 (contract_type / move_type) — NOT YET FOUND
- No `contract_type` or `move_type` fields found in migrations search
- Either stored on a table not yet checked, or absent (which would make T2.1 a pure build)
- Run Spike 3 properly to confirm — this one is still open.

### Spike 4 (Family/spouse) — NOT YET CHECKED
- Run as designed in the plan.

### Spike 1 (Destination depth) — NOT YET CHECKED
- Run as designed — this is mostly content team work.

---

## How to Execute Each Task

### The workflow (same every time)

```
1. Open Claude Code in terminal: cd ~/Documents/GitHub/rolec && claude
2. Paste the starter prompt (corrected version below, or from the plan)
3. CC explores first — review its findings before it touches anything
4. Greenlight the approach
5. CC implements + tests
6. Run acceptance criteria as test plan
7. Commit, move to next task
```

### Golden rule from the plan (keep this)
> **No task ships without verifying audit_log captures the action.**
> If you find an action that doesn't call `insert_audit_log()`, fix it as part of the task.

---

## Corrected Spike Starter Prompts (actual file paths)

### Spike 5 — Tenant Isolation + Audit Log (START HERE)

```
Read backend/services/audit_log_service.py in full.
Read backend/app/auth_deps.py in full.
Read backend/app/routers/cases.py and backend/app/routers/admin.py.
Read backend/tests/test_audit_log_service.py.

Then:
Step 1: List every state-changing endpoint in all routers under backend/app/routers/.
For each, confirm: does it call insert_audit_log()? (yes/no/partial)

Step 2: Check tenant isolation. In auth_deps.py, how is organization_id
scoped on queries? Can a user from org A access data from org B through
any endpoint?

Step 3: Check the Supabase Postgres-level triggers — search migrations/
for relopass_audit_row() and list which tables it covers.

Step 4: Report gaps with severity: existential (cross-tenant leak) /
high (action not logged) / cosmetic (metadata missing).

Do NOT implement fixes yet — just verify and report.
```

### Spike 2 — due_date (30 minutes, likely pre-answered)

```
Read supabase/migrations/20260227000001_hr_command_center_risk_rpc.sql.
Read supabase/migrations/20260227000000_hr_command_center.sql.

Step 1: Confirm relocation_tasks has a due_date column. List its type and constraints.
Step 2: Confirm trg_relocation_tasks_recalc_risk trigger exists and fires on UPDATE.
Step 3: Check whether any code computes "assignment_end_date - 90 days" to seed due_date.
Step 4: Check whether the Command Center frontend renders overdue task count.

Output: 1-page verification report. Is due_date wired end-to-end, or just in DB schema?
```

### Spike 3 — contract_type / move_type

```
Step 1: Search all Supabase migrations for contract_type, move_type fields.
Step 2: Search backend/app/ for any reference to contract_type or move_type.
Step 3: If found: trace how it flows through plan generation, policy application,
services catalog, and resources surfacing.
Step 4: If not found: report "absent" and estimate effort to add move_type discriminator
across these subsystems:
  - backend/app/routers/cases.py (case creation)
  - backend/agents/ (plan generation logic)
  - backend/app/recommendations/ (engine + plugins)
  - frontend services catalog display

Output: present/absent + effort estimate if absent.
```

### Spike 4 — Family / spouse propagation

```
Step 1: Search supabase/migrations for family_members or case_family table. List fields.
Look for spouse_wants_to_work or wants_to_work field.
Step 2: Search backend/ for reads of that field.
Step 3: For each expected consumer (resources filter, services, policy, recommendations),
confirm: reads the field or ignores it?
Step 4: Report gap list.
```

### Spike 1 — Destination Data Depth

```
Step 1: Query (or read seed files) to list all destinations with content.
Check: backend/app/recommendations/datasets/ and supabase/migrations for seed data.
Step 2: For each destination, count movers, schools, neighborhoods, resources by category.
Step 3: Score each 0-5 against Singapore as reference.
Step 4: Recommend top 2-3 for MVP positioning. List what's missing for parity.
```

---

## Tier 1 Corrected Task Pointers

### T1.1 — Audit Log Gap Remediation
- Main service: `backend/services/audit_log_service.py`
- Existing tests: `backend/tests/test_audit_log_service.py`
- Routers to audit: `backend/app/routers/` (all 13 files)
- Schema: search `supabase/migrations/` for `audit_logs` table definition

### T1.2 — due_date + Date Triggers
- Schema: `supabase/migrations/20260227000001_hr_command_center_risk_rpc.sql`
- Tasks table: `supabase/migrations/20260227000000_hr_command_center.sql`
- (Likely already done — Spike 2 will confirm)

### T1.3 — ExceptionRequest model
- Skeleton exists: `backend/app/models.py` line 184 has `EXCEPTION = "exception"` status
- `backend/app/schemas.py` line 142 same
- Build point: the full ExceptionRequest entity, API endpoints, and workflow

### T1.4 — FX / currency
- Currency fields exist on multiple tables (policy comparison, services, RFQ)
- Search `supabase/migrations/` for `currency` to map all tables involved
- Build point: FX rate lookup, conversion display, estimate currency normalization

### T1.5 — Estimate Review (3-5 weeks, depends on T1.3 + T1.4)
- Largest single task. Don't start until T1.3 and T1.4 are merged.
- Split into 3 PRs: calc engine, UI shell, HR view + tenant-configurable threshold

### T1.6 — Employee Dashboard (independent, can run in parallel)
- Frontend: `frontend/src/` — find employee-facing routes
- No backend dependencies blocking this

### T1.7–T1.11 — Quick wins
- T1.7 paused status: check `backend/app/models.py` for case status enum
- T1.9 hide RFQ: search frontend for RFQ component
- T1.10 dev tooling strip: search for debug/dev flags
- T1.11 UUID cleanup: grep for numeric IDs in URLs

---

## Execution Order (wall-clock optimized)

```
Day 1 morning:   Spike 5 (existential risk — do this before anything else)
Day 1 afternoon: Spike 2 (30 min — likely just confirms due_date exists)
                 Spike 3 (start reading, report by end of day)
Week 1:          Spike 4, Spike 1 (parallel, mostly reading/querying)
                 T1.1 if Spike 5 found gaps (start immediately)
Week 2+:         T1.2 → T1.3 → T1.4 → T1.5 (sequenced)
                 T1.6 in parallel (independent)
                 T1.7, T1.9, T1.10, T1.11 as quick wins between big tasks
```

---

## Cross-Cutting PR Checklist (apply to every task)

From CC1-CC5 in the plan — treat as required PR review items:

- [ ] **CC1 Tenant isolation:** Every new query scoped to `organization_id`
- [ ] **CC2 Audit log:** New state-changing action calls `insert_audit_log()`
- [ ] **CC3 Test coverage:** Happy path + at least one edge case test
- [ ] **CC4 Friendly errors:** No raw stack traces surfaced to users
- [ ] **CC5 Performance:** No new N+1 queries; check query plans on new joins

---

## Key Files Quick Reference

| What | Where |
|---|---|
| Case creation/update | `backend/app/routers/cases.py` |
| Auth + tenant scoping | `backend/app/auth_deps.py` |
| Audit log service | `backend/services/audit_log_service.py` |
| Recommendations engine | `backend/app/recommendations/engine.py` + `plugins/` |
| Policy engine | `backend/app/routers/policy_canonical.py` |
| Admin routers | `backend/app/routers/admin*.py` (9 files) |
| Database schema | `supabase/migrations/` (97 migration files) |
| Frontend | `frontend/src/` |
| This plan | `ReloPass_Implementation_Plan_for_Claude_Code.md` |
| Original audit | `ReloPass_Audit_Final_Synthesis_INTERNAL.md` |
| Investor cut | `audit-docs/ReloPass_Audit_Investor_Cut.md` |
