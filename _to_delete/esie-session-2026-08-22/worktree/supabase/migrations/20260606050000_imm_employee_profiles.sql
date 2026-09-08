-- AIQ-756-FU backfill — public.imm_employee_profiles (immigration PII vault)
-- Orphaned out-of-band table: created directly on prod, no in-repo CREATE, yet
-- ALTERed by the merged migration 20260606100000_imm18_retention_automation.sql
-- (ADD COLUMN anonymised_at) — so a fresh replay aborts there with 42P01.
-- Placed just before that migration. DDL is prod-as-oracle (2026-06-04), MINUS
-- the anonymised_at column (added by imm18 via ADD COLUMN IF NOT EXISTS, so the
-- end state matches prod). Text-id table, no FKs. Idempotent; no-op on prod.

begin;

create table if not exists public.imm_employee_profiles (
  id                    text not null default (gen_random_uuid())::text,
  case_id               text not null,
  employee_id           text not null,
  org_id                text not null,
  legal_first_name      text,
  legal_last_name       text,
  middle_names          text,
  date_of_birth         date,
  place_of_birth        text,
  nationality           text,
  second_nationality    text,
  gender                text,
  passport_number       text,
  passport_expiry       date,
  passport_issue_date   date,
  passport_country      text,
  passport_mrz_line1    text,
  passport_mrz_line2    text,
  existing_visa_type    text,
  existing_visa_expiry  date,
  prior_visa_refusals   boolean default false,
  current_address       jsonb,
  address_history       jsonb default '[]'::jsonb,
  employer_name         text,
  employer_reg_number   text,
  employer_address      jsonb,
  job_title             text,
  job_title_local       text,
  employment_start_date date,
  salary_amount         numeric,
  salary_currency       text default 'EUR'::text,
  contract_type         text,
  highest_qualification text,
  institution           text,
  graduation_year       integer,
  degree_anabin_status  text,
  marital_status        text,
  spouse_name           text,
  spouse_nationality    text,
  spouse_dob            date,
  dependents            jsonb default '[]'::jsonb,
  field_sources         jsonb default '{}'::jsonb,
  field_confidence      jsonb default '{}'::jsonb,
  field_conflicts       jsonb default '{}'::jsonb,
  consent_record_id     text,
  consent_timestamp     timestamptz,
  consent_version       text,
  consent_purposes      text[],
  retention_expires_at  timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint imm_employee_profiles_pkey primary key (id)
);

create unique index if not exists idx_imm_employee_profiles_case_employee
  on public.imm_employee_profiles (case_id, employee_id);
create index if not exists idx_imm_employee_profiles_case_id
  on public.imm_employee_profiles (case_id);
create index if not exists idx_imm_employee_profiles_org_id
  on public.imm_employee_profiles (org_id);
create index if not exists idx_imm_employee_profiles_retention
  on public.imm_employee_profiles (retention_expires_at) where (retention_expires_at is not null);

alter table public.imm_employee_profiles enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='imm_employee_profiles' and policyname='imm_profiles_employee_select') then
    create policy imm_profiles_employee_select on public.imm_employee_profiles
      for select to authenticated using (employee_id = (auth.uid())::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='imm_employee_profiles' and policyname='imm_profiles_employee_insert') then
    create policy imm_profiles_employee_insert on public.imm_employee_profiles
      for insert to authenticated with check (employee_id = (auth.uid())::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='imm_employee_profiles' and policyname='imm_profiles_employee_update') then
    create policy imm_profiles_employee_update on public.imm_employee_profiles
      for update to authenticated using (employee_id = (auth.uid())::text) with check (employee_id = (auth.uid())::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='imm_employee_profiles' and policyname='imm_profiles_hr_select') then
    create policy imm_profiles_hr_select on public.imm_employee_profiles
      for select to authenticated using (exists (
        select 1 from public.case_assignments ca
        where ca.case_id = imm_employee_profiles.case_id and ca.hr_user_id = (auth.uid())::text));
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='imm_employee_profiles' and policyname='imm_profiles_hr_update') then
    create policy imm_profiles_hr_update on public.imm_employee_profiles
      for update to authenticated using (exists (
        select 1 from public.case_assignments ca
        where ca.case_id = imm_employee_profiles.case_id and ca.hr_user_id = (auth.uid())::text));
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='imm_employee_profiles' and policyname='imm_profiles_service_role') then
    create policy imm_profiles_service_role on public.imm_employee_profiles
      for all to service_role using (true) with check (true);
  end if;
end $$;

revoke all on public.imm_employee_profiles from anon;

commit;
