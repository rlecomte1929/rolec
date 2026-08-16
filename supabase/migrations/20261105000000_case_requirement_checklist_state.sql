-- Per-case completion state for the Visa Checklist.
--
-- WHY A NEW TABLE
-- ---------------
-- The case cockpit's checklist needs "has this requirement been done for THIS case", and no
-- existing table holds it:
--   * `case_requirements_snapshots` is an immutable point-in-time blob (snapshot_json /
--     sources_json). It records what was required, never what was completed.
--   * `case_requirement_evaluations` records the engine's automated evaluation, not a human
--     ticking a box.
-- So this is the minimal state store the brief asks for: keyed by case + requirement, nothing
-- more. The requirement CONTENT still comes from `requirement_items` via
-- `requirements_builder.compute_case_requirements` — this table never duplicates it.
--
-- TYPES, DELIBERATELY
-- -------------------
-- `requirement_id` is TEXT, not uuid. `public.requirement_items.id` is `character varying`
-- (a uuid5 string written by the YAML seeder and the Otto promoter), so a uuid column here
-- would fail every insert with `42804 column is of type uuid but expression is of type
-- character varying` — the same mismatch that produced a production 500 in #1864.
--
-- `case_id` carries no FK. Case ids reach the API from three tables (`cases`,
-- `relocation_cases`, `case_assignments`) and are normalised by `resolve_case_ids` before they
-- get here; a FK to any single one of them would reject ids that are legitimately resolvable.
-- Tenant enforcement lives in the API layer (`_assert_case_access`), which is the same control
-- the requirements read itself goes through.

begin;

create table if not exists public.case_requirement_checklist_state (
  id             uuid primary key default gen_random_uuid(),
  case_id        uuid not null,
  requirement_id text not null,
  completed      boolean not null default false,
  completed_by   uuid,
  completed_at   timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  -- One row per (case, requirement): the API upserts on this key so a double-click or a
  -- retried request cannot create a second, contradictory state row.
  unique (case_id, requirement_id)
);

comment on table public.case_requirement_checklist_state is
  'Per-case completion state for requirement_items rendered in the case Visa Checklist. Content lives in requirement_items; this table holds only whether a case has completed each one.';

create index if not exists idx_crcs_case
  on public.case_requirement_checklist_state (case_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS — deny by default, mediated entirely by FastAPI.
--
-- Same shape as 20261104000000_counsel_attestation_phase1.sql: one explicit service_role
-- policy plus REVOKE on anon and authenticated. There is no supabase-js
-- `.from('case_requirement_checklist_state')` path in the frontend — the checklist reads and
-- writes through the backend, which already enforces case access — so a tenant-scoped
-- `authenticated` policy would be dead code. A policy-LESS public table would trip CLAUDE.md's
-- hard gate and scripts/check_rls_coverage.py, hence the explicit policy rather than none.
--
-- Replay-safe: DROP POLICY IF EXISTS before CREATE; REVOKE is a no-op when never granted.
-- ─────────────────────────────────────────────────────────────────────────────
alter table public.case_requirement_checklist_state enable row level security;

drop policy if exists case_requirement_checklist_state_service_role_all
  on public.case_requirement_checklist_state;
create policy case_requirement_checklist_state_service_role_all
  on public.case_requirement_checklist_state
  for all to service_role
  using (true) with check (true);

revoke all on public.case_requirement_checklist_state from anon;
revoke all on public.case_requirement_checklist_state from authenticated;

commit;
