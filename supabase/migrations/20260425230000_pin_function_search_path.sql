-- Pin `search_path = ''` on the 10 SQL/PLPGSQL functions in `public` that
-- the Supabase Security Advisor flagged with "Function Search Path
-- Mutable". An unset/mutable search_path lets a hostile role create
-- objects in `pg_temp` or another reachable schema and shadow references
-- inside the function body — particularly dangerous for the SECURITY
-- DEFINER functions in this list.
--
-- Why `''` (empty) is safe here: every reference inside these function
-- bodies is already fully schema-qualified — `public.case_assignments`,
-- `public.rfqs`, `public.admin_allowlist`, `public.hr_profiles`,
-- `public.recalculate_case_risk`, `auth.uid()`. Built-ins like `now()`,
-- `coalesce()`, `btrim()`, `jsonb_array_elements()`, casts, and
-- `exists(…)` resolve via the implicit `pg_catalog` lookup, which
-- Postgres always performs even when `pg_catalog` is not listed in
-- search_path. So an empty search_path is the strictest setting that
-- keeps current behaviour while closing the search-path attack surface.
--
-- Idempotent: ALTER FUNCTION ... SET search_path is unconditional.

ALTER FUNCTION public.set_updated_at()
  SET search_path = '';

ALTER FUNCTION public.set_company_updated_at()
  SET search_path = '';

ALTER FUNCTION public.try_parse_timestamptz(text)
  SET search_path = '';

ALTER FUNCTION public.is_admin()
  SET search_path = '';

ALTER FUNCTION public.my_company_id()
  SET search_path = '';

ALTER FUNCTION public.trigger_recalculate_risk_on_task()
  SET search_path = '';

ALTER FUNCTION public.trigger_recalculate_risk_on_budget()
  SET search_path = '';

ALTER FUNCTION public.hr_reopen_assignment(text, text)
  SET search_path = '';

ALTER FUNCTION public.employee_unsubmit_assignment(text)
  SET search_path = '';

ALTER FUNCTION public.create_rfq_with_items(text, uuid, text, jsonb, uuid[])
  SET search_path = '';
