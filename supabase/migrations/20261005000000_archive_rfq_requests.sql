-- AIQ-1683 · Archive the retired HR-initiated `rfq_requests` model.
--
-- Two-models consolidation, S3/4. With the HR read repointed to canonical `rfqs`
-- (S1, #1641), the HR-initiated create/update removed (S2, #1642), and the last
-- reader (`hr_rfq.list_rfqs` GET) removed in this same PR, `public.rfq_requests`
-- has zero live consumers. Per Romain's decision we ARCHIVE — rename → `_legacy`
-- and make it read-only, PRESERVING the rows — rather than migrating them into the
-- canonical model. Mirrors `20260719210652_rename_vendors_to_vendors_legacy.sql`.
--
-- Indexes (`rfq_requests_pkey`, `rfq_requests_case_id_idx`) and the RLS policies
-- (`rfq_requests_hr_{insert,read,update}`) follow the table on RENAME — their names
-- do not need to match the new table name, so they are intentionally left as-is.
--
-- Idempotent: every step is guarded on table existence so a re-run or a fresh
-- Supabase Preview replay is a no-op. Validated on the real prod schema in a
-- rolled-back transaction (old→null, new set, 51 rows preserved, write grants 0).
--
-- Applied OUT-OF-BAND by the operator + ledger reconciled — never `apply_migration`
-- to prod (see CLAUDE.md "Migration discipline (MANDATORY)").

-- 1) Rename rfq_requests → rfq_requests_legacy.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'rfq_requests'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'rfq_requests_legacy'
  ) THEN
    ALTER TABLE public.rfq_requests RENAME TO rfq_requests_legacy;
  END IF;
END $$;

-- 2) Make the archive read-only: revoke write grants (defense-in-depth on top of
--    the RLS policies that came across with the rename). Idempotent — revoking an
--    absent grant is a no-op. Guarded on the renamed table existing.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'rfq_requests_legacy'
  ) THEN
    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON public.rfq_requests_legacy FROM authenticated';
    EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON public.rfq_requests_legacy FROM anon';
  END IF;
END $$;
