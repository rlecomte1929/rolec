-- Minimal graph-shaped relocation context: cases, people, documents, catalog, rules, evaluations

begin;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.mobility_cases (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  employee_user_id uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.case_people (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.mobility_cases (id) on delete cascade,
  role text not null
    check (role in (
      'employee',
      'spouse_partner',
      'dependent',
      'sponsor',
      'other'
    )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.case_documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.mobility_cases (id) on delete cascade,
  person_id uuid references public.case_people (id) on delete set null,
  document_status text not null default 'missing'
    check (document_status in (
      'missing',
      'requested',
      'uploaded',
      'under_review',
      'approved',
      'rejected',
      'waived'
    )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.requirements_catalog (
  id uuid primary key default gen_random_uuid(),
  requirement_code text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint requirements_catalog_requirement_code_key unique (requirement_code)
);

create table public.policy_rules (
  id uuid primary key default gen_random_uuid(),
  rule_code text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint policy_rules_rule_code_key unique (rule_code)
);

create table public.case_requirement_evaluations (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.mobility_cases (id) on delete cascade,
  person_id uuid references public.case_people (id) on delete set null,
  requirement_id uuid not null references public.requirements_catalog (id) on delete restrict,
  source_rule_id uuid references public.policy_rules (id) on delete set null,
  evaluation_status text not null default 'unknown'
    check (evaluation_status in (
      'unknown',
      'not_applicable',
      'pending',
      'met',
      'unmet',
      'waived'
    )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_mobility_cases_company_id on public.mobility_cases (company_id);
create index idx_mobility_cases_employee_user_id on public.mobility_cases (employee_user_id);
create index idx_case_people_case_id on public.case_people (case_id);
create index idx_case_documents_case_id on public.case_documents (case_id);
create index idx_case_documents_person_id on public.case_documents (person_id);
create index idx_case_requirement_evaluations_case_id on public.case_requirement_evaluations (case_id);
create index idx_case_requirement_evaluations_requirement_id on public.case_requirement_evaluations (requirement_id);

drop trigger if exists trg_mobility_cases_updated on public.mobility_cases;
create trigger trg_mobility_cases_updated
  before update on public.mobility_cases
  for each row execute function public.set_updated_at();

drop trigger if exists trg_case_people_updated on public.case_people;
create trigger trg_case_people_updated
  before update on public.case_people
  for each row execute function public.set_updated_at();

drop trigger if exists trg_case_documents_updated on public.case_documents;
create trigger trg_case_documents_updated
  before update on public.case_documents
  for each row execute function public.set_updated_at();

drop trigger if exists trg_requirements_catalog_updated on public.requirements_catalog;
create trigger trg_requirements_catalog_updated
  before update on public.requirements_catalog
  for each row execute function public.set_updated_at();

drop trigger if exists trg_policy_rules_updated on public.policy_rules;
create trigger trg_policy_rules_updated
  before update on public.policy_rules
  for each row execute function public.set_updated_at();

drop trigger if exists trg_case_requirement_evaluations_updated on public.case_requirement_evaluations;
create trigger trg_case_requirement_evaluations_updated
  before update on public.case_requirement_evaluations
  for each row execute function public.set_updated_at();

commit;
