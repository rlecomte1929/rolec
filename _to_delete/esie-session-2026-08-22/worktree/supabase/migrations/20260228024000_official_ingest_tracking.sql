-- Official source ingest tracking + knowledge_docs metadata

begin;

-- pending candidates: ensure destination_country column for clarity
alter table public.research_source_candidates
  add column if not exists destination_country text;

-- knowledge_docs metadata for ingestion
alter table public.knowledge_docs
  add column if not exists fetched_at timestamptz,
  add column if not exists fetch_status text not null default 'not_fetched' check (fetch_status in ('not_fetched','fetched','fetch_failed')),
  add column if not exists content_excerpt text,
  add column if not exists content_sha256 text,
  add column if not exists last_verified_at timestamptz;

create unique index if not exists idx_knowledge_docs_source_url
  on public.knowledge_docs (source_url);

-- ingest jobs
create table if not exists public.knowledge_doc_ingest_jobs (
  id uuid primary key default gen_random_uuid(),
  candidate_id uuid null,
  doc_id uuid null,
  url text not null,
  destination_country text not null,
  status text not null default 'queued' check (status in ('queued','running','done','failed')),
  error text null,
  started_at timestamptz null,
  finished_at timestamptz null,
  created_at timestamptz default now()
);

create index if not exists idx_knowledge_doc_ingest_jobs_status
  on public.knowledge_doc_ingest_jobs (status);

commit;
