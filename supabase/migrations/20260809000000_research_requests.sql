-- AIQ-1349 P2 — research_requests: customer-requested immigration research for an
-- uncovered corridor. Admin-approved (no charge yet; cost recorded for later
-- invoicing) → moves to in_progress for the P3 curation flow. Mirrors
-- catalog_destination_requests (table + triggers + tenant RLS). Idempotent.

begin;

create table if not exists public.research_requests (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  requester_user_id uuid not null,
  origin_country text,
  dest_country text not null,
  corridor text not null,
  purpose text,
  scope text,
  estimated_cost numeric,
  actual_cost numeric,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'in_progress', 'completed', 'rejected')),
  assigned_curator_user_id uuid,
  created_queue_item_id uuid,
  result_summary text,
  resolved_by uuid,
  resolved_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_rr_status on public.research_requests (status, created_at desc);
create index if not exists idx_rr_company on public.research_requests (company_id, created_at desc);
create index if not exists idx_rr_corridor on public.research_requests (corridor, status);

create or replace function public.rr_set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists trg_rr_updated_at on public.research_requests;
create trigger trg_rr_updated_at before update on public.research_requests
  for each row execute function public.rr_set_updated_at();

-- Audit trail (research_requests has an id PK, so relopass_audit_row works).
drop trigger if exists trg_audit_rr on public.research_requests;
create trigger trg_audit_rr after insert or update or delete on public.research_requests
  for each row execute function public.relopass_audit_row();

-- ── RLS (tenant-scoped; backend service-role bypasses, this is defense-in-depth) ──
alter table public.research_requests enable row level security;

drop policy if exists rr_insert_hr_or_employee on public.research_requests;
create policy rr_insert_hr_or_employee on public.research_requests
  for insert to authenticated
  with check (
    company_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role in ('HR', 'ADMIN', 'EMPLOYEE')
    )
  );

drop policy if exists rr_select_tenant_or_admin on public.research_requests;
create policy rr_select_tenant_or_admin on public.research_requests
  for select to authenticated
  using (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
    or company_id in (
      select company_id::uuid from public.profiles
      where id::uuid = auth.uid() and role in ('HR', 'EMPLOYEE')
    )
  );

drop policy if exists rr_update_admin_or_hr on public.research_requests;
create policy rr_update_admin_or_hr on public.research_requests
  for update to authenticated
  using (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
    or company_id in (
      select company_id::uuid from public.profiles where id::uuid = auth.uid() and role = 'HR'
    )
  )
  with check (
    exists (select 1 from public.profiles where id::uuid = auth.uid() and role = 'ADMIN')
    or company_id in (
      select company_id::uuid from public.profiles where id::uuid = auth.uid() and role = 'HR'
    )
  );

revoke all on public.research_requests from anon;

commit;
