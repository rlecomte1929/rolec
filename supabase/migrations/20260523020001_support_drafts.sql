-- HUMAN-7C: support_drafts table
-- ─────────────────────────────────────────────────────────────────────────────
-- Stores AI-generated draft replies for support tickets that are routed to the
-- 'ai_reply' path. Drafts sit in 'pending_review' until a human approves or
-- rejects them — nothing auto-sends from this table.
--
-- Lifecycle: pending_review → approved → sent
--            pending_review → rejected  (draft discarded, ticket re-escalated)
--
-- Populated by: lib/support-ai-reply.ts → saveDraft()
-- Consumed by:  SUPPORT-4D auto-reply pipeline (reads approved rows)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.support_drafts (
  id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Ticket reference
  ticket_id             UUID        NOT NULL
                          REFERENCES public.support_tickets(id)
                          ON DELETE CASCADE,

  -- Draft content
  subject               TEXT        NOT NULL,
  body                  TEXT        NOT NULL,

  -- Human review gate
  requires_human_review BOOLEAN     NOT NULL DEFAULT true,

  -- Lifecycle status
  status                TEXT        NOT NULL DEFAULT 'pending_review'
                          CHECK (status IN ('pending_review', 'approved', 'rejected', 'sent')),

  -- Audit trail
  reviewed_by           TEXT,          -- user_id of the HR agent who approved/rejected
  reviewed_at           TIMESTAMPTZ,
  review_notes          TEXT           -- optional note from reviewer
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_support_drafts_ticket_id  ON public.support_drafts(ticket_id);
CREATE INDEX IF NOT EXISTS idx_support_drafts_status     ON public.support_drafts(status);
CREATE INDEX IF NOT EXISTS idx_support_drafts_created_at ON public.support_drafts(created_at DESC);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.support_drafts ENABLE ROW LEVEL SECURITY;

-- Service role has full access (backend + Edge Functions)
CREATE POLICY IF NOT EXISTS "service_role_all_support_drafts"
  ON public.support_drafts FOR ALL
  USING (auth.role() = 'service_role');

-- HR users can view and approve/reject drafts for their company's tickets
CREATE POLICY IF NOT EXISTS "hr_manage_support_drafts"
  ON public.support_drafts FOR ALL
  USING (
    auth.role() = 'authenticated'
    AND ticket_id IN (
      SELECT id FROM public.support_tickets
      WHERE company_id = (
        SELECT raw_user_meta_data->>'company_id'
        FROM auth.users WHERE id = auth.uid()
      )
    )
  );

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE  public.support_drafts                       IS 'HUMAN-7C: AI-generated reply drafts for support tickets — pending human approval before send';
COMMENT ON COLUMN public.support_drafts.requires_human_review IS 'true = must be approved by a human before sending; set automatically for high-difficulty or billing tickets';
COMMENT ON COLUMN public.support_drafts.status                IS 'pending_review → approved → sent | pending_review → rejected';
COMMENT ON COLUMN public.support_drafts.body                  IS 'Draft reply body only — greeting and sign-off are added by the send pipeline (SUPPORT-4D)';
