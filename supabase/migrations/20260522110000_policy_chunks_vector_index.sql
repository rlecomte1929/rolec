-- [P2-7] policy_chunks — dual-index retrieval store (pgvector + BM25)
--
-- Creates the vector store that powers the AI policy assistant:
--   • embedding VECTOR(1536)  → semantic similarity via HNSW (cosine)
--   • bm25_vector TSVECTOR    → exact keyword matching (GIN)
--   • compound filter index   → tenant-scoped, tier-filtered queries
--
-- Technical constraints
--   • pgvector extension, OpenAI text-embedding-3-large (1536 dims)
--   • HNSW m=16  ef_construction=64 (standard defaults per spec)
--   • Supabase PostgreSQL (pgvector ≥ 0.5)

begin;

-- ---------------------------------------------------------------------------
-- 1. Enable pgvector extension (idempotent)
-- ---------------------------------------------------------------------------

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- 2. policy_chunks table
-- ---------------------------------------------------------------------------

create table if not exists public.policy_chunks (
  id             uuid        primary key default gen_random_uuid(),

  -- Source document link (nullable: chunks can exist pre-ingestion for tests)
  doc_id         uuid        references public.policy_documents (id) on delete cascade,

  -- Position within the source document
  chunk_index    integer     not null,
  page_start     integer,
  page_end       integer,

  -- Raw extracted text (required for BM25 generation and embedding re-generation)
  text           text        not null,

  -- Semantic embedding (OpenAI text-embedding-3-large, 1536 dimensions)
  embedding      extensions.vector(1536),

  -- BM25 full-text index — auto-generated from text, maintained by Postgres
  bm25_vector    tsvector    generated always as (to_tsvector('english', text)) stored,

  -- Document structure hierarchy (e.g. "Section 3 > Tier Benefits > Manager")
  section_path   text,

  -- Policy metadata — mirrors the classification fields in policy_facts
  category_code  text,
  tier           text,

  -- Tenant scope — MUST always be filtered in queries for data isolation
  company_id     text        not null,

  -- Confidence metadata (copied from policy_facts at ingest time)
  confidence_score  numeric(4, 3)  check (confidence_score between 0 and 1),
  validated_at      timestamptz,

  created_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 3. Indexes
-- ---------------------------------------------------------------------------

-- HNSW index for approximate nearest-neighbour cosine similarity search
-- m=16: controls the number of connections per layer (higher = more accurate, more RAM)
-- ef_construction=64: controls index build quality (higher = more accurate, slower build)
create index if not exists idx_policy_chunks_embedding_hnsw
  on public.policy_chunks
  using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- GIN index for BM25 / full-text search via tsvector
create index if not exists idx_policy_chunks_bm25
  on public.policy_chunks
  using gin (bm25_vector);

-- Compound filter index: most policy queries will be scoped by tenant + tier + category
create index if not exists idx_policy_chunks_tenant_filter
  on public.policy_chunks (company_id, tier, category_code);

-- Supporting index for doc-level chunk retrieval (ordered)
create index if not exists idx_policy_chunks_doc_order
  on public.policy_chunks (doc_id, chunk_index);

-- ---------------------------------------------------------------------------
-- 4. Row-Level Security
-- ---------------------------------------------------------------------------

alter table public.policy_chunks enable row level security;

-- HR users (and admins) can read chunks belonging to their company
drop policy if exists policy_chunks_select on public.policy_chunks;
create policy policy_chunks_select
  on public.policy_chunks
  for select to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and (p.company_id = policy_chunks.company_id or p.role = 'ADMIN')
    )
  );

-- Only backend service roles (or admins) may insert/update/delete chunks
drop policy if exists policy_chunks_write on public.policy_chunks;
create policy policy_chunks_write
  on public.policy_chunks
  for all to authenticated
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.role = 'ADMIN'
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()::text
        and p.role = 'ADMIN'
    )
  );

-- ---------------------------------------------------------------------------
-- 5. Helper function: hybrid_search
--
-- Returns top-k chunks matching either a semantic embedding (cosine) or a
-- BM25 keyword query, filtered to a specific tenant and optional tier.
--
-- Usage:
--   SELECT * FROM hybrid_search(
--     query_embedding  := '[0.01, 0.02, ...]'::vector,
--     query_text       := 'housing allowance manager',
--     company          := 'acme-corp',
--     tier_filter      := 'Manager',   -- NULL = all tiers
--     match_count      := 10
--   );
-- ---------------------------------------------------------------------------

create or replace function public.hybrid_search(
  query_embedding  extensions.vector(1536),
  query_text       text,
  company          text,
  tier_filter      text    default null,
  match_count      integer default 10
)
returns table (
  id               uuid,
  doc_id           uuid,
  chunk_index      integer,
  text             text,
  category_code    text,
  tier             text,
  section_path     text,
  page_start       integer,
  page_end         integer,
  confidence_score numeric,
  cosine_distance  float,
  bm25_rank        float,
  hybrid_score     float
)
language sql stable security definer
set search_path = public, extensions
as $$
  with vector_results as (
    select
      c.id,
      c.doc_id,
      c.chunk_index,
      c.text,
      c.category_code,
      c.tier,
      c.section_path,
      c.page_start,
      c.page_end,
      c.confidence_score,
      (c.embedding <=> query_embedding)::float            as cosine_distance,
      0.0::float                                          as bm25_rank
    from public.policy_chunks c
    where c.company_id = company
      and (tier_filter is null or c.tier = tier_filter)
      and c.embedding is not null
    order by c.embedding <=> query_embedding
    limit match_count * 2
  ),
  bm25_results as (
    select
      c.id,
      c.doc_id,
      c.chunk_index,
      c.text,
      c.category_code,
      c.tier,
      c.section_path,
      c.page_start,
      c.page_end,
      c.confidence_score,
      1.0::float                                          as cosine_distance,
      ts_rank_cd(c.bm25_vector, plainto_tsquery('english', query_text))::float as bm25_rank
    from public.policy_chunks c
    where c.company_id = company
      and (tier_filter is null or c.tier = tier_filter)
      and c.bm25_vector @@ plainto_tsquery('english', query_text)
    order by bm25_rank desc
    limit match_count * 2
  ),
  -- Reciprocal Rank Fusion (k=60) combining both result sets
  combined as (
    select id, doc_id, chunk_index, text, category_code, tier,
           section_path, page_start, page_end, confidence_score,
           cosine_distance, bm25_rank
    from vector_results
    union all
    select id, doc_id, chunk_index, text, category_code, tier,
           section_path, page_start, page_end, confidence_score,
           cosine_distance, bm25_rank
    from bm25_results
  ),
  scored as (
    select
      id, doc_id, chunk_index, text, category_code, tier,
      section_path, page_start, page_end, confidence_score,
      min(cosine_distance)                                as cosine_distance,
      max(bm25_rank)                                      as bm25_rank,
      -- RRF score: weight semantic 0.7, keyword 0.3
      (0.7 / (60.0 + row_number() over (order by min(cosine_distance)))) +
      (0.3 / (60.0 + row_number() over (order by max(bm25_rank) desc))) as hybrid_score
    from combined
    group by id, doc_id, chunk_index, text, category_code, tier,
             section_path, page_start, page_end, confidence_score
  )
  select
    id, doc_id, chunk_index, text, category_code, tier,
    section_path, page_start, page_end, confidence_score,
    cosine_distance, bm25_rank, hybrid_score
  from scored
  order by hybrid_score desc
  limit match_count;
$$;

comment on function public.hybrid_search is
  'RRF-fused hybrid search: 70% cosine similarity (HNSW) + 30% BM25 keyword matching. '
  'Always filtered by company_id (tenant isolation). tier_filter is optional.';

commit;
