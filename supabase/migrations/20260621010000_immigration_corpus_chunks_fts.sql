-- W3-2 hybrid retrieval — Postgres full-text-search leg for immigration_corpus_chunks.
--
-- Adds a STORED generated tsvector over chunk_text + a GIN index so the keyword
-- (BM25-style) leg can rank via ts_rank(chunk_tsv, websearch_to_tsquery(...)).
-- The vector leg (idx_icc_vector, pgvector cosine) is unchanged; HybridRetriever
-- fuses the two via Reciprocal Rank Fusion.
--
-- immigration_corpus_chunks is an EXISTING table (created in
-- 20260615000000_immigration_corpus_chunks.sql) — this only ADDs a generated
-- column + index, so no new-table RLS/grant work is required. FTS is Postgres
-- core ('english' config); no extension needed. Fully idempotent.

ALTER TABLE public.immigration_corpus_chunks
  ADD COLUMN IF NOT EXISTS chunk_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_icc_chunk_tsv
  ON public.immigration_corpus_chunks USING gin (chunk_tsv);
