# Migration drift inventory — 2026-06-01

**Filed:** end of session, follow-up to the #176 attempt which surfaced `rce.policy_gaps` and `rce.case_artefacts` as drift cases (tables on prod with no repo migration that creates them).

## TL;DR

- **Prod tables surveyed:** 287 (excluding system/extension schemas).
- **Literal drift count (prod tables with no `CREATE TABLE` matched in `supabase/migrations/` on origin/main): 47** — **but this number is NOT definitive.** The regex extraction has confirmed false-positives (see Caveat). Treat 47 as an upper bound.
- **Reverse drift (repo `CREATE TABLE` with no prod table): 14** — includes the whole `relocation_navigator.*` schema (4 tables, superseded by the move to `public`) + dropped/renamed tables.
- **Actionable, confirmed-sourceless tables (no `CREATE TABLE` anywhere in `backend/` or `supabase/` — verified by ripgrep):**
  - `rce.policy_gaps`, `rce.case_artefacts` (the #176 pattern)
  - `public.providers`, `public.immigration_cases`, `public.hris_connections`, `public.agent_runs`, `public.translation_cache`, `public.prescreening_results` (spot-checked; almost certainly more in the 47)
  These exist on prod via **history drift** — applied (likely via MCP `apply_migration` or since-deleted files), with no committed repo source. A fresh `supabase db reset` would NOT create them.

## ⚠️ Caveat — the regex method is not reliable enough to be "definitive"

The method (grep `CREATE TABLE` out of `supabase/migrations/`, diff against `pg_tables`) has **false-positives**: e.g. `roadmap_steps` IS created by `supabase/migrations/20260520000000_platform_redesign_schema.sql`, but the extraction regex missed it (multiline / formatting variance), so it was wrongly flagged as drift. Conversely the public schema is created across **three** mechanisms — `supabase/migrations/`, `backend/alembic/versions/`, and `backend/database.py` `init_db()` (128 raw `CREATE TABLE` statements) — so "drift vs supabase-migrations alone" structurally overcounts. Reliably attributing all 287 tables by regex is a rabbit hole and was stopped per the 15-case hard stop.

## ✅ Recommended method for tomorrow (authoritative, not regex)

Two reliable signals, either of which beats regex:
1. **Migration-history diff:** compare prod's `supabase_migrations.schema_migrations` (every applied version) against the migration *filenames* in the repo. Versions in prod history with no repo file = the exact set of drift-causing migrations. This directly finds the `rce.policy_gaps`/`policy_assistant_chunks`/etc. history-only applies.
2. **Schema-reset diff:** apply all repo migrations to a scratch Supabase branch (`create_branch` → it replays migrations), then diff its `pg_tables` against prod. Anything on prod but not on the fresh branch = true drift. This is the definitive test and also validates replayability.

## Counts (with the caveat above)

- Prod tables: 287
- Repo `CREATE TABLE` (supabase/migrations, regex-extracted): 254
- Literal drift (upper bound): **47** = 2 `rce.*` + 44 `public.*` + 1 `supabase_migrations.schema_migrations` (system table, ignore)
- Reverse drift: **14**

## Drift candidates (literal 47, upper bound — verify with the authoritative method)

**rce.\* (2) — confirmed genuine, the #176 pattern:** `rce.policy_gaps`, `rce.case_artefacts`

**public.\* (44)** — mixed. Confirmed-sourceless spot-checks: `providers`, `immigration_cases`, `hris_connections`, `agent_runs`, `translation_cache`, `prescreening_results`. Known false-positive: `roadmap_steps` (has a migration). Full list in `/tmp/drift2.txt` at session time; re-derive with the authoritative method before acting. Others in the set: `ai_spend_requests`, `assignment_audit_log`, `benefits_templates`, `case_alerts`, `case_assignment_id`, `case_budget_lines`, `document_uploads`, `form_prefill_instances`, `hr_notifications`, `hr_profiles`, `hris_field_mappings`, `hris_sync_log`, `imm_employee_profiles`, `immigration_advisors`, `industry_benchmarks`, `legacy_employee_profiles`, `pet_restrictions`, `policy_audit_log`, `policy_categories`, `policy_values`, `preferred_advisors`, `prospect_candidates`, `provider_invites`, `provider_messages`, `provider_tasks`, `relocation_policies`, `relocation_profiles`, `requirement_research_jobs`, `rfq_requests`, `roadmap_gap_questions`, `roadmap_generation_jobs`, `task_templates`, `workspace_stats`.

## Reverse drift — repo `CREATE TABLE` with no prod table (14)

`public.ai_refusal_logs`, `public.employee_cap_overrides`, `public.employee_tiers`, `public.policy_assistant_chunks`, `public.policy_chunks`, `public.policy_conflicts`, `public.policy_feedback`, `public.policy_review_queue`, `rce.agent_versions`, `rce.extraction_agents`, `relocation_navigator.relocation_artifacts`, `relocation_navigator.relocation_cases`, `relocation_navigator.relocation_runs`, `relocation_navigator.relocation_sources`.

Mostly safe (a table that doesn't exist can't cause runtime bugs; it confuses replay). The `relocation_navigator.*` set is a schema that was moved to `public` (migration `relocation_navigator_move_to_public`). `policy_chunks`/`policy_assistant_chunks`/`ai_refusal_logs` look dropped/renamed.

## Recommended next actions (bundle with #176 / #209 reconciliation)

1. Run the **authoritative method** (history-diff or schema-reset-diff) to get the definitive drift set — don't act on the regex list.
2. For each confirmed drift table: decide canonical source — commit a `CREATE TABLE IF NOT EXISTS` migration matching prod's *actual* schema (mind the policy-name/posture mismatch that bit #176 — see `daytime-run-stuck.md`), OR document it as intentionally code-managed (`database.py init_db`).
3. The `rce.*` cases are the urgent ones (pure-migration-managed; fresh reset breaks without them). The legacy `public.*` ones are lower-priority (the app's `init_db()` and alembic cover most of them at startup).
