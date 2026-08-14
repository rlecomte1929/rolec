-- LEDGER RECONCILIATION (CLAUDE.md § Ledger reconciliation).
-- This migration was applied to prod OUT-OF-BAND (schema_migrations version
-- 20260727055939, name 20261007000000_ai_decisions_input_context — AIQ-1694·2) but
-- never had a matching repo file, so the read-only migration-drift check failed on
-- EVERY migration PR ("prod version with no repo file"). This file reproduces the
-- applied DDL verbatim from schema_migrations.statements to reconcile the ledger.
-- Idempotent (ADD COLUMN IF NOT EXISTS / DROP CONSTRAINT IF EXISTS) — safe to replay.

-- AIQ-1694·2 — masked input_context columns + 'produced' decision state on ai_decisions.
ALTER TABLE public.ai_decisions
  ADD COLUMN IF NOT EXISTS input_context JSONB,
  ADD COLUMN IF NOT EXISTS model_name    TEXT,
  ADD COLUMN IF NOT EXISTS produced_at   TIMESTAMPTZ;

COMMENT ON COLUMN public.ai_decisions.input_context IS
  'PII-masked input context that produced the AI recommendation (AIQ-1694). NULL = not captured. Masked via pii_masker before write.';
COMMENT ON COLUMN public.ai_decisions.model_name IS
  'Model/provider that produced the recommendation (e.g. claude-haiku-4-5) or ''rule-based'' (AIQ-1694).';
COMMENT ON COLUMN public.ai_decisions.produced_at IS
  'When the recommendation was produced, distinct from created_at of a human action (AIQ-1694).';

ALTER TABLE public.ai_decisions DROP CONSTRAINT IF EXISTS ai_decisions_decision_check;
ALTER TABLE public.ai_decisions
  ADD CONSTRAINT ai_decisions_decision_check
  CHECK (decision = ANY (ARRAY['accept','override','reject','produced']));
