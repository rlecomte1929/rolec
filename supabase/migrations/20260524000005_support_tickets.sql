-- SUPPORT-4A: support_tickets table
-- ─────────────────────────────────────────────────────────────────────────────
-- Stores every inbound support interaction: email (via Postmark inbound webhook)
-- and in-app (via Help button form). Both sources insert here and fire a
-- support_ticket.created event via the events table.
--
-- Triage results (from SUPPORT-4B) are stored in the triage_result JSONB column.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.support_tickets (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Source and content
  source                TEXT        NOT NULL CHECK (source IN ('email', 'in-app')),
  subject               TEXT,
  raw_content           TEXT        NOT NULL,    -- first message only (quoted replies stripped)
  html_content          TEXT,                     -- HTML body if available (email only)

  -- Sender identity
  from_email            TEXT,
  from_name             TEXT,
  user_id               TEXT,                     -- Supabase auth user ID if logged in
  company_id            TEXT,                     -- Must be non-null for logged-in users

  -- Status lifecycle
  status                TEXT        NOT NULL DEFAULT 'new'
                          CHECK (status IN ('new', 'triaged', 'resolved', 'escalated', 'crisis_escalated')),

  -- Triage result populated by SUPPORT-4B
  triage_result         JSONB,

  -- Deduplication
  postmark_message_id   TEXT        UNIQUE,       -- Prevents duplicate email inserts

  -- Routing metadata
  assigned_to           TEXT,                     -- User ID of assigned support agent
  resolved_at           TIMESTAMPTZ,
  resolution_notes      TEXT
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_support_tickets_status        ON public.support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_company_id    ON public.support_tickets(company_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at    ON public.support_tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_source        ON public.support_tickets(source);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id       ON public.support_tickets(user_id);

-- ── updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_support_ticket_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_support_tickets_updated_at ON public.support_tickets;
CREATE TRIGGER trg_support_tickets_updated_at
  BEFORE UPDATE ON public.support_tickets
  FOR EACH ROW EXECUTE FUNCTION public.set_support_ticket_updated_at();

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for backend and Edge Functions)
CREATE POLICY IF NOT EXISTS "service_role_all_support_tickets"
  ON public.support_tickets FOR ALL
  USING (auth.role() = 'service_role');

-- HR users can view tickets for their company
CREATE POLICY IF NOT EXISTS "hr_read_own_company_tickets"
  ON public.support_tickets FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND company_id = (
      SELECT raw_user_meta_data->>'company_id'
      FROM auth.users WHERE id = auth.uid()
    )
  );

-- Users can view their own tickets
CREATE POLICY IF NOT EXISTS "user_read_own_tickets"
  ON public.support_tickets FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND user_id = auth.uid()::text
  );

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE  public.support_tickets                IS 'SUPPORT-4A: Inbound support interactions from email (Postmark) and in-app Help button';
COMMENT ON COLUMN public.support_tickets.source         IS 'email = Postmark inbound; in-app = in-product Help form';
COMMENT ON COLUMN public.support_tickets.raw_content    IS 'First message only — quoted reply threads are stripped before storage';
COMMENT ON COLUMN public.support_tickets.triage_result  IS 'SUPPORT-4B JSON: {issue_category, root_cause_hypothesis, fix_difficulty, suggested_action, draft_reply}';
COMMENT ON COLUMN public.support_tickets.status         IS 'Lifecycle: new → triaged → (resolved|escalated|crisis_escalated)';
