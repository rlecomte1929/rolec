-- [CASE-BRIDGE / AIQ-1720 S4] Follow-up backfill of public.cases from relocation_cases.
--
-- Re-runs the eligibility-gated backfill first shipped in
-- 20260624000000_case_bridge_backfill_public_cases.sql, VERBATIM, to capture cases
-- that have become eligible since (gained a valid company_id / employee profile /
-- countries). As of 2026-07-27: 168 of 748 relocation_cases have a public.cases row;
-- of the 580 missing, only 26 satisfy every public.cases constraint and are still
-- missing — this migration inserts exactly those 26.
--
-- The remaining ~555 are NOT a backfill bug: they are incomplete pre-launch test
-- data that cannot satisfy public.cases' FK/NOT NULL constraints (no uuid company_id
-- in public.companies, no matching public.profiles employee, or a NULL country) —
-- exactly the rows the forward bridge (backend/db/cases.py) also skips. They resolve
-- naturally once the data is completed, or as part of the pre-launch data reset
-- (see AIQ-1720 S2/S3, deferred). See docs/architecture/CASE_ID_UNIFICATION_AUDIT.md.
--
-- Idempotent: NOT EXISTS + ON CONFLICT (id) DO NOTHING make re-runs and application
-- after the forward bridge has populated more rows safe no-ops. public.cases already
-- has RLS; this is a data-only INSERT and touches no policy/grant.

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
