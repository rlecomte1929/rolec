-- Phase 1 Step 4: Add canonical_case_id to key operational tables.
-- Additive bridge step. Do not remove legacy case_id. Do not force non-null.
-- Backfill: canonical_case_id = case_id where case_id exists in wizard_cases.

begin;

-- =============================================================================
-- 1. Add canonical_case_id column to each table (if not present)
-- =============================================================================

alter table public.case_assignments add column if not exists canonical_case_id text null;
alter table public.case_events add column if not exists canonical_case_id text null;
alter table public.case_participants add column if not exists canonical_case_id text null;
alter table public.case_evidence add column if not exists canonical_case_id text null;
alter table public.case_requirements_snapshots add column if not exists canonical_case_id text null;
alter table public.case_feedback add column if not exists canonical_case_id text null;
alter table public.case_services add column if not exists canonical_case_id text null;
alter table public.case_service_answers add column if not exists canonical_case_id text null;
alter table public.case_resource_preferences add column if not exists canonical_case_id text null;
alter table public.rfqs add column if not exists canonical_case_id text null;
alter table public.dossier_answers add column if not exists canonical_case_id text null;
alter table public.dossier_case_questions add column if not exists canonical_case_id text null;
alter table public.dossier_case_answers add column if not exists canonical_case_id text null;
alter table public.dossier_source_suggestions add column if not exists canonical_case_id text null;
alter table public.relocation_guidance_packs add column if not exists canonical_case_id text null;
alter table public.relocation_trace_events add column if not exists canonical_case_id text null;

-- =============================================================================
-- 2. Backfill: canonical_case_id = case_id where case_id exists in wizard_cases
-- =============================================================================

update public.case_assignments ca
set canonical_case_id = ca.case_id::text
where ca.canonical_case_id is null and ca.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = ca.case_id::text);

update public.case_events t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_participants t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_evidence t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_requirements_snapshots t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_feedback t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_services t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_service_answers t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.case_resource_preferences t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.rfqs t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.dossier_answers t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.dossier_case_questions t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.dossier_case_answers t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.dossier_source_suggestions t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.relocation_guidance_packs t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

update public.relocation_trace_events t
set canonical_case_id = t.case_id::text
where t.canonical_case_id is null and t.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = t.case_id::text);

-- =============================================================================
-- 3. Indexes on canonical_case_id for most important tables
-- =============================================================================

create index if not exists idx_case_assignments_canonical_case_id on public.case_assignments (canonical_case_id);
create index if not exists idx_case_events_canonical_case_id on public.case_events (canonical_case_id);
create index if not exists idx_case_participants_canonical_case_id on public.case_participants (canonical_case_id);
create index if not exists idx_case_evidence_canonical_case_id on public.case_evidence (canonical_case_id);
create index if not exists idx_rfqs_canonical_case_id on public.rfqs (canonical_case_id);
create index if not exists idx_relocation_guidance_packs_canonical_case_id on public.relocation_guidance_packs (canonical_case_id);

commit;
