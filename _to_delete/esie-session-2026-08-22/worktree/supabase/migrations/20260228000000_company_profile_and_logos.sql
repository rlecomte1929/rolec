-- Company Profile: extended companies table for name, logo, defaults
-- Auth is enforced by backend; RLS optional when using Supabase Auth directly.

begin;

alter table public.companies
  add column if not exists legal_name text,
  add column if not exists website text,
  add column if not exists hq_city text,
  add column if not exists industry text,
  add column if not exists logo_url text,
  add column if not exists brand_color text,
  add column if not exists updated_at timestamptz default now(),
  add column if not exists default_destination_country text,
  add column if not exists support_email text,
  add column if not exists default_working_location text;

update public.companies set updated_at = now() where updated_at is null;

create or replace function public.set_company_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists companies_updated_at on public.companies;
create trigger companies_updated_at
  before update on public.companies
  for each row execute function public.set_company_updated_at();

create index if not exists idx_companies_name_lower on public.companies (lower(name));

commit;
