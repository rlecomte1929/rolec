-- AIQ-756 backfill — public.immigration_cases
-- Prod-applied out-of-band (schema_migrations version 20260526071431, name
-- "immigration_cases") with no CREATE in the repo, so a fresh `supabase db
-- reset` / Supabase Preview diverges from prod. DDL below is prod-as-oracle
-- (information_schema + pg_constraint + pg_indexes + pg_policies, 2026-06-04).
-- Idempotent: CREATE TABLE IF NOT EXISTS + IF NOT EXISTS indexes + pg_policies
-- guards, so this is a clean no-op on prod (table already present) and a full
-- create on a fresh DB.
--
-- REPLAY-SAFE FK GUARD (2026-06-04): on prod public.relocation_cases.id is uuid
-- (matching case_id), but on a fresh baseline replay it is still text — a
-- pre-existing baseline-collision divergence (#224 class) not yet fixed for
-- relocation_cases. A hard FK here aborts replay with 42804 ("incompatible
-- types: uuid and text"). So the table is created WITHOUT the inline FK, and
-- the FK is added only when relocation_cases.id is actually uuid. On prod the
-- FK already exists (no-op); on a fresh DB it is skipped until the separate
-- relocation_cases id→uuid baseline fix lands. Tracked as a follow-up.

begin;

create table if not exists public.immigration_cases (
  id                       uuid        not null default gen_random_uuid(),
  case_id                  uuid        not null,
  corridor_from            text        not null,
  corridor_to              text        not null,
  permit_type              text        not null,
  partner_name             text,
  expected_submission_date date,
  expected_grant_date      date,
  permit_expiry_date       date,
  status                   text        not null default 'initiated'::text,
  document_statuses        jsonb       not null default '{}'::jsonb,
  created_by_hr_id         uuid,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  constraint immigration_cases_pkey primary key (id),
  constraint immigration_cases_permit_type_check
    check (permit_type = any (array['eu_blue_card'::text, 'work_permit'::text,
      'skilled_worker_visa'::text, 'eea_registration'::text, 'other'::text])),
  constraint immigration_cases_status_check
    check (status = any (array['initiated'::text, 'documents_collected'::text,
      'submitted'::text, 'under_review'::text, 'decision'::text, 'granted'::text]))
);

-- Replay-safe FK: only when relocation_cases.id is uuid (see header note).
do $$
begin
  if not exists (
        select 1 from pg_constraint
        where conname = 'immigration_cases_case_id_fkey'
          and conrelid = 'public.immigration_cases'::regclass)
     and (select data_type from information_schema.columns
          where table_schema = 'public' and table_name = 'relocation_cases'
            and column_name = 'id') = 'uuid'
  then
    alter table public.immigration_cases
      add constraint immigration_cases_case_id_fkey
      foreign key (case_id) references public.relocation_cases (id) on delete cascade;
  end if;
end $$;

create unique index if not exists immigration_cases_case_id_uidx
  on public.immigration_cases (case_id);
create index if not exists immigration_cases_status_idx
  on public.immigration_cases (status);

alter table public.immigration_cases enable row level security;

-- Prod policy: locked to the backend service role; anon + authenticated denied.
do $$
begin
  if not exists (select 1 from pg_policies
    where schemaname = 'public' and tablename = 'immigration_cases'
      and policyname = 'service_role_only') then
    create policy service_role_only on public.immigration_cases
      for all to anon, authenticated using (false);
  end if;
end $$;

revoke all on public.immigration_cases from anon;

commit;
