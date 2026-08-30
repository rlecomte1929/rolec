-- ============================================================
-- Revert 20261123000000 — drop the verifier columns that P1 does not need
-- ============================================================
--
-- WHY THIS EXISTS. 20261123000000 added ten columns and a unique index to
-- public.requirement_fact_candidates for a Verifier P1 design that was superseded
-- before it shipped. The CORRECTED P1 brief (post-P0-recon) is explicit on both points:
--
--     "verify_ledger.py is a preprocessor, not a new pipeline. It never writes
--      entities/facts itself and adds no staging table."
--     "No additive migration required for P1 (no new columns on facts). If you want to
--      persist the V1/V2 verdict, write it to the report/agent_runs, not to a new
--      table — defer any schema change to P2."
--     "dedupe_key replaces fact_uid — confirmed, throughout. ... drop the synthetic
--      fact_uid/entity_uid."
--
-- The accompanying revert removes the only code that ever referenced these columns, so
-- after it lands they are unreferenced by anything in the repo.
--
-- MEASURED against prod immediately before writing this, across the table's 23 rows:
-- nine of the ten columns are 100% NULL. The tenth, `contradiction`, is non-NULL on all
-- 23 — not because anything wrote it, but because it was added as `DEFAULT false`, which
-- backfilled every existing row. So the only values being dropped are 23 defaulted
-- `false`s that no code ever set or read. The partial unique index covers zero rows (it
-- is `WHERE fact_uid IS NOT NULL`, and fact_uid is NULL everywhere). Nothing a human or a
-- pipeline produced is destroyed here.
--
-- The verdict/tier/depth idea is not being rejected — it is deferred to P2, where the
-- brief wants it, and where the target table can be chosen deliberately.
-- requirement_fact_candidates is a poor host for it in any case:
-- backend/app/routers/requirement_facts.py:7-20 (AIQ-1821) records that approving a row
-- there moves it into an "Approved" tab no product surface, service or ingestion path
-- reads, and that new extraction work should not build on it.
--
-- SAFETY. Every statement is IF EXISTS, so this is idempotent and a no-op if
-- 20261123000000 was never applied in a given environment. DROP COLUMN on an unreferenced,
-- all-NULL column takes only a brief ACCESS EXCLUSIVE lock and rewrites no heap.
--
-- NO NEW TABLE, so no RLS/policy/REVOKE clause belongs here; the table's RLS posture is
-- unchanged (rowsecurity=true, 2 policies) and is not touched by this migration.
-- ============================================================

DROP INDEX IF EXISTS public.uq_requirement_fact_candidates_fact_uid;

ALTER TABLE public.requirement_fact_candidates
  DROP COLUMN IF EXISTS fact_uid,
  DROP COLUMN IF EXISTS verdict,
  DROP COLUMN IF EXISTS tier,
  DROP COLUMN IF EXISTS verification_depth,
  DROP COLUMN IF EXISTS source_authority_rank,
  DROP COLUMN IF EXISTS corroboration_count,
  DROP COLUMN IF EXISTS contradiction,
  DROP COLUMN IF EXISTS checks_json,
  DROP COLUMN IF EXISTS fetched_at,
  DROP COLUMN IF EXISTS dimension;
