-- Phase 1 Step 2: case_participants as case-scoped participant junction
-- No persons table yet; person_id is text (user id from auth/users).
-- Backfill from case_assignments (hr_user_id, employee_user_id).

begin;

-- =============================================================================
-- 1. Create case_participants table
-- =============================================================================
create table if not exists public.case_participants (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references public.wizard_cases(id) on delete cascade,
  person_id text not null,
  role text not null check (role in ('relocatee','hr_owner','hr_reviewer','observer')),
  invited_at timestamptz null,
  joined_at timestamptz null,
  created_at timestamptz not null default now(),
  unique(case_id, person_id, role)
);

create index if not exists idx_case_participants_case_id on public.case_participants (case_id);
create index if not exists idx_case_participants_person_id on public.case_participants (person_id);

comment on table public.case_participants is 'Case-scoped participant junction. Phase 1: person_id = user id.';

-- =============================================================================
-- 2. Backfill from case_assignments
-- =============================================================================
insert into public.case_participants (case_id, person_id, role, joined_at, created_at)
select
  ca.case_id,
  ca.hr_user_id,
  'hr_owner',
  now(),
  now()
from public.case_assignments ca
where ca.hr_user_id is not null
  and ca.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = ca.case_id)
on conflict (case_id, person_id, role) do nothing;

insert into public.case_participants (case_id, person_id, role, joined_at, created_at)
select
  ca.case_id,
  ca.employee_user_id::text,
  'relocatee',
  now(),
  now()
from public.case_assignments ca
where ca.employee_user_id is not null
  and ca.case_id is not null
  and exists (select 1 from public.wizard_cases wc where wc.id = ca.case_id)
on conflict (case_id, person_id, role) do nothing;

commit;
