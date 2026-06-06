-- W3 / AIQ-837 — persist cited chunk ids on answer traces.
--
-- The RAG engine extracts the chunk ids cited in each answer but never stored
-- them on the trace, so user feedback could not be joined back to the chunks
-- that produced the answer. ai_human_feedback.trace_session_id already FKs to
-- policy_assistant_traces.id, so adding cited_chunk_ids to the trace closes the
-- loop (foundation for a future source_reliability_score).
--
-- Additive, nullable-with-default. Stored as jsonb (not uuid[]): cited ids are
-- "[chunk:<id>]" text refs, not UUIDs, and jsonb mirrors the existing
-- steps_json column + stays cross-DB consistent with the SQLite dev TEXT column.

begin;

alter table policy_assistant_traces
  add column if not exists cited_chunk_ids jsonb not null default '[]'::jsonb;

-- Join recipe — "chunks cited in rejected answers" (input to source reliability):
--   SELECT t.cited_chunk_ids, f.verdict
--   FROM ai_human_feedback f
--   JOIN policy_assistant_traces t ON t.id = f.trace_session_id
--   WHERE f.verdict = 'reject';

commit;
