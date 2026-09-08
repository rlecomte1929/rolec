-- W2-3 (HR-MVP): first-class "escalate this case to a specialist / legal" action.
-- Until now escalation only existed at the contradiction level (hr_case_resolve);
-- the operational review_queue_items table has no case/company scoping and is
-- admin-only, so it can't carry HR case escalations. This adds a dedicated,
-- tenant-scoped HR escalation entity.
--
-- Note on case_id: this is the HR-surface case id (the relocation_cases /
-- case_assignments id the cockpit uses for /api/hr/cases/{id}); it is deliberately
-- NOT FK'd to public.cases, which is a separate, bridge-backfilled canonical table
-- (the documented case-table schism). Tenant isolation is by company_id.
-- Idempotent DDL.

CREATE TABLE IF NOT EXISTS public.case_escalations (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id          text NOT NULL,
  company_id       text NOT NULL,
  kind             text NOT NULL DEFAULT 'specialist'
                     CHECK (kind IN ('specialist', 'legal', 'other')),
  reason           text NOT NULL,
  status           text NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'in_review', 'resolved', 'cancelled')),
  assignee         text,
  sla_due_at       timestamptz,
  created_by       text,
  resolution_note  text,
  resolved_at      timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_escalations_case ON public.case_escalations(case_id);
CREATE INDEX IF NOT EXISTS idx_case_escalations_company ON public.case_escalations(company_id);

-- RLS: tenant isolation by company. HR/admin of the owning company (and admins
-- globally). Reuses the canonical my_company_id() / my_role() helpers.
ALTER TABLE public.case_escalations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_escalations_company ON public.case_escalations;
CREATE POLICY case_escalations_company ON public.case_escalations FOR ALL
  USING (
    public.my_role() = 'admin'
    OR (company_id = public.my_company_id()::text AND public.my_role() IN ('hr', 'admin'))
  );

-- Defense-in-depth: never expose via the anon (PostgREST) role.
REVOKE ALL ON public.case_escalations FROM anon;
