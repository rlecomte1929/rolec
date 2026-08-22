-- ============================================================
-- immigration_requirements: a page-fetch date is not a verification event
-- ============================================================
--
-- WHAT IS WRONG TODAY. `backend/scripts/ingest_corridor_corpus.py` maps the corpus
-- retrieval timestamp straight onto a column named `last_verified_date`:
--
--     line 16:  •  corpus `fetched_at`  →  last_verified_date
--
-- So "when we downloaded the page" is recorded, and read, as "when a human last
-- confirmed this requirement is still true". Measured in production 2026-08-22:
--
--     source='corridor_corpus'   70 rows   last_verified_date = 2026-06-04  (ALL of them)
--     source='relopass_team'     65 rows   last_verified_date IS NULL
--
-- All 70 share one date because they are one ingest run, not 70 verifications. Their
-- `created_at` is the same day, so nothing is lost by removing the claim. The 65
-- team-authored rows already model the honest state: no stamp, no claim.
--
-- WHY IT MATTERS MORE THAN IT LOOKS. `public.immigration_requirements` is SERVED —
-- `immigration_requirement_service` is one of the five serving roots named in CLAUDE.md's
-- serving/LLM isolation guard, and it calls this table "the ENTRY-VISA document checklist".
-- Unlike `requirement_items` it has no `verification_status`, no `verified_by`, and is not
-- covered by `verification_guard.py`. A freshness metric computed over `last_verified_date`
-- would therefore produce a precise, confident number over a field that does not mean what
-- its name says — which is worse than having no metric, because it looks like evidence.
--
-- WHAT THIS DOES.
--   1. Adds `corpus_fetched_at date` — the honest home for the value the ingest actually
--      holds. A retrieval timestamp is a real, useful provenance signal; it is simply not
--      a verification event, and the freshness design ranks it BELOW one for that reason
--      (COALESCE(verified_at, retrieved_at, updated_at, created_at)).
--   2. Moves the 70 corpus dates into it and clears `last_verified_date` for those rows
--      only. Scoped by `source='corridor_corpus'`, so a genuine human stamp — none exist
--      today, but they will — is never touched.
--
-- WHAT THIS DOES NOT DO. It does not add `verification_status` or an actor column to this
-- table, and it does not bring it under `verification_guard.py`. That is the second half of
-- the fix and is deliberately a separate change: locking down who may write a verification
-- claim is a different decision from removing a claim nobody made.
--
-- NO NEW TABLE, so CLAUDE.md's three gates (ENABLE RLS + policy + REVOKE anon) do not
-- apply — this is an ALTER plus a scoped backfill on an existing table whose RLS posture is
-- unchanged. Stated explicitly so a reviewer applying that gate does not go looking.
--
-- ORDERING. Stamped above BOTH the repo max (20261118000000) and the production ledger max
-- (20261116000000), per CLAUDE.md "Choosing a migration timestamp". Note 20261117000000 and
-- 20261118000000 are committed but NOT yet applied; this migration does not depend on
-- either and may be applied before or after them.
--
-- IDEMPOTENT. `ADD COLUMN IF NOT EXISTS`, and the backfill's WHERE clause matches nothing
-- once it has run.
--
-- PROBE (run after applying; expect corpus_dated=70, still_claiming=0, team_rows_untouched=65):
--   SELECT count(*) FILTER (WHERE corpus_fetched_at IS NOT NULL)                AS corpus_dated,
--          count(*) FILTER (WHERE source='corridor_corpus'
--                             AND last_verified_date IS NOT NULL)               AS still_claiming,
--          count(*) FILTER (WHERE source='relopass_team')                       AS team_rows_untouched
--     FROM public.immigration_requirements;
-- ============================================================

ALTER TABLE public.immigration_requirements
  ADD COLUMN IF NOT EXISTS corpus_fetched_at date;

COMMENT ON COLUMN public.immigration_requirements.corpus_fetched_at IS
  'When the source page was retrieved by the corridor-corpus ingest. Provenance, NOT '
  'assurance: it says the text was current when fetched, not that anyone confirmed the '
  'requirement. Never copy this into last_verified_date.';

COMMENT ON COLUMN public.immigration_requirements.last_verified_date IS
  'When a HUMAN last confirmed this requirement is still true. NULL means nobody has — '
  'which is the honest state for every row that arrived from an automated ingest. Do not '
  'populate it from a fetch, crawl or import timestamp; use corpus_fetched_at.';

-- Move the ingest dates off the verification column. Scoped to the ingest's own rows.
UPDATE public.immigration_requirements
   SET corpus_fetched_at  = last_verified_date,
       last_verified_date = NULL
 WHERE source = 'corridor_corpus'
   AND last_verified_date IS NOT NULL;
