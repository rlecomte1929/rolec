-- Timeline workflow: case_milestones + milestone_links
-- Provides time-based structure for relocation cases

begin;

create table if not exists public.case_milestones (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  canonical_case_id text,
  milestone_type text not null,
  title text not null,
  description text,
  target_date date,
  actual_date date,
  status text not null default 'pending'
    check (status in ('pending','in_progress','done','skipped','overdue')),
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_case_milestones_case_id on public.case_milestones(case_id);
create index if not exists idx_case_milestones_canonical on public.case_milestones(canonical_case_id);
create index if not exists idx_case_milestones_sort on public.case_milestones(case_id, sort_order);

create table if not exists public.milestone_links (
  id uuid primary key default gen_random_uuid(),
  milestone_id uuid not null references public.case_milestones(id) on delete cascade,
  linked_entity_type text not null,
  linked_entity_id text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_milestone_links_milestone on public.milestone_links(milestone_id);

alter table public.case_milestones enable row level security;
alter table public.milestone_links enable row level security;

-- RLS: case_assignments employee/HR can access milestones for their cases
drop policy if exists case_milestones_select on public.case_milestones;
create policy case_milestones_select on public.case_milestones for select to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where (ca.case_id = case_milestones.case_id or ca.case_id = case_milestones.canonical_case_id)
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists case_milestones_all on public.case_milestones;
create policy case_milestones_all on public.case_milestones for all to service_role using (true) with check (true);

drop policy if exists milestone_links_select on public.milestone_links;
create policy milestone_links_select on public.milestone_links for select to authenticated
  using (
    exists (
      select 1 from public.case_milestones cm
      join public.case_assignments ca on (ca.case_id = cm.case_id or ca.case_id = cm.canonical_case_id)
      where cm.id = milestone_links.milestone_id
        and (ca.employee_user_id = auth.uid()::text or ca.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists milestone_links_all on public.milestone_links;
create policy milestone_links_all on public.milestone_links for all to service_role using (true) with check (true);

commit;
