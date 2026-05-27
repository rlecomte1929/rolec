-- AI-002: Human oversight decision log for EU AI Act Art. 14 compliance
-- ─────────────────────────────────────────────────────────────────────────────
-- Every HR action on an AI-generated recommendation (accept / override / reject)
-- is recorded here, paired with the original AI output. Satisfies Art. 14(4)(c):
-- "the ability to monitor the operation of the high-risk AI system".
--
-- Append-only from the HR/authenticated user perspective. Service role may
-- update `outcome` later when downstream signals reveal whether the decision
-- proved correct.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.ai_decisions (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Who made the human decision
  actor_id            UUID,                              -- auth.users.id; nullable for service-role inserts
  company_id          TEXT,                              -- denormalised for HR tenant scoping

  -- Which AI surface and recommendation
  feature             TEXT        NOT NULL,              -- e.g. 'assignment_match', 'case_readiness', 'exception_insight'
  recommendation_id   TEXT        NOT NULL,              -- caller-provided id of the specific recommendation
  ai_output           JSONB       NOT NULL,              -- the full AI recommendation as shown to the HR admin

  -- Human decision
  decision            TEXT        NOT NULL
                        CHECK (decision IN ('accept', 'override', 'reject')),
  reason              TEXT,                              -- required for override/reject (enforced at app layer)

  -- Future-populated: did the decision prove correct?
  outcome             TEXT
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ai_decisions_created_at  ON public.ai_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_actor       ON public.ai_decisions(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_feature     ON public.ai_decisions(feature, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_company     ON public.ai_decisions(company_id, created_at DESC);

-- ── updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_ai_decision_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_decisions_updated_at ON public.ai_decisions;
CREATE TRIGGER trg_ai_decisions_updated_at
  BEFORE UPDATE ON public.ai_decisions
  FOR EACH ROW EXECUTE FUNCTION public.set_ai_decision_updated_at();

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.ai_decisions ENABLE ROW LEVEL SECURITY;

-- Service role full access (backend writes through here)
CREATE POLICY IF NOT EXISTS "service_role_all_ai_decisions"
  ON public.ai_decisions FOR ALL
  USING (auth.role() = 'service_role');

-- HR / admin can read decisions for their own company
CREATE POLICY IF NOT EXISTS "hr_read_own_company_ai_decisions"
  ON public.ai_decisions FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND company_id = (
      SELECT raw_user_meta_data->>'company_id'
      FROM auth.users WHERE id = auth.uid()
    )
  );

-- Authenticated users can read their own decisions (covers admin and HR self-audit)
CREATE POLICY IF NOT EXISTS "user_read_own_ai_decisions"
  ON public.ai_decisions FOR SELECT
  USING (
    auth.role() = 'authenticated'
    AND actor_id = auth.uid()
  );

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE  public.ai_decisions                  IS 'AI-002: Human oversight decision log (EU AI Act Art. 14)';
COMMENT ON COLUMN public.ai_decisions.feature          IS 'AI surface key, e.g. assignment_match, case_readiness, exception_insight';
COMMENT ON COLUMN public.ai_decisions.recommendation_id IS 'Caller-provided id of the specific AI recommendation that was acted on';
COMMENT ON COLUMN public.ai_decisions.ai_output        IS 'Full AI recommendation payload as shown to the HR admin (for audit replay)';
COMMENT ON COLUMN public.ai_decisions.decision         IS 'HR action: accept | override | reject';
COMMENT ON COLUMN public.ai_decisions.reason           IS 'Free-text reason. Required at the app layer for override and reject.';
COMMENT ON COLUMN public.ai_decisions.outcome          IS 'Optional later assessment: did the decision prove correct? Populated by downstream signals.';
