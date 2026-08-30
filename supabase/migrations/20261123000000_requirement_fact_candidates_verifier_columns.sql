-- ============================================================
-- Corridor Verifier Service P1 — verifier columns on requirement_fact_candidates
-- ============================================================
--
-- Additive only: nine verdict columns from the Verifier P1 brief, plus `fact_uid`.
--
-- WHY fact_uid IS HERE AND NOT IN THE BRIEF. The brief requires the V0 upsert to be
-- "idempotent by fact_uid", but the live table has no such column — its columns are
-- id, created_at, source_url, corridor, requirement_type, fact_text, confidence_score,
-- source_quote, extraction_method, status, reviewed_by, reviewed_at (measured against
-- prod 2026-08-30). `id` is a uuid the table generates, so it cannot carry a batch's
-- own identifier, and there is no natural key to ON CONFLICT against. Without fact_uid
-- the idempotency requirement is unimplementable, so it is added here.
--
-- The unique index is on a NULLABLE column: Postgres permits many NULLs in a UNIQUE
-- index, so the 23 rows already in the table (all pre-verifier, no fact_uid) are
-- unaffected and no backfill is required.
--
-- NO NEW TABLE, so no RLS/policy/REVOKE clause belongs here — this is an ALTER on an
-- existing table whose RLS posture is unchanged (measured: rowsecurity=true, 2 policies).
-- Stated explicitly so a reviewer applying the "every new public table needs RLS" gate
-- does not go looking for one.
--
-- ⚠️ READ THIS BEFORE APPLYING — the target table is documented in this repo as a dead end.
-- `backend/app/routers/requirement_facts.py:7-20` (AIQ-1821):
--     "requirement_fact_candidates is a dead end: approving a row here moves it into an
--      'Approved' tab that no product surface, service or ingestion path reads. ...
--      Prefer the official-ingest route for new extraction work. This router and its 13
--      existing rows are kept for review/audit; do not build on them."
-- The verifier's *landing* step writes public.requirement_facts, which IS the live path
-- (admin approve -> list_approved_requirement_facts -> compute_requirements_sufficiency).
-- This migration is applied as specified in the P1 brief; the staging hop through this
-- table is flagged for a design decision and is NOT load-bearing for the landing step.
--
-- IDEMPOTENT: every statement is IF NOT EXISTS. Safe to re-run.
-- ============================================================

ALTER TABLE public.requirement_fact_candidates
  ADD COLUMN IF NOT EXISTS fact_uid              text,
  ADD COLUMN IF NOT EXISTS verdict               text,
  ADD COLUMN IF NOT EXISTS tier                  text,
  ADD COLUMN IF NOT EXISTS verification_depth    text,
  ADD COLUMN IF NOT EXISTS source_authority_rank integer,
  ADD COLUMN IF NOT EXISTS corroboration_count   integer,
  ADD COLUMN IF NOT EXISTS contradiction         boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS checks_json           jsonb,
  ADD COLUMN IF NOT EXISTS fetched_at            timestamptz,
  ADD COLUMN IF NOT EXISTS dimension             text;

-- The idempotency key for the V0 upsert. Partial (WHERE NOT NULL) so it indexes only
-- verifier-written rows and stays small; pre-existing rows never enter it.
CREATE UNIQUE INDEX IF NOT EXISTS uq_requirement_fact_candidates_fact_uid
  ON public.requirement_fact_candidates (fact_uid)
  WHERE fact_uid IS NOT NULL;

COMMENT ON COLUMN public.requirement_fact_candidates.fact_uid IS
  'Batch-supplied stable id for one fact. The verifier upserts ON CONFLICT (fact_uid); '
  'NULL on the 23 rows that predate the verifier.';

COMMENT ON COLUMN public.requirement_fact_candidates.verdict IS
  'Verifier outcome for this fact: pass | flag | reject. Machine-written. Never a '
  'statement that a human approved it — that is review_status on requirement_items.';

COMMENT ON COLUMN public.requirement_fact_candidates.checks_json IS
  'Per-check detail for one fact (V0-V3): which gate ran, its verdict and why. The '
  'audit trail behind `verdict`.';
