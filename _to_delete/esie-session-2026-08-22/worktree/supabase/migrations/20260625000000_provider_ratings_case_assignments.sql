-- CATALOG-3 / AIQ-1067 follow-up — re-point provider_ratings at the employee
-- assignment id space.
--
-- The initial table FK'd case_id to public.cases, but the live employee flow
-- uses public.case_assignments (a separate id space under the case-identity
-- schism). case_assignments.id is TEXT (559/567 uuid-shaped, 8 non-uuid), so a
-- rating against a real assignment 404'd / couldn't be stored. Fix:
--   * case_id: uuid -> text, drop the public.cases FK (id space is in flux;
--     ownership is validated app-side against case_assignments).
--   * company_id: relax NOT NULL — resolved best-effort from the employee
--     profile; a missing company must not break rating capture.
-- Safe: provider_ratings has 0 rows in prod.

ALTER TABLE public.provider_ratings DROP CONSTRAINT IF EXISTS provider_ratings_case_id_fkey;
ALTER TABLE public.provider_ratings ALTER COLUMN case_id TYPE text USING case_id::text;
ALTER TABLE public.provider_ratings ALTER COLUMN company_id DROP NOT NULL;

COMMENT ON COLUMN public.provider_ratings.case_id IS
  'case_assignments.id (text id space; no FK — validated app-side via employee_user_id).';
