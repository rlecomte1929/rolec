-- Exception requests: employee asks HR to allow a service estimate that exceeds policy cap.
-- T1.3 from the Sprint 2 execution plan.
--
-- 2026-05-29: retroactive cast added to ALL FOUR subqueries against public.profiles
-- (company_id::uuid, id::uuid) so this migration is replayable on a clean-slate
-- database. Prior to this edit, Supabase preview branches failed at the first
-- CREATE POLICY with `operator does not exist: text = uuid` because
-- public.profiles.id and public.profiles.company_id start as TEXT earlier in the
-- migration history. The follow-up 20260522150000_fix_exception_requests_rls_uuid_cast
-- migration drops and recreates these policies, so already-applied environments
-- converge to the same end state — this edit only affects fresh replays.

begin;

create table public.exception_requests (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.mobility_cases (id) on delete cascade,
  organization_id uuid not null,
  category text not null,
  requested_amount numeric(12, 2) not null check (requested_amount >= 0),
  cap_amount numeric(12, 2) not null check (cap_amount >= 0),
  currency text not null check (length(currency) = 3),
  reason text not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  hr_note text,
  requested_by_user_id uuid not null,
  resolved_by_user_id uuid,
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  updated_at timestamptz not null default now()
);

comment on table public.exception_requests is
  'Employee-initiated request to exceed an HR policy cap on a service estimate. HR resolves with status + optional note.';
comment on column public.exception_requests.organization_id is
  'Denormalized for tenant-isolation queries — must equal mobility_cases.company_id.';

create index idx_exception_requests_case on public.exception_requests (case_id, created_at desc);
create index idx_exception_requests_org_status on public.exception_requests (organization_id, status, created_at desc);
create index idx_exception_requests_requester on public.exception_requests (requested_by_user_id);

-- updated_at trigger using the same pattern as mobility_cases
create or replace function public.exception_requests_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_exception_requests_updated_at on public.exception_requests;
create trigger trg_exception_requests_updated_at
  before update on public.exception_requests
  for each row execute function public.exception_requests_set_updated_at();

-- Audit trail: cover insert/update/delete via the existing relopass_audit_row() trigger.
drop trigger if exists trg_audit_exception_requests on public.exception_requests;
create trigger trg_audit_exception_requests
  after insert or update or delete on public.exception_requests
  for each row execute function public.relopass_audit_row();

-- RLS: tenant-scoped read for HR + employee; insert by employee on their own case;
-- update by HR only. Mirrors the patterns in earlier mobility-graph migrations.
alter table public.exception_requests enable row level security;

create policy exception_requests_select_tenant
  on public.exception_requests
  for select
  to authenticated
  using (
    organization_id in (
      select company_id::uuid from public.profiles where id::uuid = auth.uid()
    )
  );

create policy exception_requests_insert_employee
  on public.exception_requests
  for insert
  to authenticated
  with check (
    requested_by_user_id = auth.uid()
    and organization_id in (
      select company_id::uuid from public.profiles where id::uuid = auth.uid()
    )
  );

create policy exception_requests_update_hr
  on public.exception_requests
  for update
  to authenticated
  using (
    organization_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role in ('HR', 'ADMIN')
    )
  )
  with check (
    organization_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role in ('HR', 'ADMIN')
    )
  );

commit;
