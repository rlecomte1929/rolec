-- [P4-3] Ad-hoc "Add document" support on case_forms.
-- Lets HR attach a custom document that has no FieldDefinition-backed
-- form_template. We reuse the existing public.case_forms table rather than
-- introducing a new table (no new RLS surface).

-- An ad-hoc form has no template, so the FK column must be nullable.
ALTER TABLE public.case_forms ALTER COLUMN form_template_id DROP NOT NULL;

ALTER TABLE public.case_forms
  ADD COLUMN IF NOT EXISTS is_adhoc        boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS adhoc_name      text,
  ADD COLUMN IF NOT EXISTS adhoc_authority text,
  ADD COLUMN IF NOT EXISTS notes           text;

COMMENT ON COLUMN public.case_forms.is_adhoc        IS '[P4-3] true when this is an ad-hoc "Add document" entry with no form_template.';
COMMENT ON COLUMN public.case_forms.adhoc_name      IS '[P4-3] display name for an ad-hoc form (no template to derive it from).';
COMMENT ON COLUMN public.case_forms.adhoc_authority IS '[P4-3] issuing authority label for an ad-hoc form.';
COMMENT ON COLUMN public.case_forms.notes           IS '[P4-3] optional free-text notes captured on the Add-document modal.';
