-- AIQ-2358: employee_tasks was created without RLS and was deferred from
-- 20260605200000_data_api_opt_out.sql. FastAPI uses the service role / postgres
-- role and is unaffected. This is the PostgREST defense-in-depth boundary so
-- the shipped anon key cannot read another employee's tasks.
--
-- Hard gates: ENABLE RLS + tenant-scoped policy + REVOKE anon.

ALTER TABLE public.employee_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS employee_tasks_select_own ON public.employee_tasks;
CREATE POLICY employee_tasks_select_own ON public.employee_tasks
  FOR SELECT
  USING (employee_id = (SELECT auth.uid()::text));

DROP POLICY IF EXISTS employee_tasks_service_role_all ON public.employee_tasks;
CREATE POLICY employee_tasks_service_role_all ON public.employee_tasks
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

REVOKE ALL ON public.employee_tasks FROM anon;
REVOKE ALL ON public.employee_tasks FROM public;
