-- ============================================================
-- [P2-5] Completion % — Postgres function + trigger
-- Date: 2026-05-21
--
-- Ensures case_forms.completion_pct is always up to date on
-- EVERY write path to case_form_field_values — not only through
-- the PUT /fields API endpoint (which already calls the Python
-- _compute_completion helper as belt-and-suspenders).
--
-- Write paths this trigger covers that Python code does not:
--   • Pre-Fill Engine inserts (backend/app/services/prefill_engine.py)
--   • Trigger Engine cascade re-fills
--   • Direct Supabase SQL editor inserts (ops / migrations)
--   • Any future Edge Function or external write
--
-- Formula:
--   (filled required fields / total required fields) × 100
--   Falls back to all fields when no fields are marked required.
--   Rounds to nearest integer (ROUND, not FLOOR).
--
-- Tables touched:
--   READ:  public.form_templates.fields (jsonb array of FieldDefinition)
--          public.case_form_field_values (stored values)
--   WRITE: public.case_forms.completion_pct
-- ============================================================


-- ============================================================
-- FUNCTION: compute_completion_pct(p_case_form_id uuid) → int
--
-- Pure-read function — marked STABLE (same inputs → same output
-- within a transaction; does not modify DB state).
-- ============================================================
CREATE OR REPLACE FUNCTION public.compute_completion_pct(p_case_form_id uuid)
RETURNS int
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_total  int;
  v_filled int;
BEGIN
  -- ── Step 1: count required fields in the linked template ──────────────
  SELECT COUNT(*)
  INTO   v_total
  FROM   public.case_forms             cf
  JOIN   public.form_templates         ft  ON ft.id = cf.form_template_id
  CROSS JOIN LATERAL jsonb_array_elements(ft.fields) AS f(val)
  WHERE  cf.id = p_case_form_id
    AND  (f.val->>'required')::boolean = true;

  -- ── No required fields? Fall back to counting ALL template fields ─────
  IF v_total = 0 THEN
    SELECT COUNT(*)
    INTO   v_total
    FROM   public.case_forms             cf
    JOIN   public.form_templates         ft  ON ft.id = cf.form_template_id
    CROSS JOIN LATERAL jsonb_array_elements(ft.fields) AS f(val)
    WHERE  cf.id = p_case_form_id;

    -- Template has no fields at all → return 0
    IF v_total = 0 THEN
      RETURN 0;
    END IF;

    -- Count filled (non-null, non-empty) fields across all template fields
    SELECT COUNT(*)
    INTO   v_filled
    FROM   public.case_forms             cf
    JOIN   public.form_templates         ft  ON ft.id = cf.form_template_id
    CROSS JOIN LATERAL jsonb_array_elements(ft.fields) AS f(val)
    JOIN   public.case_form_field_values fv
           ON  fv.case_form_id = p_case_form_id
           AND fv.field_id     = (f.val->>'id')
    WHERE  cf.id = p_case_form_id
      AND  fv.value IS NOT NULL
      AND  fv.value <> '';

    RETURN ROUND((v_filled::float / v_total) * 100);
  END IF;

  -- ── Step 2: count filled required fields ──────────────────────────────
  SELECT COUNT(*)
  INTO   v_filled
  FROM   public.case_forms             cf
  JOIN   public.form_templates         ft  ON ft.id = cf.form_template_id
  CROSS JOIN LATERAL jsonb_array_elements(ft.fields) AS f(val)
  JOIN   public.case_form_field_values fv
         ON  fv.case_form_id = p_case_form_id
         AND fv.field_id     = (f.val->>'id')
  WHERE  cf.id = p_case_form_id
    AND  (f.val->>'required')::boolean = true
    AND  fv.value IS NOT NULL
    AND  fv.value <> '';

  RETURN ROUND((v_filled::float / v_total) * 100);
END;
$$;

COMMENT ON FUNCTION public.compute_completion_pct(uuid) IS
  '[P2-5] Returns 0-100 completion % for a CaseForm. '
  'Formula: filled_required / total_required × 100. '
  'Falls back to all fields when no required fields defined. '
  'Rounds to nearest integer.';


-- ============================================================
-- TRIGGER FUNCTION: sync_case_form_completion()
--
-- Invoked after any INSERT / UPDATE / DELETE on
-- case_form_field_values. Updates completion_pct on the parent
-- case_form so it stays consistent with the stored values.
-- ============================================================
CREATE OR REPLACE FUNCTION public.sync_case_form_completion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_form_id uuid;
BEGIN
  -- For DELETE we use the OLD row; INSERT and UPDATE use NEW
  v_form_id := CASE WHEN TG_OP = 'DELETE'
               THEN OLD.case_form_id
               ELSE NEW.case_form_id
               END;

  UPDATE public.case_forms
  SET    completion_pct = public.compute_completion_pct(v_form_id),
         updated_at     = now()
  WHERE  id = v_form_id;

  -- Trigger functions must return a row (NEW for INSERT/UPDATE, OLD for DELETE)
  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.sync_case_form_completion() IS
  '[P2-5] Trigger function: recomputes case_forms.completion_pct '
  'after any INSERT/UPDATE/DELETE on case_form_field_values.';


-- ============================================================
-- TRIGGER: trg_sync_completion_pct
--
-- AFTER (not BEFORE) so the write is already committed when we
-- read it back in compute_completion_pct.
-- FOR EACH ROW so we know exactly which case_form_id changed.
-- Idempotent: DROP IF EXISTS before CREATE.
-- ============================================================
DROP TRIGGER IF EXISTS trg_sync_completion_pct ON public.case_form_field_values;

CREATE TRIGGER trg_sync_completion_pct
  AFTER INSERT OR UPDATE OR DELETE
  ON    public.case_form_field_values
  FOR EACH ROW
  EXECUTE FUNCTION public.sync_case_form_completion();


-- ============================================================
-- END
-- ============================================================
-- Reviewer verification steps:
--
-- 1. Apply:  supabase db push
--            (or Supabase MCP apply_migration)
--
-- 2. Confirm functions exist:
--    SELECT proname FROM pg_proc
--    WHERE proname IN ('compute_completion_pct','sync_case_form_completion');
--
-- 3. Confirm trigger exists:
--    SELECT trigger_name FROM information_schema.triggers
--    WHERE event_object_table = 'case_form_field_values'
--      AND trigger_name = 'trg_sync_completion_pct';
--
-- 4. Smoke test (run in a DO block to roll back):
--    See backend/tests/test_completion_pct.py for formula coverage.
--    Postgres integration: insert 5 of 10 required field rows →
--    SELECT completion_pct FROM case_forms WHERE id = '<form_id>'
--    → expect 50.
-- ============================================================
