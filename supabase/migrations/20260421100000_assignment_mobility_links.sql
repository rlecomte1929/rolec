-- Bridge: one live case_assignments row <-> one mobility_cases row (durable graph lane entry).
-- Allows pending-claim assignments (no employee auth user yet) to still own a mobility case.

begin;

alter table public.mobility_cases
  alter column employee_user_id drop not null;

create table public.assignment_mobility_links (
  id uuid primary key default gen_random_uuid(),
  assignment_id text not null
    references public.case_assignments (id) on delete cascade,
  mobility_case_id uuid not null
    references public.mobility_cases (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint assignment_mobility_links_assignment_id_key unique (assignment_id),
  constraint assignment_mobility_links_mobility_case_id_key unique (mobility_case_id)
);

create index idx_assignment_mobility_links_assignment_id
  on public.assignment_mobility_links (assignment_id);

comment on table public.assignment_mobility_links is
  '1:1 bridge from live case_assignments.id to mobility_cases.id; app creates rows idempotently.';

drop trigger if exists trg_assignment_mobility_links_updated on public.assignment_mobility_links;
create trigger trg_assignment_mobility_links_updated
  before update on public.assignment_mobility_links
  for each row execute function public.set_updated_at();

drop trigger if exists trg_audit_assignment_mobility_links on public.assignment_mobility_links;
create trigger trg_audit_assignment_mobility_links
  after insert or update or delete on public.assignment_mobility_links
  for each row execute function public.relopass_audit_row();

commit;
