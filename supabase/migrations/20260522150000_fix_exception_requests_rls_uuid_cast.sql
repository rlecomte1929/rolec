-- Fix exception_requests RLS policies that fail on a clean-slate Preview
-- database because profiles.id and profiles.company_id start as TEXT in the
-- original remote_schema migration and the IN-subquery hits a text = uuid
-- operator mismatch.
--
-- Solution: drop and recreate the four tenant-scoped policies with an explicit
-- ::uuid cast on profiles.id so they work regardless of column type at the
-- point in migration history when this file runs.

DROP POLICY IF EXISTS exception_requests_select_tenant    ON public.exception_requests;
DROP POLICY IF EXISTS exception_requests_insert_employee  ON public.exception_requests;
DROP POLICY IF EXISTS exception_requests_update_hr        ON public.exception_requests;
DROP POLICY IF EXISTS exception_requests_update_admin     ON public.exception_requests;

CREATE POLICY exception_requests_select_tenant
  ON public.exception_requests
  FOR SELECT TO authenticated
  USING (
    organization_id IN (
      SELECT company_id::uuid
      FROM public.profiles
      WHERE id::uuid = auth.uid()
    )
  );

CREATE POLICY exception_requests_insert_employee
  ON public.exception_requests
  FOR INSERT TO authenticated
  WITH CHECK (
    requested_by_user_id = auth.uid()
  );

CREATE POLICY exception_requests_update_hr
  ON public.exception_requests
  FOR UPDATE TO authenticated
  USING (
    organization_id IN (
      SELECT company_id::uuid
      FROM public.profiles
      WHERE id::uuid = auth.uid()
    )
  );

CREATE POLICY exception_requests_update_admin
  ON public.exception_requests
  FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id::uuid = auth.uid()
        AND role = 'admin'
    )
  );
