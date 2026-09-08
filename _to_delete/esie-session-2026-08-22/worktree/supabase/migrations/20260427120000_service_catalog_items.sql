-- Master catalog of service vendors per (category, city/country).
-- Phase 2a of the recommendations catalog routine: gives the scraper
-- (Phase 2c) a writable home and the admin a queryable surface.
--
-- Authority: ADMIN OWNS this table. HR sees rows but never writes here;
-- HR's selections live in a separate company_vendor_selections table
-- (Phase 2d). Employees never see this table directly.

begin;

create table if not exists public.service_catalog_items (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  -- Canonical city name as used by the recommendation plugins
  -- (e.g. "Munich", "Singapore"). Null for geo-agnostic categories
  -- whose rows apply everywhere.
  city text,
  country text,
  name text not null,
  -- Free-form attributes preserve whatever shape the legacy JSON
  -- datasets carry per category (curriculum, tuition_level, rating,
  -- etc.). Keeping it as jsonb avoids a per-category schema migration
  -- every time we add a field.
  attributes_json jsonb not null default '{}'::jsonb,
  source text not null default 'manual'
    check (source in ('scraper', 'manual', 'seed', 'hr_promoted')),
  active boolean not null default true,
  -- Original item_id from the JSON datasets (so the JSON→DB backfill
  -- is idempotent and re-runs replace-in-place rather than duplicating).
  external_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by_user_id uuid,
  unique (category, external_id)
);

comment on table public.service_catalog_items is
  'Admin-owned master catalog. Scraper writes here in Phase 2c. HR reads via company_vendor_selections (Phase 2d); employees never see this table directly.';

create index if not exists idx_service_catalog_items_cat_city on public.service_catalog_items (category, city) where active;
create index if not exists idx_service_catalog_items_cat_country on public.service_catalog_items (category, country) where active;
create index if not exists idx_service_catalog_items_source on public.service_catalog_items (source);

create or replace function public.service_catalog_items_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_service_catalog_items_updated_at on public.service_catalog_items;
create trigger trg_service_catalog_items_updated_at
  before update on public.service_catalog_items
  for each row execute function public.service_catalog_items_set_updated_at();

-- Audit trail via existing relopass_audit_row().
drop trigger if exists trg_audit_service_catalog_items on public.service_catalog_items;
create trigger trg_audit_service_catalog_items
  after insert or update or delete on public.service_catalog_items
  for each row execute function public.relopass_audit_row();

-- RLS: read for any authenticated caller (HR needs to see master items
-- to curate; employees never query this directly but can't be locked
-- out at the row level without complicating the curation join). Writes
-- restricted to admins; the FastAPI tier additionally gates the admin
-- write endpoints, this is belt-and-suspenders.
alter table public.service_catalog_items enable row level security;

create policy service_catalog_items_select_authenticated
  on public.service_catalog_items
  for select
  to authenticated
  using (true);

create policy service_catalog_items_insert_admin
  on public.service_catalog_items
  for insert
  to authenticated
  with check (
    exists (
      select 1 from public.profiles
      where id::uuid = auth.uid() and role = 'ADMIN'
    )
  );

create policy service_catalog_items_update_admin
  on public.service_catalog_items
  for update
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id::uuid = auth.uid() and role = 'ADMIN'
    )
  )
  with check (
    exists (
      select 1 from public.profiles
      where id::uuid = auth.uid() and role = 'ADMIN'
    )
  );

commit;
