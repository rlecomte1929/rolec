-- HR's per-company vendor curation (Phase 2d).
-- The middle tier of the authority chain:
--   ADMIN owns service_catalog_items (Phase 2a).
--   HR picks rows here per (company, category, destination).
--   Employee API (Phase 2c+) joins through this table.
--
-- A row carries either:
--   master_item_id  → an admin master row HR has decided about (selected on/off), or
--   custom_item_json → a vendor HR added on their own that isn't in the master.
-- Exactly one of the two is set; CHECK below enforces.

begin;

create table public.company_vendor_selections (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  category text not null,
  destination_city text,
  country text,
  master_item_id uuid references public.service_catalog_items (id) on delete set null,
  custom_item_json jsonb,
  selected boolean not null default true,
  display_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by_user_id uuid,
  -- Exactly one of master_item_id / custom_item_json must be set.
  constraint cvs_one_source check (
    (master_item_id is not null and custom_item_json is null)
    or (master_item_id is null and custom_item_json is not null)
  ),
  -- Don't allow duplicate decisions on the same master row per
  -- (company, category, city); HR toggles in place.
  unique (company_id, category, destination_city, master_item_id)
);

comment on table public.company_vendor_selections is
  'HR per-company curation: which admin master vendors are visible to their employees, plus HR-added custom vendors. Employees never see the raw master.';

create index idx_cvs_company_cat_city
  on public.company_vendor_selections (company_id, category, destination_city)
  where selected;
create index idx_cvs_master_item
  on public.company_vendor_selections (master_item_id)
  where master_item_id is not null;

create or replace function public.cvs_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_cvs_updated_at on public.company_vendor_selections;
create trigger trg_cvs_updated_at
  before update on public.company_vendor_selections
  for each row execute function public.cvs_set_updated_at();

drop trigger if exists trg_audit_cvs on public.company_vendor_selections;
create trigger trg_audit_cvs
  after insert or update or delete on public.company_vendor_selections
  for each row execute function public.relopass_audit_row();

alter table public.company_vendor_selections enable row level security;

-- Tenant-scoped read: HR sees only their own company's curation.
create policy cvs_select_tenant
  on public.company_vendor_selections
  for select
  to authenticated
  using (
    company_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  );

-- HR-only writes (Admin too via the FastAPI tier passing through HR auth deps).
create policy cvs_insert_hr
  on public.company_vendor_selections
  for insert
  to authenticated
  with check (
    company_id in (
      select company_id from public.profiles
      where id = auth.uid() and role in ('HR', 'ADMIN')
    )
  );

create policy cvs_update_hr
  on public.company_vendor_selections
  for update
  to authenticated
  using (
    company_id in (
      select company_id from public.profiles
      where id = auth.uid() and role in ('HR', 'ADMIN')
    )
  )
  with check (
    company_id in (
      select company_id from public.profiles
      where id = auth.uid() and role in ('HR', 'ADMIN')
    )
  );

create policy cvs_delete_hr
  on public.company_vendor_selections
  for delete
  to authenticated
  using (
    company_id in (
      select company_id from public.profiles
      where id = auth.uid() and role in ('HR', 'ADMIN')
    )
  );

commit;
