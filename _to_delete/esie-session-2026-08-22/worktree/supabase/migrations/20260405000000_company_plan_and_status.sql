-- Company plan tier and status for admin control and feature gating.
-- Safe to run on existing companies table.

begin;

alter table public.companies
  add column if not exists status text default 'active',
  add column if not exists plan_tier text default 'low',
  add column if not exists hr_seat_limit integer,
  add column if not exists employee_seat_limit integer;

-- Constrain plan_tier to known values (optional; comment out if you prefer app-level only)
alter table public.companies
  drop constraint if exists companies_plan_tier_check;
alter table public.companies
  add constraint companies_plan_tier_check
  check (plan_tier is null or plan_tier in ('low', 'medium', 'premium'));

-- Optional: constrain status
alter table public.companies
  drop constraint if exists companies_status_check;
alter table public.companies
  add constraint companies_status_check
  check (status is null or status in ('active', 'inactive', 'archived'));

update public.companies set status = 'active' where status is null;
update public.companies set plan_tier = 'low' where plan_tier is null;

create index if not exists idx_companies_status on public.companies (status);
create index if not exists idx_companies_plan_tier on public.companies (plan_tier);

commit;
