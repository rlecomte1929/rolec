-- IMM-17 (AIQ-123) — GDPR Art.17 erasure-request workflow table
--
-- An erasure request is a *record of intent*, not an automatic delete. The employee
-- files it; HR/admin reviews and actions it (the actual deletion + retention
-- automation land in IMM-18). Status moves pending -> approved/rejected -> completed,
-- so this table is mutable (unlike consent_records / data_access_log) and carries an
-- updated_at trigger.

CREATE TABLE IF NOT EXISTS public.erasure_requests (
  id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  case_id          TEXT NOT NULL,
  employee_id      TEXT NOT NULL,
  org_id           TEXT,
  status           TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | completed
  reason           TEXT,                              -- employee's stated reason (optional)
  requested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  statutory_due_at TIMESTAMPTZ NOT NULL,             -- requested_at + 30 days (Art.12(3))
  reviewed_by      TEXT,                             -- HR/admin user id who actioned it
  reviewed_at      TIMESTAMPTZ,
  review_notes     TEXT,
  completed_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_erasure_requests_case_employee
  ON public.erasure_requests(case_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_erasure_requests_status
  ON public.erasure_requests(status);

ALTER TABLE public.erasure_requests ENABLE ROW LEVEL SECURITY;

-- Employees read their own requests
DROP POLICY IF EXISTS erasure_requests_employee_select ON public.erasure_requests;
CREATE POLICY erasure_requests_employee_select
  ON public.erasure_requests FOR SELECT TO authenticated
  USING (employee_id = auth.uid()::text);

-- Employees file their own requests
DROP POLICY IF EXISTS erasure_requests_employee_insert ON public.erasure_requests;
CREATE POLICY erasure_requests_employee_insert
  ON public.erasure_requests FOR INSERT TO authenticated
  WITH CHECK (employee_id = auth.uid()::text);

-- HR reads requests for cases they own
DROP POLICY IF EXISTS erasure_requests_hr_select ON public.erasure_requests;
CREATE POLICY erasure_requests_hr_select
  ON public.erasure_requests FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = erasure_requests.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- HR actions (approve/reject/complete) requests for cases they own
DROP POLICY IF EXISTS erasure_requests_hr_update ON public.erasure_requests;
CREATE POLICY erasure_requests_hr_update
  ON public.erasure_requests FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = erasure_requests.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- Backend (service role) can do everything
DROP POLICY IF EXISTS erasure_requests_service_role ON public.erasure_requests;
CREATE POLICY erasure_requests_service_role
  ON public.erasure_requests FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- Defense-in-depth: the anon key ships in the frontend bundle
REVOKE ALL ON public.erasure_requests FROM anon;

-- Keep updated_at fresh
CREATE OR REPLACE FUNCTION public.fn_erasure_requests_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_erasure_requests_updated_at ON public.erasure_requests;
CREATE TRIGGER trg_erasure_requests_updated_at
  BEFORE UPDATE ON public.erasure_requests
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_erasure_requests_updated_at();
