-- P2-06e · Adapt policy_assistant_chunks to hold immigration-corpus RAG chunks.
--
-- The table (20260503100001_policy_assistant_chunks.sql) was built for the
-- Policy Assistant (HR) use case. The immigration RAG retriever
-- (backend/app/services/immigration_retriever.py) stores corridor rule chunks
-- in the SAME table, tagged source_type='immigration_rule' under a fixed
-- synthetic corpus company_id (immigration rules are corridor-scoped, not
-- company-scoped). Two adaptations are required before those chunks can land:
--
--   1. Allow 'immigration_rule' in the source_type CHECK constraint. The
--      original CHECK only permitted the HR-policy source types.
--   2. Defense-in-depth REVOKE on anon. The original create migration omitted
--      the `REVOKE ALL ... FROM anon` required by the repo's migration security
--      rules (see root CLAUDE.md). Back-filled here so a replay of the full
--      migration chain reproduces the hardened prod state. Idempotent.
--
-- No new table; no row changes. Replay-safe.

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
