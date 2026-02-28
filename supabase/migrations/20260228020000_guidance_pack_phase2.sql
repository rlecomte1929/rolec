-- Guidance Pack Phase 2 (Option A): knowledge packs and generated guidance

begin;

-- =============================================================================
-- Knowledge packs (curated, read-only for users)
-- =============================================================================
create table if not exists public.knowledge_packs (
  id uuid primary key default gen_random_uuid(),
  destination_country text not null check (destination_country in ('SG','US')),
  domain text not null check (domain in ('immigration','registration','payroll','housing','tax','other')),
  version int not null default 1,
  status text not null default 'active' check (status in ('active','inactive')),
  effective_from date null,
  effective_to date null,
  last_verified_at timestamptz null,
  created_at timestamptz not null default now()
);

create table if not exists public.knowledge_docs (
  id uuid primary key default gen_random_uuid(),
  pack_id uuid not null references public.knowledge_packs(id) on delete cascade,
  title text not null,
  publisher text null,
  source_url text not null,
  text_content text not null,
  checksum text null,
  created_at timestamptz not null default now()
);

create table if not exists public.knowledge_rules (
  id uuid primary key default gen_random_uuid(),
  pack_id uuid not null references public.knowledge_packs(id) on delete cascade,
  rule_key text not null unique,
  applies_if jsonb null,
  title text not null,
  phase text not null check (phase in ('pre_move','arrival','first_90_days','first_tax_year')),
  category text not null check (category in ('immigration','registration','payroll','housing','tax','other')),
  guidance_md text not null,
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_knowledge_rules_pack on public.knowledge_rules(pack_id);
create index if not exists idx_knowledge_docs_pack on public.knowledge_docs(pack_id);

-- =============================================================================
-- Generated packs per case
-- =============================================================================
create table if not exists public.relocation_guidance_packs (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null,
  user_id uuid not null,
  destination_country text not null,
  profile_snapshot jsonb not null,
  plan jsonb not null,
  checklist jsonb not null,
  markdown text not null,
  sources jsonb not null default '[]'::jsonb,
  not_covered jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_guidance_packs_case_created
  on public.relocation_guidance_packs (case_id, created_at desc);

-- =============================================================================
-- Trace events
-- =============================================================================
create table if not exists public.relocation_trace_events (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid not null,
  case_id uuid not null,
  step_name text not null,
  input jsonb not null default '{}'::jsonb,
  output jsonb not null default '{}'::jsonb,
  status text not null check (status in ('ok','error')),
  error text null,
  created_at timestamptz not null default now()
);

create index if not exists idx_trace_events_case_created
  on public.relocation_trace_events (case_id, created_at desc);

-- =============================================================================
-- RLS
-- =============================================================================
alter table public.knowledge_packs enable row level security;
alter table public.knowledge_docs enable row level security;
alter table public.knowledge_rules enable row level security;
alter table public.relocation_guidance_packs enable row level security;
alter table public.relocation_trace_events enable row level security;

-- Knowledge: authenticated can read, service role writes
drop policy if exists knowledge_packs_select on public.knowledge_packs;
create policy knowledge_packs_select
  on public.knowledge_packs
  for select
  to authenticated
  using (true);

drop policy if exists knowledge_docs_select on public.knowledge_docs;
create policy knowledge_docs_select
  on public.knowledge_docs
  for select
  to authenticated
  using (true);

drop policy if exists knowledge_rules_select on public.knowledge_rules;
create policy knowledge_rules_select
  on public.knowledge_rules
  for select
  to authenticated
  using (true);

drop policy if exists knowledge_admin_write on public.knowledge_packs;
create policy knowledge_admin_write
  on public.knowledge_packs
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists knowledge_docs_admin_write on public.knowledge_docs;
create policy knowledge_docs_admin_write
  on public.knowledge_docs
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists knowledge_rules_admin_write on public.knowledge_rules;
create policy knowledge_rules_admin_write
  on public.knowledge_rules
  for all
  to service_role
  using (true)
  with check (true);

-- Guidance packs: users can read/write their own rows for cases they belong to
drop policy if exists guidance_packs_select on public.relocation_guidance_packs;
create policy guidance_packs_select
  on public.relocation_guidance_packs
  for select
  to authenticated
  using (
    user_id = auth.uid()
    and exists (
      select 1 from public.case_assignments ca
      where ca.case_id::uuid = relocation_guidance_packs.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists guidance_packs_insert on public.relocation_guidance_packs;
create policy guidance_packs_insert
  on public.relocation_guidance_packs
  for insert
  to authenticated
  with check (
    user_id = auth.uid()
    and exists (
      select 1 from public.case_assignments ca
      where ca.case_id::uuid = relocation_guidance_packs.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

-- Trace events: read-only for users on their case; insert service role
drop policy if exists trace_events_select on public.relocation_trace_events;
create policy trace_events_select
  on public.relocation_trace_events
  for select
  to authenticated
  using (
    exists (
      select 1 from public.case_assignments ca
      where ca.case_id::uuid = relocation_trace_events.case_id
        and (ca.employee_user_id::text = auth.uid()::text or ca.hr_user_id::text = auth.uid()::text)
    )
  );

drop policy if exists trace_events_insert on public.relocation_trace_events;
create policy trace_events_insert
  on public.relocation_trace_events
  for insert
  to service_role
  with check (true);

-- =============================================================================
-- Seed minimal packs + docs + rules (SG, US)
-- =============================================================================
insert into public.knowledge_packs (destination_country, domain, version, status)
values
  ('SG', 'immigration', 1, 'active'),
  ('SG', 'registration', 1, 'active'),
  ('US', 'immigration', 1, 'active'),
  ('US', 'registration', 1, 'active')
on conflict do nothing;

with packs as (
  select id, destination_country, domain
  from public.knowledge_packs
  where status = 'active'
)
insert into public.knowledge_docs (pack_id, title, publisher, source_url, text_content)
select p.id,
  case
    when p.destination_country = 'SG' and p.domain = 'immigration' then 'MOM Work Passes Overview'
    when p.destination_country = 'SG' and p.domain = 'registration' then 'ICA Entry Requirements'
    when p.destination_country = 'US' and p.domain = 'immigration' then 'USCIS Working in the United States'
    when p.destination_country = 'US' and p.domain = 'registration' then 'Travel.State.Gov – US Visas'
  end as title,
  case
    when p.destination_country = 'SG' then 'Singapore Government'
    when p.destination_country = 'US' then 'US Government'
  end as publisher,
  case
    when p.destination_country = 'SG' and p.domain = 'immigration' then 'https://www.mom.gov.sg/passes-and-permits'
    when p.destination_country = 'SG' and p.domain = 'registration' then 'https://www.ica.gov.sg/enter-transit-depart'
    when p.destination_country = 'US' and p.domain = 'immigration' then 'https://www.uscis.gov/working-in-the-united-states'
    when p.destination_country = 'US' and p.domain = 'registration' then 'https://travel.state.gov/content/travel/en/us-visas.html'
  end as source_url,
  'Official guidance summary placeholder (curated).' as text_content
from packs p
on conflict do nothing;

with doc_map as (
  select d.id as doc_id, p.id as pack_id, p.destination_country, p.domain
  from public.knowledge_docs d
  join public.knowledge_packs p on p.id = d.pack_id
)
insert into public.knowledge_rules (
  pack_id, rule_key, applies_if, title, phase, category, guidance_md, citations
)
select
  pack_id,
  case
    when destination_country = 'SG' and domain = 'immigration' then 'sg_immig_basic'
    when destination_country = 'SG' and domain = 'registration' then 'sg_entry_basic'
    when destination_country = 'US' and domain = 'immigration' then 'us_immig_basic'
    when destination_country = 'US' and domain = 'registration' then 'us_entry_basic'
  end as rule_key,
  null as applies_if,
  case
    when destination_country = 'SG' then 'Confirm work authorization and entry requirements'
    when destination_country = 'US' then 'Confirm visa category and entry requirements'
  end as title,
  'pre_move' as phase,
  case when domain = 'immigration' then 'immigration' else 'registration' end as category,
  'Check eligibility and required documents with official sources and your employer. Please confirm details before submission.' as guidance_md,
  jsonb_build_array(doc_id) as citations
from doc_map
on conflict do nothing;

commit;
