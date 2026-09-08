-- AIQ-1414 Phase 2b — persistent Mobility Coordinator session state.
--
-- One durable "memory" row per relocation for the AI coordinator (Option B:
-- "the memory is Postgres"). Instead of an accruing Anthropic server session,
-- the coordinator re-reads authoritative case state each turn (see
-- coordinator_context_builder) and keeps only a bounded rolling summary + the
-- last few verbatim turns + an event cursor here. Additive + idempotent; the
-- feature is flag-gated (RELOPASS_AI_COORDINATOR_ENABLED, default OFF), so this
-- table is inert until enabled behind the human gate.
--
-- Mirrors the interview_sessions pattern (20260518120000): one state row per
-- case, TEXT ids (auth.uid()::text), RLS + service-role bypass.

CREATE TABLE IF NOT EXISTS public.ai_coordinator_sessions (
  id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  case_id            TEXT NOT NULL,          -- HR-surface case id (the coordinator anchor)
  employee_id        TEXT,                    -- assignee (nullable pre-assignment)
  company_id         TEXT NOT NULL,

  rolling_summary    TEXT NOT NULL DEFAULT '',          -- bounded LLM-maintained narrative
  recent_turns       JSONB NOT NULL DEFAULT '[]'::jsonb, -- last N verbatim {user, assistant}
  last_event_cursor  TIMESTAMPTZ,                        -- newest case_events folded into summary
  model              TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',

  status             TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'closed')),

  started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_active_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One coordinator session per relocation.
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_coordinator_sessions_case
  ON public.ai_coordinator_sessions(case_id);

CREATE INDEX IF NOT EXISTS idx_ai_coordinator_sessions_company
  ON public.ai_coordinator_sessions(company_id);

-- ── RLS (hard gate: ENABLE + policy + REVOKE anon) ──────────────────────────
ALTER TABLE public.ai_coordinator_sessions ENABLE ROW LEVEL SECURITY;

-- Defense-in-depth: the anon key is shipped in the frontend bundle; this table
-- is never exposed to it.
REVOKE ALL ON public.ai_coordinator_sessions FROM anon;

-- Employee owns their own coordinator session.
DROP POLICY IF EXISTS ai_coordinator_sessions_employee ON public.ai_coordinator_sessions;
CREATE POLICY ai_coordinator_sessions_employee
  ON public.ai_coordinator_sessions FOR ALL TO authenticated
  USING (employee_id = auth.uid()::text)
  WITH CHECK (employee_id = auth.uid()::text);

-- HR for the owning company (via the case→assignment link) may read.
DROP POLICY IF EXISTS ai_coordinator_sessions_hr_select ON public.ai_coordinator_sessions;
CREATE POLICY ai_coordinator_sessions_hr_select
  ON public.ai_coordinator_sessions FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.case_id = ai_coordinator_sessions.case_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- Backend (service role) manages the row; RLS bypassed, scoping enforced in-app.
DROP POLICY IF EXISTS ai_coordinator_sessions_service_role ON public.ai_coordinator_sessions;
CREATE POLICY ai_coordinator_sessions_service_role
  ON public.ai_coordinator_sessions FOR ALL TO service_role
  USING (true) WITH CHECK (true);
