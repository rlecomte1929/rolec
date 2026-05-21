-- ============================================================
-- [P1-3] case_forms — add dependent_id + fix unique constraint
-- Date: 2026-05-21
--
-- Problem: the original UNIQUE(case_id, form_template_id, person_id) constraint
-- in the P1-1 migration cannot guarantee idempotency for dependent-specific
-- CaseForms (spouse, each_child) because those forms have person_id = NULL,
-- and Postgres treats NULLs as distinct in unique constraints — so re-firing
-- the same trigger event would create duplicate rows.
--
-- Fix:
--   1. Add dependent_id uuid → case_dependents (nullable) to carry the
--      case_dependents.id for forms that belong to a dependent rather than
--      the primary employee profile.
--   2. Drop the old unique constraint.
--   3. Add UNIQUE NULLS NOT DISTINCT on (case_id, form_template_id,
--      person_id, dependent_id) so that (NULL, NULL) compares equal and
--      ON CONFLICT DO NOTHING correctly deduplicates on re-trigger.
--
-- NULLS NOT DISTINCT requires Postgres 15+ (Supabase default — safe).
-- ============================================================

-- 1. Add dependent_id column (nullable FK to case_dependents)
ALTER TABLE public.case_forms
  ADD COLUMN IF NOT EXISTS dependent_id uuid
    REFERENCES public.case_dependents(id) ON DELETE SET NULL;

-- 2. Drop the old unique constraint (created in 20260521000000_dossier_forms_core.sql)
ALTER TABLE public.case_forms
  DROP CONSTRAINT IF EXISTS case_forms_unique_person;

-- 3. Add the new idempotency-safe unique constraint
--    NULLS NOT DISTINCT: two NULLs are treated as equal so ON CONFLICT
--    correctly fires even when both person_id and dependent_id are NULL.
ALTER TABLE public.case_forms
  ADD CONSTRAINT case_forms_unique_person_dep
    UNIQUE NULLS NOT DISTINCT (case_id, form_template_id, person_id, dependent_id);

-- 4. Index on dependent_id for lookups in the Trigger Engine second pass
CREATE INDEX IF NOT EXISTS idx_case_forms_dependent_id
  ON public.case_forms (dependent_id)
  WHERE dependent_id IS NOT NULL;

-- ============================================================
-- END
-- ============================================================
