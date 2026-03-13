-- Supplier Registry: source of truth for recommendation matching and RFQ
-- Compatible with existing vendors: suppliers.vendor_id links to vendors for RFQ flow

begin;

-- A. suppliers
create table if not exists public.suppliers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  legal_name text null,
  status text not null default 'active' check (status in ('active', 'inactive', 'draft')),
  description text null,
  website text null,
  contact_email text null,
  contact_phone text null,
  languages_supported text[] not null default '{}',
  verified boolean not null default false,
  vendor_id uuid null references public.vendors(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_suppliers_status on public.suppliers(status);
create index if not exists idx_suppliers_vendor_id on public.suppliers(vendor_id);

-- B. supplier_service_capabilities
create table if not exists public.supplier_service_capabilities (
  id uuid primary key default gen_random_uuid(),
  supplier_id uuid not null references public.suppliers(id) on delete cascade,
  service_category text not null,
  coverage_scope_type text not null default 'country' check (coverage_scope_type in ('global', 'country', 'city')),
  country_code text null,
  city_name text null,
  specialization_tags text[] not null default '{}',
  min_budget numeric null,
  max_budget numeric null,
  family_support boolean not null default false,
  corporate_clients boolean not null default false,
  remote_support boolean not null default false,
  notes text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_supplier_capabilities_supplier on public.supplier_service_capabilities(supplier_id);
create index if not exists idx_supplier_capabilities_service on public.supplier_service_capabilities(service_category);
create index if not exists idx_supplier_capabilities_country on public.supplier_service_capabilities(country_code);
create index if not exists idx_supplier_capabilities_city on public.supplier_service_capabilities(city_name);

-- C. supplier_scoring_metadata (1:1 with supplier)
create table if not exists public.supplier_scoring_metadata (
  supplier_id uuid primary key references public.suppliers(id) on delete cascade,
  average_rating numeric null,
  review_count int not null default 0,
  response_sla_hours int null,
  preferred_partner boolean not null default false,
  premium_partner boolean not null default false,
  last_verified_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- RLS
alter table public.suppliers enable row level security;
alter table public.supplier_service_capabilities enable row level security;
alter table public.supplier_scoring_metadata enable row level security;

-- Admin/service_role can manage; authenticated can read active
drop policy if exists suppliers_select on public.suppliers;
create policy suppliers_select on public.suppliers for select to authenticated
  using (status = 'active' or auth.jwt() ->> 'role' = 'service_role');

drop policy if exists suppliers_all on public.suppliers;
create policy suppliers_all on public.suppliers for all to service_role using (true) with check (true);

drop policy if exists supplier_capabilities_select on public.supplier_service_capabilities;
create policy supplier_capabilities_select on public.supplier_service_capabilities for select to authenticated using (true);

drop policy if exists supplier_capabilities_all on public.supplier_service_capabilities;
create policy supplier_capabilities_all on public.supplier_service_capabilities for all to service_role using (true) with check (true);

drop policy if exists supplier_scoring_select on public.supplier_scoring_metadata;
create policy supplier_scoring_select on public.supplier_scoring_metadata for select to authenticated using (true);

drop policy if exists supplier_scoring_all on public.supplier_scoring_metadata;
create policy supplier_scoring_all on public.supplier_scoring_metadata for all to service_role using (true) with check (true);

commit;
