-- [CASE-BRIDGE] One-time backfill of public.cases from existing relocation_cases.
--
-- The canonical-case bridge (backend/db/cases.py apply_wizard_patch_side_effects)
-- upserts wizard intakes into public.cases, but it was silently failing on
-- cases_purpose_check for ~every case (it inserted purpose='relocation', which the
-- constraint rejects). That forward bug is fixed separately (the _CASE_PURPOSE_MAP
-- change). This migration backfills the cases that already exist in
-- relocation_cases but never got a public.cases row, so the document/forms/dossier
-- subsystem (which FKs to public.cases) works for them too.
--
-- Only cases whose data satisfies every public.cases constraint are backfilled:
--   * company_id is a uuid present in public.companies (cases_company_id_fkey),
--   * the assignment's employee resolves to a public.profiles row (cases.employee_id FK),
--   * both countries are present (origin/dest_country_code are NOT NULL).
-- Incomplete rows (most of the pre-launch test data) are skipped — the bridge
-- itself returns early on the same missing data. Validated against prod in a
-- rollback transaction: 47 rows inserted, no constraint violation.
--
-- purpose := 'work' (a cases_purpose_check-valid value and the column default);
-- relocation_cases has no purpose column to derive from.
--
-- Idempotent: the NOT EXISTS guard + ON CONFLICT (id) DO NOTHING make re-runs and
-- application after the forward bridge has populated more rows safe no-ops.

INSERT INTO public.cases
  (id, company_id, employee_id, origin_country_code, dest_country_code, dest_city,
   purpose, status, stage, target_move_date, created_at, updated_at)
SELECT DISTINCT ON (rc.id)
  rc.id,
  rc.company_id::uuid,
  p.id,
  rc.home_country,
  rc.host_country,
  rc.host_city,
  'work',
  'active',
  'discovery',
  rc.expected_start_date,
  now(),
  now()
FROM public.relocation_cases rc
JOIN public.case_assignments ca
  ON (ca.canonical_case_id = rc.id::text OR ca.case_id = rc.id::text)
JOIN public.profiles p
  ON p.id::text = ca.employee_user_id
JOIN public.companies co
  ON co.id = rc.company_id::uuid
WHERE NOT EXISTS (SELECT 1 FROM public.cases c WHERE c.id = rc.id)
  AND rc.company_id ~ '^[0-9a-f-]{36}$'
  AND rc.home_country IS NOT NULL
  AND rc.host_country IS NOT NULL
ORDER BY rc.id, ca.intake_updated_at DESC NULLS LAST
ON CONFLICT (id) DO NOTHING;
