# Migration drift inventory — DEFINITIVE (2026-06-02)

> **Supersedes** `audit/migration-drift-inventory-2026-06-01.md` (regex-based, acknowledged-unreliable). Ground truth here is `prod's supabase_migrations.schema_migrations` (the table Supabase uses to track applied migrations). Cross-referenced against `git ls-tree origin/main supabase/migrations/`.

## TL;DR

| Category | Count | Severity |
|----|----|----|
| **Hard drift** — applied to prod, no real repo file | **3** | Action-required (was 6; entries 1/2/5 resolved by #176, merge `5a58bf0d`) |
| **`_remote_stub` soft drift** — empty placeholder files paired by timestamp to prod migrations | **~80+** | **Structural — repo not replayable** |
| **Reverse drift** — repo file exists, never applied to prod | **13** | Mixed (entry 1 RESOLVED via #219; entry 12 RESOLVED in-session via #220 Option B; entry 11 DEFERRED — missing prerequisite; entry 10 DE dossier seed FIX AUTHORED in #221 & verified-by-chain-advancement but unmerged; **entry 13 `employee_profiles.case_id` is the NEW live replay blocker, surfaced when #221's fix advanced Preview past entry 10**; rest cleanup). **Key reframe: Supabase Preview red is a CHAIN of replay landmines, not a single bug — each fix reveals the next. Preview won't go green until the whole chain (10 → 13 → …) is drained.** |

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
| **10** | `20260507150000_de_dossier_questions.sql` | `20260507150000` | **🛠️ FIX AUTHORED (#221) — not merged** | **Schema drift** | New tracked item from #219 surfacing. `dossier_questions` table is created with columns (`destination_country`, `domain`, `options`, `is_mandatory`) at `20260228010000`, but the DE seed at `20260507150000` inserts using **phantom** columns (`destination`, `category`, `options_json`, `required`, `applies_if_json`) — which exist NOWHERE (not on prod, not in any migration; the version that actually seeded prod's 9 DE rows used the real columns and this repo file simply diverged). Fresh replay aborted here (`column "destination" … does not exist`, SQLSTATE 42703). GB (`20260507120000`) + FR (`20260507130000`) seeds use the original column names and replay clean; divergence started at DE. **Fix authored in PR #221 (branch `fix/de-dossier-replay`, Option D): no-op the broken file + replay-safe re-seed at `20260604300000` using the real columns, `ON CONFLICT (destination_country, question_key, version) DO NOTHING` (true no-op on prod's existing 9 rows). Pre-authorship verified: category→domain is a clean 1:1 against prod's 9 DE rows; unique key `(destination_country, question_key, version)` confirmed.** **Status: fix is CORRECT and VERIFIED-BY-CHAIN-ADVANCEMENT** — Supabase Preview on #221 no longer aborts at this timestamp; it now walks PAST May 7 and fails further down at the **next** landmine (entry 13, `employee_profiles.case_id`, May 18). **#221 is NOT merged**: per the run's decision tree, "Preview RED for a DIFFERENT error → STOP, document, do not merge." Preview cannot go green until the whole replay chain is drained, so #221 holds open behind entry 13. |
| 2 | `20260529100000_rce_extraction_agents.sql` | `20260529100000` | Cleanup | **B1: orphan** | Verify never-applied via MCP; if orphan, drop in a cleanup PR. |
| 3 | `*_policy_conflicts*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 4 | `*_policy_chunks_vector_index*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 5 | `*_employee_tiers*` | — | Cleanup | **B1: orphan** | Verify, drop (or backfill if actually live). |
| 6 | `*_ai_refusal_logs*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 7 | `*_canonical_policy_facts_tier*` | — | Cleanup | **B1: orphan** | Verify, drop. |
| 8 | `20260304*_policy_version_status.sql` | `20260304` | Naming inconsistency | **B1 likely / B3 possibly** | Cross-check whether prod has equivalent under a different name. |
| 9 | `20260305*_resolved_assignment_policies.sql` | `20260305` | Naming inconsistency | **B1 likely / B3 possibly** | Cross-check. |
| **11** | `20260601080000_ai_unit_economics.sql` (Parker Step G) | `20260601080000` | **🚨 Replay-blocking + functionality-blocking** | **Schema drift — missing prerequisite** | **Surfaced 2026-06-02 during #220 (Parker A–J) post-merge MCP apply; migration HELD/DEFERRED, not applied.** Sections 2+3 `ALTER TABLE public.policy_assistant_traces ADD COLUMN …` + build `mv_ai_unit_economics … FROM public.policy_assistant_traces`. **That table does not exist on prod** (`to_regclass` → null) and **has no creation path anywhere**: the file's header claim that `init_db()` bootstraps it is false for Postgres — `backend/database.py:1186` does `if not _is_sqlite: return` *before* the `CREATE TABLE policy_assistant_traces` block (line 2428), which the AIQ-383 comment explicitly marks "SQLite-only dev scaffolding"; no Supabase migration `CREATE TABLE`s it; no `_maybe_ensure_*` PG helper creates it. `ALTER TABLE` has no table-level `IF EXISTS`, so apply fails `relation … does not exist` and rolls back. Whole file held as one txn — partial apply of section 1 alone would orphan `ai_model_energy_profiles` with no consumer. **Side implications (pre-existing, not caused by #220):** the `admin_ai_unit_economics` endpoint reads this base table → already non-functional on prod; P5-8 trace writes have silently no-op'd on prod since P5-8 (writes are best-effort/swallowed). **Next action:** author a `policy_assistant_traces` table-creation migration with PG-grade types (UUID id, TIMESTAMPTZ, real numeric/int cols — not the SQLite `TEXT`/`REAL` scaffolding) + RLS hard gates, apply it, then re-apply migration 7 in a follow-up session. FK chain itself is clean (`ml_models`, `prompt_versions` both present; mig 7 declares no FKs). |
| **12** | `20260601100000_translation_cache.sql` (Parker Step I) | `20260601100000` | **✅ RESOLVED (during apply)** | **Schema drift — ORM/migration shape divergence** | **Surfaced 2026-06-02 during #220 post-merge MCP apply; reconciled in-session via Option B (DROP + clean re-apply).** Same root pattern as entry 11 (Parker assumes migrations are the sole source of truth, but a second runtime table-creation path interacts on Postgres) — but the **manifestation is the inverse**. Here the table was **already present on prod in a degraded shape**: `backend/app/db.py:19` runs `Base.metadata.create_all(bind=engine)` at boot, which created `translation_cache` from the `TranslationCache` ORM model (`backend/app/models.py:400`) **before** the migration ever ran. `create_all()` is `CREATE TABLE IF NOT EXISTS`-semantic, so the migration's `CREATE TABLE IF NOT EXISTS` silently no-op'd against the ORM-shaped table — leaving prod **without RLS, without the `domain`/`provider` CHECK constraints, and without the migration's exact column types**. The ORM docstring at `models.py:404` ("The Postgres table + RLS live in the migration; this ORM mapping is what the service/repo and test DB use") is wrong for Postgres: `create_all` runs there too and wins the race. **Reconciliation:** verified 0 rows + no inbound FKs, then atomic `DROP TABLE` + migration `apply_migration` in a single transaction (strictly safer than separate DROP-then-apply; mirrors the #176 clean-rebuild pattern). Post-apply verified: full migration shape landed (UUID PK, CHAR(5) langs, `domain`/`provider` CHECKs, RLS on + 2 policies `service_all`/`authenticated_read`, `authenticated:SELECT` grant only, both indexes, `case_assignments.preferred_language` ALTER column), anon smoke = 401. **Residual risk (flagged, not blocking):** `create_all()` will not *re-drop* the now-correct migration-shaped table on future boots (`IF NOT EXISTS` no-ops), so prod is stable — but the ORM model and the migration must be kept shape-aligned by hand, or a future `create_all` on a *fresh* DB (where it wins the race again) reintroduces the degraded shape. Long-term fix belongs with the entry-11 class: stop `create_all()` from running on Postgres (it's dev/test scaffolding, same as the `database.py:1186` guard) so migrations are the sole DDL authority. |

| **13** | `20260518120000_immigration_core_tables.sql` (IMM-01) | `20260518120000` | **🚨 Replay-blocking** | **Schema drift — apply-order ≠ file-order** | **Surfaced 2026-06-02 on PR #221's Supabase Preview, immediately downstream of the entry-10 DE fix** (the DE fix advanced the replay from May 7 to here). Fresh replay aborts at statement 3: `CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_profiles_case_employee ON public.employee_profiles(case_id, employee_id)` → `column "case_id" does not exist` (SQLSTATE 42703). **Root cause:** an earlier `employee_profiles` already exists from the Feb 21 baseline dump (`20260221105601_remote_schema.sql:167`, PK on `assignment_id`, **no `case_id`**). Migration A here opens with `CREATE TABLE IF NOT EXISTS public.employee_profiles (… case_id …)` which **silently no-ops** against that legacy table, then its `case_id` index fails. The proper fix already exists — `20260522170000_imm_employee_profiles_schema.sql` (migration B) RENAMEs the legacy table → `legacy_employee_profiles` and re-creates the full IMM-01 shape — **but B is 4 days later in the chain (May 22 > May 18), so on a fresh replay A dies before B can run.** **Prod is HEALTHY** (verified via MCP read-only): current `employee_profiles` carries `case_id,employee_id,id,org_id` + the index exists; `legacy_employee_profiles` exists with `assignment_id` — i.e. B's rename DID run on prod, so prod's apply order differed from file order. Only the repo replay is broken. **Same family as entries 1/10/12: a migration that assumes prod's out-of-band state and is not fresh-replayable.** **Next action (separate authorization, NOT done):** make migration A self-sufficient on a fresh DB — either (a) hoist B's RENAME-legacy step to the top of A (so A operates on a clean slate), or (b) no-op A's `employee_profiles` block and let B be the sole authority, guarding B's RENAME with `IF EXISTS`/a regclass check so it's also clean when no legacy table is present. Either way the unique index must only run against the new-shape table. |

Entries 3–9 are listed from CC's original recon; per-file verification + confirmation of orphan status is a **separate quick cleanup PR**, not in scope for this inventory. Entry 1 (`rls_error_tracking_harden`) is **separately important** and has its own follow-up note. **Entry 13 is the live blocker as of 2026-06-02**: it is the next replay landmine after the entry-10 DE fix and is what currently keeps Supabase Preview red.

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
