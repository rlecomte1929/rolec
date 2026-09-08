-- Canonical identity: company-scoped employee contacts (pre-auth) + assignment claim invites.
-- HR assign no longer creates auth users; signup only checks public.users.

begin;

create table if not exists public.employee_contacts (
  id text primary key,
  company_id text not null references public.companies(id) on delete restrict,
  invite_key text not null,
  email_normalized text,
  first_name text,
  last_name text,
  linked_auth_user_id text references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint employee_contacts_company_invite_unique unique (company_id, invite_key)
);

create index if not exists idx_employee_contacts_company on public.employee_contacts(company_id);
create index if not exists idx_employee_contacts_invite_key on public.employee_contacts(invite_key);
create index if not exists idx_employee_contacts_linked_user on public.employee_contacts(linked_auth_user_id);

create table if not exists public.assignment_claim_invites (
  id text primary key,
  assignment_id text not null references public.case_assignments(id) on delete cascade,
  employee_contact_id text not null references public.employee_contacts(id) on delete cascade,
  email_normalized text,
  token text not null,
  status text not null default 'pending' check (status in ('pending', 'claimed', 'revoked')),
  claimed_by_user_id text references public.users(id) on delete set null,
  claimed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint assignment_claim_invites_token_unique unique (token)
);

create index if not exists idx_assignment_claim_invites_assignment on public.assignment_claim_invites(assignment_id);
create index if not exists idx_assignment_claim_invites_contact on public.assignment_claim_invites(employee_contact_id);
create index if not exists idx_assignment_claim_invites_status on public.assignment_claim_invites(status);

alter table public.case_assignments
  add column if not exists employee_contact_id text references public.employee_contacts(id) on delete set null;

create index if not exists idx_case_assignments_employee_contact on public.case_assignments(employee_contact_id);

alter table public.employee_contacts enable row level security;
alter table public.assignment_claim_invites enable row level security;

drop policy if exists employee_contacts_all on public.employee_contacts;
create policy employee_contacts_all on public.employee_contacts for all to service_role using (true) with check (true);

drop policy if exists assignment_claim_invites_all on public.assignment_claim_invites;
create policy assignment_claim_invites_all on public.assignment_claim_invites for all to service_role using (true) with check (true);

commit;

-- Backfill: run application `Database._backfill_employee_contacts()` after deploy (SQLite + Postgres), or one-off SQL from ops.
