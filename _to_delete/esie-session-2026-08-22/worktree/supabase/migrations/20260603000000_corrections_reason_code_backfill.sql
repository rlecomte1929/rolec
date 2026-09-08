-- ─────────────────────────────────────────────────────────────────────────────
-- AIQ-554 / C2-03 — Reason-code taxonomy lock-in + correction backfill
--
-- The rce.corrections.reason_code CHECK enum (6 values) and NOT NULL constraint
-- were established in C1-01 (20260528020000_relopass_case_engine_v1.sql):
--
--   OCR_ERROR, TYPO_IN_SOURCE, AMBIGUOUS_PARTICLE,
--   LEGITIMATE_VARIATION, FRAUD_SUSPECTED, OTHER
--
-- This migration is the C2-03 *backfill*: any legacy Cohort-1 correction row
-- that pre-dates the NOT NULL enforcement (e.g. ingested before C1-01 hardened
-- the column, or loaded via a bulk path that skipped the constraint) is set to
-- 'OTHER'. It is fully idempotent and no-ops when there are zero NULL rows.
--
-- NO new public table is created here, so the SEC-003 RLS gate does not apply.
-- This is a backfill on the existing rce.corrections table only.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
  affected INT := 0;
BEGIN
  -- Guard: only run if the table exists (defensive across partial-replay envs).
  IF to_regclass('rce.corrections') IS NULL THEN
    RAISE NOTICE 'AIQ-554 backfill skipped: rce.corrections does not exist';
    RETURN;
  END IF;

  UPDATE rce.corrections
     SET reason_code = 'OTHER',
         updated_at  = now()
   WHERE reason_code IS NULL;

  GET DIAGNOSTICS affected = ROW_COUNT;
  RAISE NOTICE 'AIQ-554 backfill: % correction row(s) set to OTHER', affected;
END $$;
