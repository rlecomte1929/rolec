-- Indexes for assignment + case listing hot paths.
-- Prior to this migration these queries scanned case_assignments and
-- relocation_cases sequentially; at low thousands of rows that's fine, at
-- tens of thousands the HR dashboard and command center get slow.
--
-- Partial index idioms:
--   - case_assignments(hr_user_id, created_at DESC) covers the HR list query
--     filtered by owner. Archived rows are excluded via partial predicate so
--     the index is smaller and stays useful after soft-deletes.
--   - relocation_cases(company_id, created_at DESC) covers company-scoped
--     case listings. Same archived-row exclusion.
--   - case_assignments(employee_user_id) covers the employee-portal lookup
--     that runs on every authenticated page load. Partial on non-null so
--     unassigned assignments don't bloat the index.

CREATE INDEX IF NOT EXISTS idx_case_assignments_hr_user_created_at
  ON public.case_assignments (hr_user_id, created_at DESC)
  WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_relocation_cases_company_created_at
  ON public.relocation_cases (company_id, created_at DESC)
  WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_case_assignments_employee_user
  ON public.case_assignments (employee_user_id)
  WHERE employee_user_id IS NOT NULL AND archived_at IS NULL;

-- case_id lookups (get_assignment_by_case_id, cascade soft-deletes).
CREATE INDEX IF NOT EXISTS idx_case_assignments_case_id
  ON public.case_assignments (case_id)
  WHERE archived_at IS NULL;
