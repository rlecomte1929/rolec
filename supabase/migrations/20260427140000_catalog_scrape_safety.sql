-- Cost-control surface for the catalog scraper (Phase 2b-secured).
--
-- Three tables:
--   1. catalog_destination_allowlist — admin-controlled list of (city, country)
--      pairs where HR is allowed to fire the LLM scraper. Off-allowlist HR
--      requests open a ticket (table 3) instead.
--   2. catalog_scrape_quota — per-company-per-day call counter, default cap
--      of 20 distinct (category, city) scrapes. Resets at midnight UTC.
--   3. catalog_destination_requests — ticket queue for HR-requested off-list
--      destinations. Admin approves → row is added to allowlist + the
--      requester's pending scrape can fire.

begin;

create table public.catalog_destination_allowlist (
  city text not null,
  country text not null,
  approved_by uuid,
  approved_at timestamptz not null default now(),
  notes text,
  primary key (city, country)
);

comment on table public.catalog_destination_allowlist is
  'Admin-curated list of (city, country) pairs where HR is allowed to fire the LLM catalog scraper. Anything off this list opens a ticket in catalog_destination_requests.';

create table public.catalog_scrape_quota (
  company_id uuid not null,
  day date not null,
  calls_made integer not null default 0,
  primary key (company_id, day)
);

comment on table public.catalog_scrape_quota is
  'Per-company per-day quota counter for HR-initiated catalog scrapes. Default cap = 20. Resets at midnight UTC.';

create table public.catalog_destination_requests (
  id uuid primary key default gen_random_uuid(),
  city text not null,
  country text not null,
  category text not null,
  requested_by uuid not null,
  company_id uuid not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  resolved_by uuid,
  resolved_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.catalog_destination_requests is
  'Tickets opened by HR when they ask the scraper to populate a destination not on the allowlist. Admin reviews + approves → row added to allowlist + the original (category) scrape auto-fires.';

create index idx_cdr_status on public.catalog_destination_requests (status, created_at desc);
create index idx_cdr_company on public.catalog_destination_requests (company_id, created_at desc);

create or replace function public.cdr_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_cdr_updated_at on public.catalog_destination_requests;
create trigger trg_cdr_updated_at
  before update on public.catalog_destination_requests
  for each row execute function public.cdr_set_updated_at();

-- Audit trail via existing relopass_audit_row().
drop trigger if exists trg_audit_cda on public.catalog_destination_allowlist;
create trigger trg_audit_cda
  after insert or update or delete on public.catalog_destination_allowlist
  for each row execute function public.relopass_audit_row();

drop trigger if exists trg_audit_cdr on public.catalog_destination_requests;
create trigger trg_audit_cdr
  after insert or update or delete on public.catalog_destination_requests
  for each row execute function public.relopass_audit_row();

-- RLS
alter table public.catalog_destination_allowlist enable row level security;
alter table public.catalog_scrape_quota enable row level security;
alter table public.catalog_destination_requests enable row level security;

-- Allowlist: any authenticated user reads (HR needs to know what's available);
-- admin only writes.
create policy cda_select_authenticated
  on public.catalog_destination_allowlist
  for select
  to authenticated
  using (true);

create policy cda_insert_admin
  on public.catalog_destination_allowlist
  for insert
  to authenticated
  with check (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
  );

create policy cda_update_admin
  on public.catalog_destination_allowlist
  for update
  to authenticated
  using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
  )
  with check (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
  );

create policy cda_delete_admin
  on public.catalog_destination_allowlist
  for delete
  to authenticated
  using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
  );

-- Quota: tenant-scoped read; backend service writes via the FastAPI tier
-- (no direct user write — keeps the counter trustworthy).
create policy csq_select_tenant
  on public.catalog_scrape_quota
  for select
  to authenticated
  using (
    company_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  );

-- Requests: HR sees their own company's tickets; admin sees all. Inserts
-- via the FastAPI HR endpoint; updates (resolve) via admin endpoint.
create policy cdr_select_tenant_or_admin
  on public.catalog_destination_requests
  for select
  to authenticated
  using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
    or company_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  );

create policy cdr_insert_hr
  on public.catalog_destination_requests
  for insert
  to authenticated
  with check (
    company_id in (
      select company_id from public.profiles
      where id = auth.uid() and role in ('HR', 'ADMIN')
    )
  );

create policy cdr_update_admin
  on public.catalog_destination_requests
  for update
  to authenticated
  using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
  )
  with check (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'ADMIN')
  );

commit;
