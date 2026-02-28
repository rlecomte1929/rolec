-- Research collector: pending review sources only

begin;

create table if not exists public.research_source_candidates (
  id uuid primary key default gen_random_uuid(),
  country_code text not null,
  purpose text not null,
  url text not null,
  title text not null,
  publisher_domain text not null,
  snippet text null,
  notes text null,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  retrieved_at timestamptz not null,
  content_hash text not null unique,
  created_at timestamptz not null default now()
);

create index if not exists idx_research_candidates_country
  on public.research_source_candidates (country_code);

commit;
