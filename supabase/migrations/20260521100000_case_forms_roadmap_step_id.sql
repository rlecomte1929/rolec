-- [P1-6] Links each CaseForm to the roadmap step that triggered it.
-- Allows the GET /api/cases/{id}/roadmap/tracks endpoint to aggregate
-- document counts per step for the employee Roadmap chip.

ALTER TABLE public.case_forms
  ADD COLUMN IF NOT EXISTS roadmap_step_id uuid REFERENCES public.roadmap_steps(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.case_forms.roadmap_step_id IS
  '[P1-6] Links each CaseForm to the roadmap step that triggered it.';

CREATE INDEX IF NOT EXISTS idx_case_forms_roadmap_step_id
  ON public.case_forms (roadmap_step_id);
