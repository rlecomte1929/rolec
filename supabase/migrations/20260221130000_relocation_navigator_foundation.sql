-- Relocation Navigator foundation (schema-first, additive).

create schema if not exists relocation_navigator;

create table relocation_navigator.relocation_cases (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  user_id uuid null,
  org_id uuid null,
  status text not null default 'draft',
  origin_country text null,
  destination_country text null,
  move_date date null,
  employment_type text null,
  employer_country text null,
  has_corporate_tax_support boolean not null default false,
  works_remote boolean null,
  notes text null,
  missing_fields jsonb not null default '[]'::jsonb
);

create index relocation_cases_user_id_idx
  on relocation_navigator.relocation_cases (user_id);

create index relocation_cases_org_id_idx
  on relocation_navigator.relocation_cases (org_id);

create index relocation_cases_status_idx
  on relocation_navigator.relocation_cases (status);

create table relocation_navigator.relocation_runs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  case_id uuid not null references relocation_navigator.relocation_cases (id) on delete cascade,
  run_type text not null,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  model_provider text null,
  model_name text null,
  tokens_in integer null,
  tokens_out integer null,
  cost_estimate numeric null,
  error text null
);

create index relocation_runs_case_id_created_at_idx
  on relocation_navigator.relocation_runs (case_id, created_at desc);

create index relocation_runs_run_type_idx
  on relocation_navigator.relocation_runs (run_type);

create table relocation_navigator.relocation_sources (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  case_id uuid not null references relocation_navigator.relocation_cases (id) on delete cascade,
  country text not null,
  title text not null,
  url text not null,
  source_type text not null default 'official',
  unique (case_id, url)
);

create index relocation_sources_case_id_idx
  on relocation_navigator.relocation_sources (case_id);

create table relocation_navigator.relocation_artifacts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  case_id uuid not null references relocation_navigator.relocation_cases (id) on delete cascade,
  artifact_type text not null,
  version integer not null default 1,
  content jsonb null,
  content_text text null
);

create index relocation_artifacts_case_id_type_version_idx
  on relocation_navigator.relocation_artifacts (case_id, artifact_type, version);

create or replace function relocation_navigator.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger relocation_cases_set_updated_at
before update on relocation_navigator.relocation_cases
for each row execute function relocation_navigator.set_updated_at();

alter table relocation_navigator.relocation_cases enable row level security;
alter table relocation_navigator.relocation_runs enable row level security;
alter table relocation_navigator.relocation_sources enable row level security;
alter table relocation_navigator.relocation_artifacts enable row level security;

create policy relocation_cases_select_own
  on relocation_navigator.relocation_cases
  for select
  using (user_id = auth.uid());

create policy relocation_cases_insert_own
  on relocation_navigator.relocation_cases
  for insert
  with check (user_id = auth.uid());

create policy relocation_cases_update_own
  on relocation_navigator.relocation_cases
  for update
  using (user_id = auth.uid());

create policy relocation_runs_select_own
  on relocation_navigator.relocation_runs
  for select
  using (
    exists (
      select 1
      from relocation_navigator.relocation_cases cases
      where cases.id = relocation_runs.case_id
        and cases.user_id = auth.uid()
    )
  );

create policy relocation_runs_insert_own
  on relocation_navigator.relocation_runs
  for insert
  with check (
    exists (
      select 1
      from relocation_navigator.relocation_cases cases
      where cases.id = relocation_runs.case_id
        and cases.user_id = auth.uid()
    )
  );

create policy relocation_sources_select_own
  on relocation_navigator.relocation_sources
  for select
  using (
    exists (
      select 1
      from relocation_navigator.relocation_cases cases
      where cases.id = relocation_sources.case_id
        and cases.user_id = auth.uid()
    )
  );

create policy relocation_sources_insert_own
  on relocation_navigator.relocation_sources
  for insert
  with check (
    exists (
      select 1
      from relocation_navigator.relocation_cases cases
      where cases.id = relocation_sources.case_id
        and cases.user_id = auth.uid()
    )
  );

create policy relocation_artifacts_select_own
  on relocation_navigator.relocation_artifacts
  for select
  using (
    exists (
      select 1
      from relocation_navigator.relocation_cases cases
      where cases.id = relocation_artifacts.case_id
        and cases.user_id = auth.uid()
    )
  );

create policy relocation_artifacts_insert_own
  on relocation_navigator.relocation_artifacts
  for insert
  with check (
    exists (
      select 1
      from relocation_navigator.relocation_cases cases
      where cases.id = relocation_artifacts.case_id
        and cases.user_id = auth.uid()
    )
  );
