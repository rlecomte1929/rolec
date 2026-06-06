-- Tracks "an employee viewed a category for a destination but HR hadn't
-- curated it yet." Used by the HR Vendors page to surface demand so HR
-- knows what their employees are waiting on.
--
-- Rolling-forward: we keep one row per (company_id, category, destination_city)
-- and bump last_seen_at + demand_count on every empty-state hit. The HR
-- query is a simple SELECT — no aggregation pain at read time.

begin;

create table if not exists public.catalog_employee_demand (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  category text not null,
  destination_city text,
  destination_country text,
  -- Last employee user_id who saw the empty state (so we can show the
  -- requester to HR, e.g. "Edith Employee is waiting on this"); not
  -- a fan-out, just the most recent.
  last_seen_by_user_id uuid,
  last_seen_at timestamptz not null default now(),
  -- How many empty-state hits we've recorded for this combo. Helps HR
  -- prioritize: 50 hits across the company → fix this first.
  demand_count integer not null default 1,
  created_at timestamptz not null default now(),
  unique (company_id, category, destination_city)
);

comment on table public.catalog_employee_demand is
  'Demand signal — when an employee hits the "HR is finalizing" empty state, we upsert here. HR Vendors page reads this to show what employees are waiting on.';

create index if not exists idx_ced_company on public.catalog_employee_demand (company_id, last_seen_at desc);

create or replace function public.ced_set_updated_at()
returns trigger language plpgsql as $$
begin
  return new;
end;
$$;

-- Audit trail (mostly for debugging — these rows aren't security-sensitive).
drop trigger if exists trg_audit_ced on public.catalog_employee_demand;
create trigger trg_audit_ced
  after insert or update or delete on public.catalog_employee_demand
  for each row execute function public.relopass_audit_row();

alter table public.catalog_employee_demand enable row level security;

-- Tenant-scoped read for HR/Admin; backend writes via FastAPI tier with
-- elevated privileges (RPC layer); employees never query this directly.
create policy ced_select_tenant_or_admin
  on public.catalog_employee_demand
  for select
  to authenticated
  using (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role in ('HR', 'ADMIN'))
    and (
      exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
      or company_id in (select company_id::uuid from public.profiles where id::uuid = auth.uid())
    )
  );

commit;
