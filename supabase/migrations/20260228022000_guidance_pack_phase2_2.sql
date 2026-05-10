-- Guidance Pack Phase 2.2: rule explainability + governance mode

begin;

-- knowledge_rules versioning + baseline metadata
alter table public.knowledge_rules
  add column if not exists version int not null default 1,
  add column if not exists supersedes_rule_id uuid null references public.knowledge_rules(id),
  add column if not exists is_baseline boolean not null default false,
  add column if not exists baseline_priority int not null default 100,
  add column if not exists is_active boolean not null default true;

-- Replace unique constraint on rule_key with (rule_key, version)
alter table public.knowledge_rules drop constraint if exists knowledge_rules_rule_key_key;
create unique index if not exists idx_knowledge_rules_key_version
  on public.knowledge_rules (rule_key, version);

-- relocation_guidance_packs: governance + fingerprint + rule set + coverage already added
alter table public.relocation_guidance_packs
  add column if not exists guidance_mode text not null default 'demo' check (guidance_mode in ('demo','strict')),
  add column if not exists pack_hash text,
  add column if not exists rule_set jsonb not null default '[]'::jsonb;

-- rule evaluation logs
create table if not exists public.rule_evaluation_logs (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid not null,
  case_id uuid not null,
  user_id uuid not null,
  destination_country text not null,
  rule_id uuid not null references public.knowledge_rules(id),
  rule_key text not null,
  rule_version int not null,
  pack_id uuid not null references public.knowledge_packs(id),
  pack_version int not null,
  applies_if jsonb null,
  evaluation_result boolean not null,
  was_baseline boolean not null,
  injected_for_minimum boolean not null default false,
  citations jsonb not null default '[]'::jsonb,
  snapshot_subset jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_rule_eval_case_created
  on public.rule_evaluation_logs (case_id, created_at desc);
create index if not exists idx_rule_eval_trace
  on public.rule_evaluation_logs (trace_id);

-- RLS
alter table public.rule_evaluation_logs enable row level security;

drop policy if exists rule_eval_select on public.rule_evaluation_logs;
create policy rule_eval_select
  on public.rule_evaluation_logs
  for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id::uuid = rule_evaluation_logs.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists rule_eval_insert on public.rule_evaluation_logs;
create policy rule_eval_insert
  on public.rule_evaluation_logs
  for insert
  to service_role
  with check (true);

-- Seed: set baseline priorities for existing baseline rules
update public.knowledge_rules
set baseline_priority = case
  when phase = 'pre_move' then 10
  when phase = 'arrival' then 20
  when phase = 'first_90_days' then 30
  when phase = 'first_tax_year' then 40
  else 100
end
where is_baseline = true;

commit;
