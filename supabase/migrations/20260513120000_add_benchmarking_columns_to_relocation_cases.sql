-- AIQ-97: Add compliance_flag and delay_reason to relocation_cases
-- Required by the nightly-stats Edge Function for benchmarking computations.
-- Applied to Supabase (nsvefcvpvwwwhuqyuqmp) on 2026-05-13.

ALTER TABLE relocation_cases
  ADD COLUMN IF NOT EXISTS compliance_flag BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS delay_reason    TEXT;

COMMENT ON COLUMN relocation_cases.compliance_flag IS
  'True if this case has had a compliance incident (missed deadline, unauthorised work, etc). Set by HR or compliance automation.';

COMMENT ON COLUMN relocation_cases.delay_reason IS
  'Free-text or enum reason for delay, e.g. missing_docs, embassy_appointment, degree_recognition. Used in nightly benchmarking top_delay_causes computation.';
