-- TD-FIX-2 hotfix (AIQ-1503): test_sessions.tester_segment was NOT NULL with a
-- default of 'prospect'. Under the single-link test-drive model the segment is
-- genuinely UNKNOWN at provision — the tester self-identifies later in the survey —
-- so the app now writes NULL for it. That NULL violated the NOT NULL constraint and
-- 500'd provisioning for the single link (the campaign's main path). Make the column
-- nullable (NULL = "unknown"), drop the misleading default, and constrain the valid
-- non-null values to {internal, prospect} to back up the app-layer pydantic check.
--
-- Applied to production out-of-band on 2026-07-13 via execute_sql (hotfix for a live
-- provisioning outage); this file reconciles the migration ledger. Idempotent.

ALTER TABLE public.test_sessions ALTER COLUMN tester_segment DROP NOT NULL;
ALTER TABLE public.test_sessions ALTER COLUMN tester_segment DROP DEFAULT;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'test_sessions_tester_segment_check'
  ) THEN
    ALTER TABLE public.test_sessions
      ADD CONSTRAINT test_sessions_tester_segment_check
      CHECK (tester_segment IN ('internal', 'prospect'));
  END IF;
END $$;
