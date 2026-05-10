begin;

create table if not exists public.case_services (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  assignment_id text not null,
  service_key text not null,
  category text not null,
  selected boolean not null default true,
  estimated_cost numeric null,
  currency text null default 'EUR',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (case_id, service_key)
);

create index if not exists idx_case_services_assignment_id
  on public.case_services (assignment_id);

create index if not exists idx_case_services_case_id
  on public.case_services (case_id);

create table if not exists public.case_service_answers (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  service_key text not null,
  answers jsonb not null,
  updated_at timestamptz default now(),
  unique (case_id, service_key)
);

create index if not exists idx_case_service_answers_case_id
  on public.case_service_answers (case_id);

commit;
