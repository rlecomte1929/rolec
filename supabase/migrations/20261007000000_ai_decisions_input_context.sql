-- AIQ-1694·2 — capture the PII-masked INPUT that produced each AI recommendation.
--
-- ai_decisions (migration 20260527000000_ai_decisions_human_oversight.sql) already
-- records `ai_output` (the recommendation as shown to the overseer) plus the human
-- `decision`/`reason`/`outcome`. It has NO column for the input context that produced
-- the recommendation, and rows are written ONLY on a human action (POST /api/ai/decisions).
-- AIQ-1694 adds production-time logging; this migration adds the three columns that
-- logging needs. See docs/ai/ai_decisions_coverage_audit.md (Subtask 1) for the analysis.
--
-- ADDITIVE + NULLABLE, so no backfill: a NULL `input_context` means "not captured",
-- which is exactly today's behaviour for every existing row.
--
-- RLS: ai_decisions already has RLS enabled with company-scoped policies that gate by
-- ROW (service_role_all / hr_read_own_company / user_read_own — none reference a column
-- list). A new column inherits those policies, so the new-table RLS gate does NOT apply
-- and NO policy/REVOKE changes are made here.
--
-- NOTE for Subtask 3 (write path): (feature, recommendation_id) is NOT unique in prod
-- (16 rows, 8 duplicate pairs), so a DB-level upsert / ON CONFLICT on that pair is not
-- possible. Deliberately NO unique index is added here — the produced-row vs
-- human-decision convergence must be handled in application logic, not a DB constraint.
--
-- decision state: `decision` is NOT NULL and CHECK-constrained. A production-time record
-- is written BEFORE any human acts, so it needs a non-human state. This migration widens
-- the CHECK to add 'produced' (the sentinel Subtask 3 writes at production time; the
-- POST /api/ai/decisions endpoint later updates it to accept/override/reject). Widening
-- an IN-list CHECK is safe — every existing row already satisfies the narrower list.

ALTER TABLE public.ai_decisions
  ADD COLUMN IF NOT EXISTS input_context JSONB,        -- PII-masked input that produced the recommendation
  ADD COLUMN IF NOT EXISTS model_name    TEXT,         -- producing model/provider, or 'rule-based'
  ADD COLUMN IF NOT EXISTS produced_at   TIMESTAMPTZ;  -- when the recommendation was produced (vs a human action)

-- Widen the decision CHECK to allow the production-time 'produced' state.
-- CHECK has no IF NOT EXISTS — DROP+CREATE for idempotent replay (mirrors the RLS
-- policy pattern in 20260527000000). The name matches the auto-generated constraint.
ALTER TABLE public.ai_decisions DROP CONSTRAINT IF EXISTS ai_decisions_decision_check;
ALTER TABLE public.ai_decisions
  ADD CONSTRAINT ai_decisions_decision_check
  CHECK (decision = ANY (ARRAY['accept','override','reject','produced']));

COMMENT ON COLUMN public.ai_decisions.input_context IS
  'PII-masked input context that produced the AI recommendation (AIQ-1694). NULL = not captured. Masked via pii_masker before write.';
COMMENT ON COLUMN public.ai_decisions.model_name IS
  'Model/provider that produced the recommendation (e.g. claude-haiku-4-5) or ''rule-based'' (AIQ-1694).';
COMMENT ON COLUMN public.ai_decisions.produced_at IS
  'When the recommendation was produced, distinct from created_at of a human action (AIQ-1694).';
