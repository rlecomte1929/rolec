-- ============================================================
-- [P4-5] Submission tracking — rejection_reason and
--        corrected_by_form_id on case_forms.
--
-- rejection_reason: free-text reason stored when HR/specialist
--   rejects a form so the employee can see it in the rejection
--   banner.
-- corrected_by_form_id: when a rejected form is re-opened and a
--   corrected version is created, point to the new form.
-- ============================================================

ALTER TABLE public.case_forms
  ADD COLUMN IF NOT EXISTS rejection_reason     text,
  ADD COLUMN IF NOT EXISTS corrected_by_form_id uuid
    REFERENCES public.case_forms(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.case_forms.rejection_reason IS
  '[P4-5] Free-text reason provided by the specialist when rejecting '
  'the form. Shown to the employee in the rejection banner.';

COMMENT ON COLUMN public.case_forms.corrected_by_form_id IS
  '[P4-5] FK to a new case_form created to replace this rejected form '
  '(correction flow). NULL until a correction form is submitted.';
