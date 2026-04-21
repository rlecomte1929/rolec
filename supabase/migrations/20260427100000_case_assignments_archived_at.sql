-- Soft-delete columns for case_assignments + relocation_cases.
-- Previously db.delete_assignment() did a cascading hard DELETE with no audit
-- trail, no reversibility, and wiping the parent relocation_cases row in the
-- same transaction. Adding archived_at lets the delete path set the flag and
-- leaves the rows intact for investigation / restore.
--
-- Companion code change: backend/database.py:delete_assignment now sets
-- archived_at + writes audit_logs rows; listing queries filter by
-- archived_at IS NULL. See PR for the full diff.

ALTER TABLE IF EXISTS public.case_assignments
  ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL;

ALTER TABLE IF EXISTS public.relocation_cases
  ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL;

-- Partial indexes skip the (usually large) active-rows subset and only cover
-- archived rows so the "show archived" path (admin investigation) is cheap.
CREATE INDEX IF NOT EXISTS idx_case_assignments_archived_at
  ON public.case_assignments (archived_at)
  WHERE archived_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_relocation_cases_archived_at
  ON public.relocation_cases (archived_at)
  WHERE archived_at IS NOT NULL;
