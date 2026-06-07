-- N8 / AIQ-848 — rolling source_reliability_score on the immigration corpus.
--
-- Adds the feedback-loop columns the source_reliability_service recomputes
-- (nightly cron) and the N3 retriever folds into adjusted_score as a 4th factor.
--
-- Additive + idempotent (add column if not exists). No new table, so no new RLS
-- gate — immigration_corpus_chunks already has RLS + authenticated SELECT policy +
-- anon revoked (see 20260615000000_immigration_corpus_chunks.sql).
--
-- reliability_score defaults to 0.5 (neutral) so every existing chunk keeps its
-- current ranking until the recompute job has feedback to act on. Both the score
-- and the counts are SET (full recompute) by recompute_reliability_scores(), never
-- incremented, so the job is idempotent.

begin;

alter table public.immigration_corpus_chunks
  add column if not exists reliability_score       float       not null default 0.5,
  add column if not exists citation_count          integer     not null default 0,
  add column if not exists rejection_count         integer     not null default 0,
  add column if not exists last_reliability_update  timestamptz;

commit;

-- Rollback (manual):
-- alter table public.immigration_corpus_chunks
--   drop column if exists reliability_score,
--   drop column if exists citation_count,
--   drop column if exists rejection_count,
--   drop column if exists last_reliability_update;
