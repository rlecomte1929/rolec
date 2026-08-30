-- ============================================================
-- Somewhere to record whether an Otto fact's quote is actually on its page
-- ============================================================
--
-- WHY. The Otto path — NDJSON -> otto_staging.immigration_fact_candidates ->
-- public.requirement_items — has no evidence verification anywhere in it. Measured
-- 2026-08-30:
--
--   * `backend/imports/otto/verifier.py` defers quote grounding (V3) to
--     `backend/app/services/fact_evidence.py` in its own docstring, and never calls it.
--   * This table carries `evidence_quote` and NOTHING that says whether that quote was
--     ever checked against the page it cites.
--   * `parsers.grade()` therefore sets `accuracy_tier` from publisher + quote-presence
--     alone. `auto_accepted` means "no gate objected on the day this was staged", not
--     "someone confirmed this quote".
--
-- What that costs, measured on the NO→FR transition batch (Denis's corridor, 15 facts,
-- all `auto_accepted`, docs/imports/no-fr-transition-requirements-2026-08-22/): only 3
-- of 15 quotes are verifiably on the page they cite, and one was proven to be a
-- paraphrase — the right page, but not its words. Nothing in the pipeline noticed,
-- because there is no column in which noticing could be written down.
--
-- The one place grounding does happen is `public.requirement_facts`
-- (evidence_verified / evidence_offset / evidence_checked_at, 357 true rows, written by
-- backend/scripts/backfill_fact_evidence.py). That is a DIFFERENT pipeline feeding a
-- different consumer. These three columns deliberately take the SAME NAMES so there is
-- one mental model for "was this quote checked", not two.
--
-- TRI-STATE, and it matters. `fact_evidence.check_evidence(...).verified` returns:
--     True   the quote is in the source, character-for-character modulo normalisation
--     False  same language, source in hand, quote NOT there  <- the damning case
--     None   the check DID NOT APPLY (no readable source, or a language mismatch that
--            makes a substring match impossible by construction)
-- NULL here therefore means "never checked" or "did not apply", never "failed".
-- `evidence_checked_at` is what separates the two: set, with NULL verified, means the
-- check ran and could not decide. The consuming downgrade in grade() tests `is False`
-- precisely so that a NULL never silently drops the tier of a historical row whose
-- review has already happened.
--
-- NO NEW TABLE, so no RLS/policy/REVOKE clause belongs here. otto_staging is not exposed
-- through PostgREST and this ALTER does not change that.
--
-- IDEMPOTENT: every statement IF NOT EXISTS. Safe to re-run.
-- ============================================================

ALTER TABLE otto_staging.immigration_fact_candidates
  ADD COLUMN IF NOT EXISTS evidence_verified   boolean,
  ADD COLUMN IF NOT EXISTS evidence_offset     integer,
  ADD COLUMN IF NOT EXISTS evidence_checked_at timestamptz;

COMMENT ON COLUMN otto_staging.immigration_fact_candidates.evidence_verified IS
  'Tri-state, mirroring public.requirement_facts.evidence_verified. TRUE = the quote was '
  'found on the cited page. FALSE = the page was read and the quote is not in it. NULL = '
  'never checked, or the check could not apply (unreadable source, language mismatch). '
  'Written by the verifier V3 gate; read by parsers.grade() with `is False`, never falsiness.';

COMMENT ON COLUMN otto_staging.immigration_fact_candidates.evidence_offset IS
  'Character index of the quote within the NORMALISED source text, or NULL unless verified. '
  'Lets a reviewer see the quote in its surrounding context rather than taking it on trust.';

COMMENT ON COLUMN otto_staging.immigration_fact_candidates.evidence_checked_at IS
  'When V3 last ran for this row. Set with a NULL evidence_verified means the check ran and '
  'did not apply — which is different from never having run, and is why re-grading can tell '
  'a stale row from an unverifiable one.';
