-- Profiles: status for admin deactivation and reconciliation.
-- company_id already exists; status defaults to 'active'.

begin;

alter table public.profiles
  add column if not exists status text default 'active';

alter table public.profiles
  drop constraint if exists profiles_status_check;
alter table public.profiles
  add constraint profiles_status_check
  check (status is null or status in ('active', 'inactive'));

update public.profiles set status = 'active' where status is null;

create index if not exists idx_profiles_status on public.profiles (status);
create index if not exists idx_profiles_company_id on public.profiles (company_id);

commit;
