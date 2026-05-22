-- ============================================================
-- [P4-6] AI confidence improvement loop
--
-- Adds field_value_overrides table to track every time an
-- employee or specialist corrects an AI-prefilled field value.
-- Powers the admin accuracy report that flags per-field
-- override rates > 20% as 'Low accuracy'.
-- ============================================================

-- TABLE: field_value_overrides
CREATE TABLE IF NOT EXISTS public.field_value_overrides (
  id                  uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  case_form_id        uuid         NOT NULL REFERENCES public.case_forms(id) ON DELETE CASCADE,
  form_template_id    uuid         NOT NULL REFERENCES public.form_templates(id),
  field_id            text         NOT NULL,
  original_value      text,
  corrected_value     text,
  original_confidence real,                    -- ai_confidence at time of override
  overridden_by       text         NOT NULL    -- 'employee' | 'specialist'
                        CHECK (overridden_by IN ('employee', 'specialist')),
  created_at          timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.field_value_overrides IS
  '[P4-6] Audit log of every AI-prefilled field that was corrected by a human. '
  'Used by the admin accuracy report to flag low-accuracy prefill fields.';

-- Indexes for the accuracy report query
CREATE INDEX IF NOT EXISTS idx_fvo_form_template_field
  ON public.field_value_overrides (form_template_id, field_id);

CREATE INDEX IF NOT EXISTS idx_fvo_case_form_field
  ON public.field_value_overrides (case_form_id, field_id);

-- ── RLS ──────────────────────────────────────────────────────────────────────
ALTER TABLE public.field_value_overrides ENABLE ROW LEVEL SECURITY;

-- Service role (backend) has full access
CREATE POLICY "service role full access on field_value_overrides"
  ON public.field_value_overrides
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Admins can read for the accuracy report
CREATE POLICY "admin read field_value_overrides"
  ON public.field_value_overrides
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id = (SELECT auth.uid())
        AND role IN ('admin', 'hr')
    )
  );
