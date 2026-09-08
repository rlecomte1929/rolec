-- N1 / AIQ-840 — raw crawl store for official immigration-rule pages.
--
-- One row per (corridor, source_url, content_hash). The crawler writes
-- extracted_text here (raw HTML goes to object storage via raw_html_path);
-- N2 reads is_active rows with crawl_error IS NULL to chunk + embed.

begin;

create table if not exists crawled_immigration_documents (
  id uuid primary key default gen_random_uuid(),
  corridor varchar(20) not null,          -- 'FR_NO', 'IN_DE', etc.
  source_url text not null,
  trust_tier integer not null default 2,
  raw_html_path text,                     -- Supabase Storage object path (nullable)
  extracted_text text,                    -- plain text after HTML strip
  content_hash text not null,             -- SHA-256 of extracted_text
  fetched_at timestamptz not null default now(),
  http_status integer,
  crawl_error text,
  is_active boolean default true,
  constraint uq_crawled_doc unique (corridor, source_url, content_hash)
);

create index if not exists idx_crawled_docs_corridor
  on crawled_immigration_documents (corridor, is_active);

-- Security hard-gate (root CLAUDE.md): every new public table must enable RLS,
-- have >=1 policy, and revoke anon. This is non-tenant global reference data
-- written only by the backend (service_role bypasses RLS); expose read-only to
-- authenticated, never to the anon key shipped in the frontend bundle.
alter table crawled_immigration_documents enable row level security;

drop policy if exists cid_select_authenticated on crawled_immigration_documents;
create policy cid_select_authenticated
  on crawled_immigration_documents
  for select
  to authenticated
  using (true);

revoke all on crawled_immigration_documents from anon;

commit;
