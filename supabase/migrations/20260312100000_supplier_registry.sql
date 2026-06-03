-- Supplier Registry: source of truth for recommendation matching and RFQ
-- Compatible with existing vendors: suppliers.vendor_id links to vendors for RFQ flow

begin;

-- NOTE: these three tables exist on prod as SQLAlchemy ORM-created tables (varchar
-- keys, untyped timestamps, text columns, no CHECK constraints, no vendors FK). The
-- original uuid CREATE below never took effect on prod — `if not exists` no-op'd over
-- the ORM tables. A fresh replay, however, has no pre-existing tables, so it must
-- reproduce prod's REAL shape — otherwise downstream FKs that reference suppliers(id)
-- with a varchar key (e.g. 20260524000002 matching_5a.assignment_outcomes.supplier_id)
-- fail with "incompatible types: character varying and uuid" (SQLSTATE 42804).
-- Reconstructed prod-as-oracle (live introspection 2026-06-03). Repo-only; prod no-ops.

-- A. suppliers
create table if not exists public.suppliers (
  id varchar primary key,
  name varchar not null,
  legal_name varchar null,
  status varchar not null,
  description text null,
  website varchar null,
  contact_email varchar null,
  contact_phone varchar null,
  languages_supported text null,
  verified boolean not null,
  vendor_id varchar null,
  created_at timestamp not null default now(),
  updated_at timestamp not null default now()
);

create index if not exists idx_suppliers_status on public.suppliers(status);
create index if not exists idx_suppliers_vendor_id on public.suppliers(vendor_id);

-- B. supplier_service_capabilities
create table if not exists public.supplier_service_capabilities (
  id varchar primary key,
  supplier_id varchar not null references public.suppliers(id) on delete cascade,
  service_category varchar not null,
  coverage_scope_type varchar not null,
  country_code varchar null,
  city_name varchar null,
  specialization_tags text null,
  min_budget numeric null,
  max_budget numeric null,
  family_support boolean not null,
  corporate_clients boolean not null,
  remote_support boolean not null,
  notes text null,
  created_at timestamp not null default now(),
  updated_at timestamp not null default now(),
  price_description text null
);

create index if not exists idx_supplier_capabilities_supplier on public.supplier_service_capabilities(supplier_id);
create index if not exists idx_supplier_capabilities_service on public.supplier_service_capabilities(service_category);
create index if not exists idx_supplier_capabilities_country on public.supplier_service_capabilities(country_code);
create index if not exists idx_supplier_capabilities_city on public.supplier_service_capabilities(city_name);

-- C. supplier_scoring_metadata (1:1 with supplier)
-- admin_score / manual_priority are added later by 20260407; price_range_* and
-- price_display exist on prod out-of-band (no migration) and are reconstructed here.
create table if not exists public.supplier_scoring_metadata (
  supplier_id varchar primary key references public.suppliers(id) on delete cascade,
  average_rating double precision null,
  review_count integer not null,
  response_sla_hours integer null,
  preferred_partner boolean not null,
  premium_partner boolean not null,
  last_verified_at timestamp null,
  created_at timestamp not null default now(),
  updated_at timestamp not null default now(),
  price_range_min_eur integer null,
  price_range_max_eur integer null,
  price_display text null
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
