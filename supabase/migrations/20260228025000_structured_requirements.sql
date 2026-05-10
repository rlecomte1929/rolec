-- Structured requirements (pending/approved) for curated knowledge

begin;

create table if not exists public.requirement_entities (
  id uuid primary key default gen_random_uuid(),
  destination_country text not null check (destination_country in ('SG','US')),
  domain_area text not null check (domain_area in ('immigration','registration','tax','social_security','healthcare','housing','other')),
  topic_key text not null,
  title text not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index if not exists idx_requirement_entities_topic
  on public.requirement_entities (destination_country, topic_key);

create table if not exists public.requirement_facts (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid not null references public.requirement_entities(id) on delete cascade,
  fact_type text not null check (fact_type in ('eligibility','document','step','deadline','fee','where_to_apply','account','other')),
  fact_key text not null,
  fact_text text not null,
  applies_to jsonb not null default '{}'::jsonb,
  required_fields jsonb not null default '[]'::jsonb,
  source_doc_id uuid not null references public.knowledge_docs(id) on delete cascade,
  source_url text not null,
  evidence_quote text null,
  confidence text not null default 'medium' check (confidence in ('low','medium','high')),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz default now()
);

create index if not exists idx_requirement_facts_entity
  on public.requirement_facts (entity_id);
create index if not exists idx_requirement_facts_source
  on public.requirement_facts (source_doc_id);

create table if not exists public.requirement_reviews (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid null,
  fact_id uuid null,
  reviewer_user_id uuid not null,
  action text not null check (action in ('approve','reject','edit')),
  notes text null,
  created_at timestamptz default now()
);

-- RLS: admin-only via service_role
alter table public.requirement_entities enable row level security;
alter table public.requirement_facts enable row level security;
alter table public.requirement_reviews enable row level security;

drop policy if exists req_entities_read on public.requirement_entities;
create policy req_entities_read on public.requirement_entities
  for select to service_role using (true);
drop policy if exists req_entities_write on public.requirement_entities;
create policy req_entities_write on public.requirement_entities
  for all to service_role using (true) with check (true);

drop policy if exists req_facts_read on public.requirement_facts;
create policy req_facts_read on public.requirement_facts
  for select to service_role using (true);
drop policy if exists req_facts_write on public.requirement_facts;
create policy req_facts_write on public.requirement_facts
  for all to service_role using (true) with check (true);

drop policy if exists req_reviews_read on public.requirement_reviews;
create policy req_reviews_read on public.requirement_reviews
  for select to service_role using (true);
drop policy if exists req_reviews_write on public.requirement_reviews;
create policy req_reviews_write on public.requirement_reviews
  for all to service_role using (true) with check (true);

commit;
