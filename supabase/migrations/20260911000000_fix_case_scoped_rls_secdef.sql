-- AIQ-1489 follow-up — fix RLS policies that raise 42501 instead of filtering.
--
-- Three tables' policies subquery a table the caller cannot SELECT. RLS
-- subqueries run under the *caller's* grants (RLS does not confer SELECT), so
-- PostgREST/authenticated reads raise `42501 permission denied` for the inner
-- table rather than filtering — the row is never returned and the request 500s:
--
--   pets.pets_via_case            -> subqueries public.cases   (authenticated has no grant)
--   case_forms.case_forms_via_case-> subqueries public.cases   (authenticated has no grant)
--   provider_tasks.*_hr_all       -> subqueries public.hr_users (no grant)
--   provider_tasks.*_provider_*   -> subqueries providers JOIN vendor_users (no grant)
--
-- pets is read directly from the frontend (PetRequirementsSection.tsx), so the
-- pet-import section 500s for every authenticated user. AIQ-1366 granted SELECT
-- on pets but that was necessary-not-sufficient: the policy's `cases` subquery
-- still fails.
--
-- Fix: move each cross-table lookup into a SECURITY DEFINER helper (the pattern
-- already used by my_company_id / my_role / hr_company_ids), so the lookup runs
-- as the function owner and needs no caller grant.
--
-- Isolation is unchanged. For pets + case_forms the tenant-scoping predicate is
-- copied verbatim (`x IN (SELECT id FROM cases WHERE P)` is rewritten as the
-- equivalent `EXISTS (SELECT 1 FROM cases WHERE id = x AND P)`). For
-- provider_tasks_hr_all the predicate is *substituted*, not copied: the original
-- inlined `org_id IN (SELECT hr_users.company_id WHERE profile_id = auth.uid())`,
-- and we reuse the existing hr_company_ids() helper, which resolves the same set
-- via `profile_id = (select auth.uid())::text`. Same intent, different expression.
--
-- Validated: C0 HR still sees exactly their own case_forms (46 of 67), zero
-- cross-tenant. Idempotent.

-- 1. Case-ownership helper for pets + case_forms (verbatim of the old inline predicate).
CREATE OR REPLACE FUNCTION public.user_owns_case_row(p_case_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public'
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.cases c
    WHERE c.id = p_case_id
      AND ( c.employee_id = (SELECT auth.uid())
            OR ( c.company_id = public.my_company_id()
                 AND public.my_role() = ANY (ARRAY['hr','admin']) ) )
  );
$$;
-- Postgres grants EXECUTE to PUBLIC by default, which would expose this as an
-- anon-callable PostgREST RPC (/rest/v1/rpc/user_owns_case_row). Revoke first,
-- then grant narrowly — same shape as hr_company_ids() in 20260531010000.
REVOKE ALL ON FUNCTION public.user_owns_case_row(uuid) FROM public;
GRANT EXECUTE ON FUNCTION public.user_owns_case_row(uuid) TO authenticated, service_role;

-- 2. Provider-membership helper for provider_tasks (verbatim of the old inline predicate).
CREATE OR REPLACE FUNCTION public.user_provider_ids()
RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public'
AS $$
  SELECT p.id
  FROM public.providers p
  JOIN public.vendor_users vu ON vu.vendor_id = p.vendor_id
  WHERE vu.user_id = (SELECT auth.uid());
$$;
REVOKE ALL ON FUNCTION public.user_provider_ids() FROM public;
GRANT EXECUTE ON FUNCTION public.user_provider_ids() TO authenticated, service_role;

-- 3. pets — replace the cases-subquery policy with the helper.
DROP POLICY IF EXISTS pets_via_case ON public.pets;
CREATE POLICY pets_via_case ON public.pets
  FOR ALL TO authenticated
  USING (public.user_owns_case_row(case_id))
  WITH CHECK (public.user_owns_case_row(case_id));

-- 4. case_forms — same fix.
DROP POLICY IF EXISTS case_forms_via_case ON public.case_forms;
CREATE POLICY case_forms_via_case ON public.case_forms
  FOR ALL TO authenticated
  USING (public.user_owns_case_row(case_id))
  WITH CHECK (public.user_owns_case_row(case_id));

-- 5. provider_tasks — HR path via existing hr_company_ids() (org_id is text; matches
--    the original `org_id IN (SELECT hr_users.company_id WHERE profile_id = auth.uid())`),
--    provider paths via user_provider_ids(). The JWT-claim policies were never broken
--    and are left untouched.
DROP POLICY IF EXISTS provider_tasks_hr_all ON public.provider_tasks;
CREATE POLICY provider_tasks_hr_all ON public.provider_tasks
  FOR ALL TO authenticated
  USING (org_id IN (SELECT public.hr_company_ids()));

DROP POLICY IF EXISTS provider_tasks_provider_select ON public.provider_tasks;
CREATE POLICY provider_tasks_provider_select ON public.provider_tasks
  FOR SELECT TO authenticated
  USING (provider_id IN (SELECT public.user_provider_ids()));

DROP POLICY IF EXISTS provider_tasks_provider_update ON public.provider_tasks;
CREATE POLICY provider_tasks_provider_update ON public.provider_tasks
  FOR UPDATE TO authenticated
  USING (provider_id IN (SELECT public.user_provider_ids()))
  WITH CHECK (provider_id IN (SELECT public.user_provider_ids()));
