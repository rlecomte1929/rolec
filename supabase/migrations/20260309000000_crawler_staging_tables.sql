-- Crawler/extraction pipeline staging tables
-- Content stays staged until admin review; no direct publish to country_resources / rkg_country_events
begin;

-- 1. crawl_runs: tracks each run
create table if not exists public.crawl_runs (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  source_scope text, -- json or comma list: sources, country, city, domain
  status text not null default 'running', -- running, completed, failed, cancelled
  config_snapshot jsonb default '{}',
  summary text,
  initiated_by text,
  errors_count int not null default 0,
  warnings_count int not null default 0,
  documents_fetched int not null default 0,
  chunks_created int not null default 0,
  resources_staged int not null default 0,
  events_staged int not null default 0,
  duplicates_detected int not null default 0
);

create index if not exists idx_crawl_runs_started on public.crawl_runs(started_at desc);
create index if not exists idx_crawl_runs_status on public.crawl_runs(status);

-- 2. crawled_source_documents: one per fetched page/file
create table if not exists public.crawled_source_documents (
  id uuid primary key default gen_random_uuid(),
  crawl_run_id uuid references public.crawl_runs(id) on delete cascade,
  source_name text not null,
  source_url text not null,
  final_url text,
  country_code text,
  city_name text,
  source_type text,
  trust_tier text,
  content_type text,
  content_hash text,
  fetched_at timestamptz not null default now(),
  storage_path text,
  page_title text,
  language_code text,
  http_status int,
  parse_status text default 'pending', -- pending, parsed, parse_failed
  extraction_status text default 'pending', -- pending, extracted, extract_failed, skipped
  created_at timestamptz not null default now()
);

create index if not exists idx_crawled_docs_run on public.crawled_source_documents(crawl_run_id);
create index if not exists idx_crawled_docs_hash on public.crawled_source_documents(content_hash);
create index if not exists idx_crawled_docs_url on public.crawled_source_documents(final_url);

-- 3. crawled_source_chunks: chunked units for extraction
create table if not exists public.crawled_source_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.crawled_source_documents(id) on delete cascade,
  chunk_index int not null,
  heading_path text,
  chunk_text text not null,
  chunk_hash text,
  extracted_metadata jsonb default '{}',
  created_at timestamptz not null default now()
);

create index if not exists idx_crawled_chunks_doc on public.crawled_source_chunks(document_id);

-- 4. staged_resource_candidates: extracted candidate resources (NOT published)
create table if not exists public.staged_resource_candidates (
  id uuid primary key default gen_random_uuid(),
  crawl_run_id uuid references public.crawl_runs(id) on delete set null,
  document_id uuid references public.crawled_source_documents(id) on delete set null,
  chunk_id uuid references public.crawled_source_chunks(id) on delete set null,
  country_code text not null,
  country_name text,
  city_name text,
  category_key text,
  title text not null,
  summary text,
  body text,
  content_json jsonb default '{}',
  resource_type text not null default 'guide',
  audience_type text not null default 'all',
  tags jsonb default '[]',
  source_url text,
  source_name text,
  trust_tier text,
  confidence_score numeric,
  extraction_method text, -- rule_based, schema_parser, feed_mapping, llm_structured_extraction
  status text not null default 'new', -- new, deduped, needs_review, approved_for_import, rejected
  duplicate_of_candidate_id uuid references public.staged_resource_candidates(id) on delete set null,
  duplicate_of_live_resource_id uuid,
  provenance_json jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_staged_resources_run on public.staged_resource_candidates(crawl_run_id);
create index if not exists idx_staged_resources_country_city on public.staged_resource_candidates(country_code, city_name);
create index if not exists idx_staged_resources_status on public.staged_resource_candidates(status);
create index if not exists idx_staged_resources_category on public.staged_resource_candidates(category_key);

-- 5. staged_event_candidates: extracted candidate events (NOT published)
create table if not exists public.staged_event_candidates (
  id uuid primary key default gen_random_uuid(),
  crawl_run_id uuid references public.crawl_runs(id) on delete set null,
  document_id uuid references public.crawled_source_documents(id) on delete set null,
  chunk_id uuid references public.crawled_source_chunks(id) on delete set null,
  country_code text not null,
  country_name text,
  city_name text,
  title text not null,
  description text,
  event_type text,
  venue_name text,
  address text,
  start_datetime timestamptz,
  end_datetime timestamptz,
  price_text text,
  currency text,
  is_free boolean,
  is_family_friendly boolean,
  min_age int,
  max_age int,
  language_code text,
  source_url text,
  source_name text,
  trust_tier text,
  confidence_score numeric,
  extraction_method text,
  status text not null default 'new',
  duplicate_of_candidate_id uuid references public.staged_event_candidates(id) on delete set null,
  duplicate_of_live_event_id uuid,
  provenance_json jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_staged_events_run on public.staged_event_candidates(crawl_run_id);
create index if not exists idx_staged_events_country_city on public.staged_event_candidates(country_code, city_name);
create index if not exists idx_staged_events_status on public.staged_event_candidates(status);
create index if not exists idx_staged_events_start on public.staged_event_candidates(start_datetime);

-- RLS: admin only for staging (no public read)
alter table public.crawl_runs enable row level security;
alter table public.crawled_source_documents enable row level security;
alter table public.crawled_source_chunks enable row level security;
alter table public.staged_resource_candidates enable row level security;
alter table public.staged_event_candidates enable row level security;

-- Service role bypasses RLS for CLI/backend
create policy "crawl_runs_admin" on public.crawl_runs for all using (true) with check (true);
create policy "crawled_docs_admin" on public.crawled_source_documents for all using (true) with check (true);
create policy "crawled_chunks_admin" on public.crawled_source_chunks for all using (true) with check (true);
create policy "staged_resources_admin" on public.staged_resource_candidates for all using (true) with check (true);
create policy "staged_events_admin" on public.staged_event_candidates for all using (true) with check (true);

commit;
