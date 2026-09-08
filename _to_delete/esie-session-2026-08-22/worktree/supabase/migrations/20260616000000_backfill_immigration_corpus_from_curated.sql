-- N2 / AIQ-841 — backfill the curated immigration corpus into the new table.
--
-- Before N2, immigration rules were RAG-grounded as immigration_rule rows inside
-- policy_assistant_chunks (the P2-06e curated-JSON path). N2 re-sources the
-- retriever to immigration_corpus_chunks, which would otherwise orphan that
-- curated data (US→FR, IN→DE) and regress those corridors to empty.
--
-- This copies the curated chunks into immigration_corpus_chunks: corridor
-- normalized to the underscore key form, source_tier→trust_tier, embeddings
-- reused as-is (same vector(1536)), source_doc_id NULL (not crawl-derived).
-- Idempotent (WHERE NOT EXISTS on corridor+content_hash). On a fresh replay
-- where policy_assistant_chunks has no immigration rows, this copies 0 rows.

begin;

insert into immigration_corpus_chunks
  (id, corridor, source_doc_id, source_url, chunk_text, chunk_index, chunk_metadata,
   trust_tier, fetched_at, embedding, content_hash, is_active)
select
  gen_random_uuid(),
  replace(p.chunk_metadata->>'corridor', '→', '_'),
  null,
  coalesce(p.chunk_metadata->>'source_url', p.source_ref),
  p.chunk_text,
  (row_number() over (partition by p.chunk_metadata->>'corridor' order by p.id))::int - 1,
  p.chunk_metadata,
  coalesce(nullif(p.chunk_metadata->>'source_tier', '')::int, 2),
  coalesce(p.created_at, now()),
  p.embedding,
  md5(p.chunk_text),
  true
from policy_assistant_chunks p
where p.source_type = 'immigration_rule'
  and not exists (
    select 1 from immigration_corpus_chunks i
    where i.corridor = replace(p.chunk_metadata->>'corridor', '→', '_')
      and i.content_hash = md5(p.chunk_text)
  );

commit;
