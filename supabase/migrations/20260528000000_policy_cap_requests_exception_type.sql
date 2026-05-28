-- Add `exception_type` axis to policy_cap_requests (Q3-A resolution)
-- ─────────────────────────────────────────────────────────────────────────────
-- Until now `policy_cap_requests.category` was doing two unrelated jobs:
--   - the SERVICE category (housing, schools, movers, ...) — written by
--     RequestExceptionModal when an employee/HR opens an exception against a
--     service estimate; many possible values, free-form
--   - the EXCEPTION TYPE — what kind of policy deviation is being requested
--     (new_category, cap_override, timeline_extension, additional_coverage) —
--     used by the HR exceptions inbox UI, exactly 4 values
--
-- This migration carves the second axis into its own column with a CHECK so
-- both meanings are typed and the inbox UI no longer has to guess via a
-- client-side mapping table. Backward-compatible:
--   - Column is NULLABLE so legacy rows and current-flow inserts keep working
--   - Existing rows: backfill is intentionally NULL (we don't have enough
--     signal in `category` alone to safely infer the exception type)
--   - Frontend mapping: prefer `exception_type` when present, fall back to
--     the existing client-side mapping when NULL
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.policy_cap_requests
  ADD COLUMN IF NOT EXISTS exception_type TEXT;

ALTER TABLE public.policy_cap_requests
  DROP CONSTRAINT IF EXISTS policy_cap_requests_exception_type_check;

ALTER TABLE public.policy_cap_requests
  ADD CONSTRAINT policy_cap_requests_exception_type_check
  CHECK (
    exception_type IS NULL
    OR exception_type IN (
      'new_category',
      'cap_override',
      'timeline_extension',
      'additional_coverage'
    )
  );

-- Index for the HR inbox filter view (status + exception_type are the two
-- most-common predicates in the queue dashboard).
CREATE INDEX IF NOT EXISTS idx_policy_cap_requests_exception_type
  ON public.policy_cap_requests (exception_type, status, created_at DESC);

COMMENT ON COLUMN public.policy_cap_requests.exception_type IS
  'Q3-A: HR-inbox exception-type axis. One of new_category, cap_override, '
  'timeline_extension, additional_coverage. Distinct from the service-category '
  '`category` column. NULL on legacy rows and during the transition window.';

COMMENT ON COLUMN public.policy_cap_requests.category IS
  'Service-category axis (housing, schools, movers, insurance, ...). Written '
  'by RequestExceptionModal when an employee/HR opens an exception against a '
  'service estimate. See `exception_type` for the orthogonal HR-inbox axis.';
