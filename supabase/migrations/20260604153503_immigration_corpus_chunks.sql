-- AIQ-756 — history-ledger backfill for prod version 20260604153503 (name: immigration_corpus_chunks)
--
-- This version was applied to prod out-of-band (MCP apply, 2026-06-04) with NO matching
-- repo file, so `supabase db push` / Supabase Preview fails on `Remote migration versions
-- not found in local migrations directory`. The recorded statements (dumped prod-as-oracle
-- from supabase_migrations.schema_migrations) do NOT create a table — despite the name, the
-- migration extends public.policy_assistant_chunks' source_type CHECK to allow
-- 'immigration_rule' and revokes anon. Committed verbatim (already idempotent) so the repo
-- reproduces prod and the ledger reconciles.
--
-- Replay order: policy_assistant_chunks is created earlier (20260503100001), so this ALTER
-- resolves on a fresh replay. Idempotent: drop-if-exists + add; safe re-run / prod no-op.

alter table public.policy_assistant_chunks
  drop constraint if exists policy_assistant_chunks_source_type_check;

alter table public.policy_assistant_chunks
  add constraint policy_assistant_chunks_source_type_check
  check (source_type in (
    'matrix_benefit',
    'matrix_override',
    'canonical_doc',
    'exclusion',
    'evidence_rule',
    'immigration_rule'
  ));

revoke all on public.policy_assistant_chunks from anon;
