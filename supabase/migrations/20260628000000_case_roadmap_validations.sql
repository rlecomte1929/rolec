-- Records the employee's "validate roadmap before execution" checkpoint.
-- New public table → RLS hard-gate (enable + tenant policy + revoke anon).

CREATE TABLE IF NOT EXISTS public.case_roadmap_validations (
  canonical_case_id     text PRIMARY KEY,
  validated_at          timestamptz NOT NULL DEFAULT now(),
  validated_by_user_id  text,
  created_at            timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.case_roadmap_validations ENABLE ROW LEVEL SECURITY;

-- Employee/HR who own the case can read their validation row (mirrors
-- case_milestones_select). canonical_case_id matches ca.case_id or
-- ca.canonical_case_id, same as the milestones policy.
DROP POLICY IF EXISTS case_roadmap_validations_select ON public.case_roadmap_validations;
CREATE POLICY case_roadmap_validations_select ON public.case_roadmap_validations
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE (ca.case_id = case_roadmap_validations.canonical_case_id
             OR ca.canonical_case_id = case_roadmap_validations.canonical_case_id)
        AND (ca.employee_user_id = auth.uid()::text OR ca.hr_user_id = auth.uid()::text)
    )
  );

DROP POLICY IF EXISTS case_roadmap_validations_all ON public.case_roadmap_validations;
CREATE POLICY case_roadmap_validations_all ON public.case_roadmap_validations
  FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON public.case_roadmap_validations FROM anon;
