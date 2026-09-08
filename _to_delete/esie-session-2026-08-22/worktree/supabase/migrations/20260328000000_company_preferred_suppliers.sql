-- Company-level preferred suppliers for HR
-- HR can mark suppliers as preferred for their company; employees see "Preferred by your company"

begin;

create table if not exists public.company_preferred_suppliers (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  supplier_id text not null,
  service_category text null,
  priority_rank int not null default 0,
  status text not null default 'active' check (status in ('active', 'inactive')),
  notes text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_company_preferred_suppliers_company on public.company_preferred_suppliers(company_id);
create index if not exists idx_company_preferred_suppliers_supplier on public.company_preferred_suppliers(supplier_id);
create unique index if not exists idx_company_preferred_suppliers_unique
  on public.company_preferred_suppliers(company_id, supplier_id, coalesce(service_category, ''));

alter table public.company_preferred_suppliers enable row level security;

drop policy if exists company_preferred_suppliers_admin on public.company_preferred_suppliers;
create policy company_preferred_suppliers_admin on public.company_preferred_suppliers
  for all to service_role using (true) with check (true);

commit;
