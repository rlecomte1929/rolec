-- N2 / AIQ-841 — embedded chunk store for the immigration RAG corpus.
--
-- SEPARATE from policy_assistant_chunks by design: that table is tenant-scoped
-- (company_id uuid NOT NULL + a source_type CHECK that excludes immigration),
-- and writing immigration rows there would fail and pollute the HR namespace.
-- This table is corridor-scoped (no company), populated by
-- immigration_chunk_indexer from crawled_immigration_documents.
--
-- corridor is the underscore key form ('FR_NO') — consistent with
-- crawled_immigration_documents; the retriever converts its arrow form
-- ('FR→NO') to this when querying.

begin;

create table if not exists immigration_corpus_chunks (
  id             uuid primary key default gen_random_uuid(),
  corridor       varchar(20) not null,
  source_doc_id  uuid references crawled_immigration_documents(id) on delete cascade,
  source_url     text not null,
  chunk_text     text not null,
  chunk_index    integer not null,
  chunk_metadata jsonb default '{}',
  trust_tier     integer not null default 2,
  fetched_at     timestamptz not null,
  embedding      vector(1536),
  content_hash   text not null,
  is_active      boolean default true,
  created_at     timestamptz default now()
);

create index if not exists idx_icc_vector
  on immigration_corpus_chunks using ivfflat (embedding vector_cosine_ops);
create index if not exists idx_icc_corridor
  on immigration_corpus_chunks (corridor, is_active);
-- Idempotency key for the indexer (skip already-embedded chunks).
create unique index if not exists uq_icc_doc_hash
  on immigration_corpus_chunks (source_doc_id, content_hash);

-- Security hard-gate (root CLAUDE.md): RLS + >=1 policy + revoke anon. Non-tenant
-- reference data; readable by authenticated, never by the frontend anon key.
alter table immigration_corpus_chunks enable row level security;
drop policy if exists icc_select_authenticated on immigration_corpus_chunks;
create policy icc_select_authenticated
  on immigration_corpus_chunks for select to authenticated using (true);
revoke all on immigration_corpus_chunks from anon;

commit;
