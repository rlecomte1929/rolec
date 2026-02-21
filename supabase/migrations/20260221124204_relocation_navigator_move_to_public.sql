-- Move Relocation Navigator objects to public schema (MVP-friendly).
-- Keep existing public.relocation_cases (contains production data).
-- Create public relocation_* supporting tables.
-- Drop relocation_navigator schema ONLY if it is empty (safety gate).

begin;

-- 1) Create supporting tables in PUBLIC (do not recreate/alter public.relocation_cases)

create table if not exists public.relocation_runs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  case_id text not null references public.relocation_cases (id) on delete cascade,
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

create index if not exists relocation_runs_case_id_created_at_idx
  on public.relocation_runs (case_id, created_at desc);

create index if not exists relocation_runs_run_type_idx
  on public.relocation_runs (run_type);


create table if not exists public.relocation_sources (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  case_id text not null references public.relocation_cases (id) on delete cascade,
  country text not null,
  title text not null,
  url text not null,
  source_type text not null default 'official',
  unique (case_id, url)
);

create index if not exists relocation_sources_case_id_idx
  on public.relocation_sources (case_id);


create table if not exists public.relocation_artifacts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  case_id text not null references public.relocation_cases (id) on delete cascade,
  artifact_type text not null,
  version integer not null default 1,
  content jsonb null,
  content_text text null
);

create index if not exists relocation_artifacts_case_id_type_version_idx
  on public.relocation_artifacts (case_id, artifact_type, version);


-- 2) RLS on new PUBLIC tables (do not change public.relocation_cases RLS/policies)

alter table public.relocation_runs enable row level security;
alter table public.relocation_sources enable row level security;
alter table public.relocation_artifacts enable row level security;

-- Runs
drop policy if exists relocation_runs_select_own on public.relocation_runs;
create policy relocation_runs_select_own
  on public.relocation_runs
  for select
  using (
    exists (
      select 1
      from public.relocation_cases c
      where c.id = relocation_runs.case_id
        and (c.employee_id = auth.uid()::text or c.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists relocation_runs_insert_own on public.relocation_runs;
create policy relocation_runs_insert_own
  on public.relocation_runs
  for insert
  with check (
    exists (
      select 1
      from public.relocation_cases c
      where c.id = relocation_runs.case_id
        and (c.employee_id = auth.uid()::text or c.hr_user_id = auth.uid()::text)
    )
  );

-- Sources
drop policy if exists relocation_sources_select_own on public.relocation_sources;
create policy relocation_sources_select_own
  on public.relocation_sources
  for select
  using (
    exists (
      select 1
      from public.relocation_cases c
      where c.id = relocation_sources.case_id
        and (c.employee_id = auth.uid()::text or c.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists relocation_sources_insert_own on public.relocation_sources;
create policy relocation_sources_insert_own
  on public.relocation_sources
  for insert
  with check (
    exists (
      select 1
      from public.relocation_cases c
      where c.id = relocation_sources.case_id
        and (c.employee_id = auth.uid()::text or c.hr_user_id = auth.uid()::text)
    )
  );

-- Artifacts
drop policy if exists relocation_artifacts_select_own on public.relocation_artifacts;
create policy relocation_artifacts_select_own
  on public.relocation_artifacts
  for select
  using (
    exists (
      select 1
      from public.relocation_cases c
      where c.id = relocation_artifacts.case_id
        and (c.employee_id = auth.uid()::text or c.hr_user_id = auth.uid()::text)
    )
  );

drop policy if exists relocation_artifacts_insert_own on public.relocation_artifacts;
create policy relocation_artifacts_insert_own
  on public.relocation_artifacts
  for insert
  with check (
    exists (
      select 1
      from public.relocation_cases c
      where c.id = relocation_artifacts.case_id
        and (c.employee_id = auth.uid()::text or c.hr_user_id = auth.uid()::text)
    )
  );


-- 3) Safety gate: only drop relocation_navigator schema if it exists AND is empty
do $$
declare
  rn_schema_exists boolean;
  cases_count bigint := 0;
  runs_count bigint := 0;
  sources_count bigint := 0;
  artifacts_count bigint := 0;
begin
  select exists (
    select 1 from information_schema.schemata where schema_name = 'relocation_navigator'
  ) into rn_schema_exists;

  if rn_schema_exists then
    -- Count rows if tables exist. If a table doesn't exist, count stays 0.
    if exists (select 1 from information_schema.tables where table_schema='relocation_navigator' and table_name='relocation_cases') then
      execute 'select count(*) from relocation_navigator.relocation_cases' into cases_count;
    end if;

    if exists (select 1 from information_schema.tables where table_schema='relocation_navigator' and table_name='relocation_runs') then
      execute 'select count(*) from relocation_navigator.relocation_runs' into runs_count;
    end if;

    if exists (select 1 from information_schema.tables where table_schema='relocation_navigator' and table_name='relocation_sources') then
      execute 'select count(*) from relocation_navigator.relocation_sources' into sources_count;
    end if;

    if exists (select 1 from information_schema.tables where table_schema='relocation_navigator' and table_name='relocation_artifacts') then
      execute 'select count(*) from relocation_navigator.relocation_artifacts' into artifacts_count;
    end if;

    -- Abort if ANY data exists (prevents accidental data loss)
    if (cases_count + runs_count + sources_count + artifacts_count) > 0 then
      raise exception
        'Refusing to drop schema relocation_navigator because it contains data (cases=% runs=% sources=% artifacts=%).',
        cases_count, runs_count, sources_count, artifacts_count;
    end if;

    -- Safe to drop (empty / unused). CASCADE removes tables, policies, triggers, functions in that schema.
    execute 'drop schema relocation_navigator cascade';
  end if;
end $$;

commit;