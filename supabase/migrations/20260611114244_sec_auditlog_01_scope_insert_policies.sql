-- Ledger reconciliation (prod-as-oracle): applied to prod 2026-06-11 via MCP
-- apply_migration, never committed. Exact recovered SQL below. Idempotent
-- (DROP POLICY IF EXISTS + CREATE POLICY).

-- SEC-AUDITLOG-01: Replace unrestricted INSERT WITH CHECK policies
-- Deployed: 2026-06-11
-- Before: with_check=true on data_access_log, events, assignment_outcomes
-- After:  each table scoped to the authenticated user's own context

-- ─────────────────────────────────────────────────────────────────────
-- data_access_log: caller must be a participant in the referenced case
-- ─────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS data_access_log_insert ON public.data_access_log;

CREATE POLICY data_access_log_insert ON public.data_access_log
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = data_access_log.case_id
        AND (
          ca.employee_user_id = (auth.uid())::text
          OR ca.hr_user_id    = (auth.uid())::text
        )
    )
  );

-- ─────────────────────────────────────────────────────────────────────
-- events: user_id must match caller, company_id must match caller's company
-- ─────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS events_insert_authenticated ON public.events;

CREATE POLICY events_insert_authenticated ON public.events
  FOR INSERT TO authenticated
  WITH CHECK (
    events.user_id    = (auth.uid())::text
    AND events.company_id = (public.my_company_id())::text
  );

-- ─────────────────────────────────────────────────────────────────────
-- assignment_outcomes: assignment_id must belong to a case the caller has access to
-- ─────────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS outcomes_insert_authenticated ON public.assignment_outcomes;

CREATE POLICY outcomes_insert_authenticated ON public.assignment_outcomes
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.id = assignment_outcomes.assignment_id
        AND (
          ca.employee_user_id = (auth.uid())::text
          OR ca.hr_user_id    = (auth.uid())::text
        )
    )
  );
