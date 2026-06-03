-- [AIQ-178] Close CLAUDE.md migration hard-gate #3 for the Dossier & Forms core schema.
--
-- 20260521000000_dossier_forms_core.sql created four public tables with RLS
-- enabled + tenant-scoped policies, but omitted the mandatory
-- "REVOKE ALL ... FROM anon" defense-in-depth grant (CLAUDE.md gate #3).
-- That original migration is already applied, so per the append-only rule the
-- REVOKE is added here in a new file rather than by editing the old one.
--
-- Tables hardened:
--   form_templates, case_forms, case_form_field_values, dossier_packages
--
-- Replay-safe: to_regclass guard skips missing tables; REVOKE is a no-op when
-- no anon grant was present.

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'form_templates',
    'case_forms',
    'case_form_field_values',
    'dossier_packages'
  ]
  LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'skipping missing table public.%', t;
      CONTINUE;
    END IF;
    EXECUTE format('REVOKE ALL ON public.%I FROM anon', t);
  END LOOP;
END$$;
