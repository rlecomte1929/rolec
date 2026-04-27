-- Per-case persisted Services-flow state for the employee wizard.
-- Stores selected_services / answers / recommendations / shortlist / display_currency
-- as a single jsonb blob keyed on case_id, so the employee can step away and
-- come back to the same Estimate Review without rebuilding their package.

begin;

create table public.services_state (
  case_id uuid primary key,
  organization_id uuid not null,
  state_json jsonb not null,
  updated_at timestamptz not null default now(),
  updated_by_user_id uuid
);

comment on table public.services_state is
  'Per-case snapshot of the employee Services-flow wizard (services + answers + shortlist). One row per case_id; upserted on save.';

create index idx_services_state_org on public.services_state (organization_id);

-- Audit trail via existing relopass_audit_row() trigger.
drop trigger if exists trg_audit_services_state on public.services_state;
create trigger trg_audit_services_state
  after insert or update or delete on public.services_state
  for each row execute function public.relopass_audit_row();

alter table public.services_state enable row level security;

create policy services_state_select_tenant
  on public.services_state
  for select
  to authenticated
  using (
    organization_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  );

create policy services_state_upsert_tenant
  on public.services_state
  for insert
  to authenticated
  with check (
    organization_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  );

create policy services_state_update_tenant
  on public.services_state
  for update
  to authenticated
  using (
    organization_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  )
  with check (
    organization_id in (
      select company_id from public.profiles where id = auth.uid()
    )
  );

commit;
