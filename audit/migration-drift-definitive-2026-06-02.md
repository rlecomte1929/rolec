# Migration drift inventory — DEFINITIVE (2026-06-02)

> **Supersedes** `audit/migration-drift-inventory-2026-06-01.md` (regex-based, acknowledged-unreliable). Ground truth here is `prod's supabase_migrations.schema_migrations` (the table Supabase uses to track applied migrations). Cross-referenced against `git ls-tree origin/main supabase/migrations/`.

## TL;DR

| Category | Count | Severity |
|----|----|----|
| **Hard drift** — applied to prod, no real repo file | **3** | Action-required (was 6; entries 1/2/5 resolved by #176, merge `5a58bf0d`) |
| **`_remote_stub` soft drift** — empty placeholder files paired by timestamp to prod migrations | **~80+** | **Structural — repo not replayable** |
| **Reverse drift** — repo file exists, never applied to prod | **10** | Mixed (entry 1 RESOLVED via #219; 1 newly-surfaced replay-blocking case — DE dossier seed, entry 10; rest cleanup) |

**Headline:** The `_remote_stub` pattern means a fresh `supabase db reset` produces a schema that is **substantially different from prod**. The hard-drift cases are not the main event — they are a small clean-up *of a much larger pattern*. See the structural-finding section below.

> **Update 2026-06-02:** Hard-drift entries **1, 2, and 5 are now resolved** — backfilled by PR #176 (merge `5a58bf0d78d795a3aeeefdd43d4516c5601c07a7`) via the combined idempotent migration `20260604100000_rce_policy_gaps_and_case_artefacts_with_service_role_hardening.sql`, applied to prod and verified (tables present, only `*_service_role_only` policies, no anon/authenticated grants, anon smoke = 406). Hard-drift count: **6 → 3**. Remaining: entries 3 (`public_agent_runs`), 4 (`enable_rls_tenant_tables`), 6 (`bucket_hardening_sec006`).

## Structural finding: the `_remote_stub` pattern

`supabase/migrations/` on `origin/main` contains ~80+ files named `<TS>_remote_stub.sql` whose **timestamps** exactly match prod-applied migrations under different real names. Examples:

| Repo file (origin/main) | Prod entry at same timestamp |
|----|----|
| `20260426124828_remote_stub.sql` | `error_tracking_tables` |
| `20260513*_remote_stub.sql` (multiple) | Various policy/HR/case migrations |
| `20260519*_remote_stub.sql` (multiple) | Various |
| `20260520*_remote_stub.sql` (multiple) | Various |

These stubs were committed as placeholders when the actual migrations were applied out-of-band (likely via the Supabase Dashboard SQL editor, the CLAUDE.md-flagged anti-pattern). The stubs **contain no SQL** — they exist purely so the timestamp sequence appears continuous.

**Replay consequence:** running `supabase db reset` against a clean DB executes the stubs (no-op) and arrives at a schema **missing every table/policy/grant** that the corresponding prod migrations applied. The migration system as it stands is **non-replayable end-to-end**.

**Not actionable in this session.** Backfilling the stubs is a tomorrow-grade project — for each one, the canonical prod statements need to be extracted from `supabase_migrations.schema_migrations` and committed to the repo (replacing the stub). Estimated scope: 80+ files × ~5-15 min review each = a multi-day deliberate session.

**Mitigation today:** new migrations follow the recent pattern (full SQL committed, applied via MCP, name in repo matches prod). The drift is bounded — it doesn't grow with new work; it only persists for historical migrations.

## Hard drift table — prod-applied, no repo file

| # | Prod version (apply-time) | Migration name (prod) | What it does | Classification | Action |
|---|----|----|----|----|----|
| ~~1~~ | ~~`20260529125415`~~ | ~~`rce_policy_gaps`~~ | ~~`CREATE TABLE rce.policy_gaps`~~ | **✅ RESOLVED** | Backfilled by #176 (`5a58bf0d`) → `20260604100000_…service_role_hardening.sql` |
| ~~2~~ | ~~`20260529125813`~~ | ~~`rce_case_artefacts`~~ | ~~`CREATE TABLE rce.case_artefacts`~~ | **✅ RESOLVED** | Backfilled by #176 (`5a58bf0d`) → same migration |
| 3 | `20260529223952` | `public_agent_runs` | `CREATE TABLE IF NOT EXISTS public.agent_runs` (used by agent-run telemetry; already idempotent) | **C1: prod-spec adopt** | Standalone backfill PR (low priority — table already in use, idempotent on replay) |
| 4 | `20260530095017` | `20260531010000_enable_rls_tenant_tables` | `ENABLE ROW LEVEL SECURITY` on 8 tenant tables (`employee_tasks`, `quote_requests`, `case_readiness*`, `readiness_templates*`) + policies | **C1: prod-spec adopt** | Standalone backfill PR (security-critical for replay correctness) |
| ~~5~~ | ~~`20260530111216`~~ | ~~`20260531020000_rce_service_role_only`~~ | ~~`DO $$` block — service-role-only hardening for `rce.*`~~ | **✅ RESOLVED (for policy_gaps + case_artefacts)** | The `*_service_role_only` policies for these two tables are now in repo via #176 (`5a58bf0d`). The broader `DO $$` loop over *all* `rce.*` tables remains un-backfilled for other tables, but the canonical policy convention is now sourced in-repo. |
| 6 | `20260530114300` | `bucket_hardening_sec006` | `UPDATE storage.buckets SET public = false, file_size_limit = 20971520, allowed_mime_types = …` for `hr-policies`, `form-templates`, etc. | **C1: prod-spec adopt** | Standalone backfill PR (security-critical) |

### Rename hypothesis (`enable_rls_tenant_tables` ↔ `rls_policy_hr_domain`) — DISPROVEN

CC-original recon flagged "prod ts `20260531010000`; repo has `rls_policy_hr_domain` at same timestamp — likely a rename." **Investigation refutes that.** Prod actually has **two distinct migrations** at near-timestamps:

| Apply-time | Prod name | What it does | Repo state |
|----|----|----|----|
| `20260530095017` | `20260531010000_enable_rls_tenant_tables` | Enables RLS on 8 tenant tables + policies | **Missing** (file name contains `20260531010000` prefix but it's the migration's own self-titled name) |
| `20260530104529` | `rls_policy_hr_domain` | Defines `hr_company_ids()`, `policy_version_in_company_scope()`, applies RLS to policy/HR domain | Present at repo path `20260531010000_rls_policy_hr_domain.sql` (different content from above) |

The repo file `20260531010000_rls_policy_hr_domain.sql` matches the **second** prod entry. The **first** (`enable_rls_tenant_tables`) is genuinely missing — confirming entry 4 in the hard-drift table.

## Reverse drift table — repo file, never applied to prod (by name)

| # | Repo file | Repo timestamp | Severity | Classification | Action |
|---|----|----|----|----|----|
| ~~1~~ | ~~`20260530000000_rls_error_tracking_harden.sql`~~ | ~~`20260530000000`~~ | **✅ RESOLVED** | **B-URGENT (done)** | Replay landmine removed via #219 (merge `5e1790fbd773ea161835ece073d0fc2be58c9d81`): file no-op'd + replay-safe recreation at `20260604200000`. Preview remains red due to an earlier DE dossier seed drift (separate issue, file `20260507150000_de_dossier_questions.sql`, tracked as entry 10 below). |
| **10** | `20260507150000_de_dossier_questions.sql` | `20260507150000` | **🚨 Replay-blocking** | **Schema drift** | New tracked item from #219 surfacing. `dossier_questions` table is created with columns (`destination_country`, `domain`, `options`, `is_mandatory`) at `20260228010000`, but the DE seed at `20260507150000` inserts using evolved columns (`destination`, `category`, `options_json`, `required`, `applies_if_json`) added to prod via out-of-band ALTER with no repo migration. Fresh replay aborts here (`column "destination" … does not exist`, SQLSTATE 42703). Same structural drift pattern as the `_remote_stub` cases. GB (`20260507120000`) + FR (`20260507130000`) seeds use the original column names and replay clean; divergence starts at DE. |
| 2 | `20260529100000_rce_extraction_agents.sql` | `20260529100000` | Cleanup | **B1: orphan** | Verify never-applied via MCP; if orphan, drop in a cleanup PR. |
| 3 | `*_policy_conflicts*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 4 | `*_policy_chunks_vector_index*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 5 | `*_employee_tiers*` | — | Cleanup | **B1: orphan** | Verify, drop (or backfill if actually live). |
| 6 | `*_ai_refusal_logs*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 7 | `*_canonical_policy_facts_tier*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 8 | `20260304*_policy_version_status.sql` | `20260304` | Naming inconsistency | **B1 likely / B3 possibly** | Cross-check whether prod has equivalent under a different name. |
| 9 | `20260305*_resolved_assignment_policies.sql` | `20260305` | Naming inconsistency | **B1 likely / B3 possibly** | Cross-check. |

Entries 3–9 are listed from CC's original recon; per-file verification + confirmation of orphan status is a **separate quick cleanup PR**, not in scope for this inventory. Entry 1 (`rls_error_tracking_harden`) is **separately important** and has its own follow-up note.

## Out of scope for this inventory

- **#209's 8 stale duplicate-named migrations.** Those are a `audit/parker-integration` *branch* state problem, not a prod-vs-main drift problem. Will be reconciled when #209 is taken on; see `audit/pr-209-triage.md` for that plan.
- **`_remote_stub` backfill.** Structural problem flagged above; deliberately deferred.
- **Per-file verification of reverse-drift entries 3–9.** Quick cleanup, not part of this session.

## What this unblocks

1. **#176 reconciliation** — fully concrete; see `audit/176-resolution-plan-2026-06-02.md`. The combined `rce.policy_gaps` + `rce.case_artefacts` table creation **plus** the service-role-only hardening must all live in a single new migration to be replay-safe.
2. **`rls_error_tracking_harden` landmine** — diagnosed and fix options documented in `audit/194-replay-landmine-2026-06-02.md`.

## Methodology note (for next time)

Authoritative drift inventory requires comparing **name keys** between prod's `supabase_migrations.schema_migrations` and repo filenames — NOT regex-parsing `CREATE TABLE` statements (yesterday's method, which produced inflated counts and false positives like `roadmap_steps`). The two reliable joins are:

- **Match by name suffix** (the `<TS>_<name>.sql` portion) — catches the rce.* hard-drift cases.
- **Match by timestamp** — catches the `_remote_stub` soft drift.

A name appears in **both** sets ⇒ that migration exists in repo AND has been applied (clean).
A name appears in **prod only** ⇒ hard drift.
A name appears in **repo only** ⇒ reverse drift.
A repo timestamp matches a prod timestamp **but the names differ** ⇒ either a rename, a stub, or two adjacent-time migrations. Verify content to disambiguate (the `enable_rls_tenant_tables` ↔ `rls_policy_hr_domain` case here).
