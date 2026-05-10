-- Dynamic Dossier Phase 1: questions, answers, sources, case-specific questions

begin;

-- =============================================================================
-- Tables
-- =============================================================================
create table if not exists public.dossier_questions (
  id uuid primary key default gen_random_uuid(),
  destination_country text not null,
  domain text not null,
  question_key text not null,
  question_text text not null,
  answer_type text not null,
  options jsonb,
  is_mandatory boolean not null default false,
  applies_if jsonb,
  sort_order int not null default 0,
  version int not null default 1,
  created_at timestamptz not null default now()
);

create unique index if not exists idx_dossier_questions_key
  on public.dossier_questions (destination_country, question_key, version);

create table if not exists public.dossier_answers (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  user_id uuid not null,
  question_id uuid not null references public.dossier_questions(id) on delete cascade,
  answer jsonb not null,
  answered_at timestamptz not null default now()
);

create unique index if not exists idx_dossier_answers_unique
  on public.dossier_answers (case_id, user_id, question_id);

create index if not exists idx_dossier_answers_case
  on public.dossier_answers (case_id);

create table if not exists public.dossier_source_suggestions (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  destination_country text not null,
  query text not null,
  results jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_dossier_source_suggestions_case
  on public.dossier_source_suggestions (case_id);

create table if not exists public.dossier_case_questions (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  question_text text not null,
  answer_type text not null,
  options jsonb,
  is_mandatory boolean not null default false,
  sources jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_dossier_case_questions_case
  on public.dossier_case_questions (case_id);

create table if not exists public.dossier_case_answers (
  id uuid primary key default gen_random_uuid(),
  case_id text not null,
  user_id uuid not null,
  case_question_id uuid not null references public.dossier_case_questions(id) on delete cascade,
  answer jsonb not null,
  answered_at timestamptz not null default now()
);

create unique index if not exists idx_dossier_case_answers_unique
  on public.dossier_case_answers (case_id, user_id, case_question_id);

create index if not exists idx_dossier_case_answers_case
  on public.dossier_case_answers (case_id);

-- =============================================================================
-- RLS
-- =============================================================================
alter table public.dossier_questions enable row level security;
alter table public.dossier_answers enable row level security;
alter table public.dossier_source_suggestions enable row level security;
alter table public.dossier_case_questions enable row level security;
alter table public.dossier_case_answers enable row level security;

-- Dossier questions: read-only for authenticated
drop policy if exists dossier_questions_select on public.dossier_questions;
create policy dossier_questions_select
  on public.dossier_questions
  for select
  to authenticated
  using (true);

-- Admin-only changes (service role)
drop policy if exists dossier_questions_admin_write on public.dossier_questions;
create policy dossier_questions_admin_write
  on public.dossier_questions
  for all
  to service_role
  using (true)
  with check (true);

-- Answers: user must be HR or Employee for the case and only write their own rows
drop policy if exists dossier_answers_select on public.dossier_answers;
create policy dossier_answers_select
  on public.dossier_answers
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.case_assignments ca
      where ca.case_id = dossier_answers.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists dossier_answers_write on public.dossier_answers;
create policy dossier_answers_write
  on public.dossier_answers
  for insert
  to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1
      from public.case_assignments ca
      where ca.case_id = dossier_answers.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists dossier_answers_update on public.dossier_answers;
create policy dossier_answers_update
  on public.dossier_answers
  for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- Case questions: readable if user is on case; insert only if on case
drop policy if exists dossier_case_questions_select on public.dossier_case_questions;
create policy dossier_case_questions_select
  on public.dossier_case_questions
  for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = dossier_case_questions.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists dossier_case_questions_insert on public.dossier_case_questions;
create policy dossier_case_questions_insert
  on public.dossier_case_questions
  for insert
  to authenticated
  with check (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = dossier_case_questions.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

-- Case question answers: user must be HR or Employee for the case and only write their own rows
drop policy if exists dossier_case_answers_select on public.dossier_case_answers;
create policy dossier_case_answers_select
  on public.dossier_case_answers
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.case_assignments ca
      where ca.case_id = dossier_case_answers.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists dossier_case_answers_write on public.dossier_case_answers;
create policy dossier_case_answers_write
  on public.dossier_case_answers
  for insert
  to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1
      from public.case_assignments ca
      where ca.case_id = dossier_case_answers.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists dossier_case_answers_update on public.dossier_case_answers;
create policy dossier_case_answers_update
  on public.dossier_case_answers
  for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- Source suggestions: readable if user is on case; insert only service role
drop policy if exists dossier_source_suggestions_select on public.dossier_source_suggestions;
create policy dossier_source_suggestions_select
  on public.dossier_source_suggestions
  for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id = dossier_source_suggestions.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists dossier_source_suggestions_insert on public.dossier_source_suggestions;
create policy dossier_source_suggestions_insert
  on public.dossier_source_suggestions
  for insert
  to service_role
  with check (true);

-- =============================================================================
-- Seed questions (SG/US)
-- =============================================================================
insert into public.dossier_questions
  (destination_country, domain, question_key, question_text, answer_type, options, is_mandatory, applies_if, sort_order)
values
  -- SG (Singapore)
  ('SG', 'immigration', 'sg.pass_type_known', 'Do you already know the intended work pass type? (e.g., EP, S Pass)', 'boolean', null, true,
    '{"field":"relocationBasics.destCountry","op":"in","value":["Singapore","SG"]}', 10),
  ('SG', 'immigration', 'sg.employer_sponsor', 'Will your employer sponsor the work pass application?', 'boolean', null, true,
    '{"field":"relocationBasics.destCountry","op":"in","value":["Singapore","SG"]}', 20),
  ('SG', 'registration', 'sg.move_date_confirm', 'Do you have a confirmed move date?', 'boolean', null, true,
    '{"field":"relocationBasics.targetMoveDate","op":"exists","value":false}', 30),
  ('SG', 'immigration', 'sg.nationality_confirm', 'Please confirm your nationality.', 'text', null, true,
    '{"field":"employeeProfile.nationality","op":"exists","value":false}', 40),
  ('SG', 'registration', 'sg.current_location', 'Where are you currently residing? (city/country)', 'text', null, true,
    '{"field":"employeeProfile.residenceCountry","op":"exists","value":false}', 50),
  ('SG', 'employment', 'sg.employment_type', 'What is your employment type for the Singapore role?', 'select',
    '["Permanent","Fixed-term","Contractor","Intern","Other"]'::jsonb, true,
    '{"field":"assignmentContext.contractType","op":"exists","value":false}', 60),
  ('SG', 'immigration', 'sg.dependents', 'Will any dependents accompany you?', 'boolean', null, false,
    '{"field":"relocationBasics.hasDependents","op":"exists","value":false}', 70),
  ('SG', 'immigration', 'sg.dependent_details', 'If yes, how many dependents will accompany you?', 'text', null, false,
    '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 80),

  -- US (United States)
  ('US', 'immigration', 'us.visa_known', 'Do you already know the intended visa category? (e.g., H-1B, L-1, O-1)', 'boolean', null, true,
    '{"field":"relocationBasics.destCountry","op":"in","value":["United States","USA","US"]}', 10),
  ('US', 'immigration', 'us.employer_sponsor', 'Will your employer sponsor the visa/work authorization?', 'boolean', null, true,
    '{"field":"relocationBasics.destCountry","op":"in","value":["United States","USA","US"]}', 20),
  ('US', 'registration', 'us.move_date_confirm', 'Do you have a confirmed move date?', 'boolean', null, true,
    '{"field":"relocationBasics.targetMoveDate","op":"exists","value":false}', 30),
  ('US', 'immigration', 'us.current_location', 'Where are you currently residing? (city/country)', 'text', null, true,
    '{"field":"employeeProfile.residenceCountry","op":"exists","value":false}', 40),
  ('US', 'immigration', 'us.prior_us_stays', 'Have you previously stayed or worked in the US?', 'boolean', null, false,
    '{"field":"relocationBasics.destCountry","op":"in","value":["United States","USA","US"]}', 50),
  ('US', 'employment', 'us.employment_type', 'What is your employment type for the US role?', 'select',
    '["Permanent","Fixed-term","Contractor","Intern","Other"]'::jsonb, true,
    '{"field":"assignmentContext.contractType","op":"exists","value":false}', 60),
  ('US', 'immigration', 'us.dependents', 'Will any dependents accompany you?', 'boolean', null, false,
    '{"field":"relocationBasics.hasDependents","op":"exists","value":false}', 70),
  ('US', 'immigration', 'us.dependent_details', 'If yes, how many dependents will accompany you?', 'text', null, false,
    '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 80);

commit;
