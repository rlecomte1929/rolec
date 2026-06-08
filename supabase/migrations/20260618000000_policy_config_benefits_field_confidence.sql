-- AIQ-873 (N11-FU1): add field_confidence to policy_config_benefits.
--
-- Foundation for the extraction→config-matrix bridge. N11/AIQ-851 calibrated
-- per-field extraction confidence in the LLM outputs; the bridge (separate
-- importer, built on top of this) will write an extracted benefit's confidence
-- onto config-matrix rows with source='extracted_llm'. This migration only adds
-- the destination column.
--
-- Existing table → plain additive ALTER, no new-table RLS gate. Nullable, no
-- default: NULL is the honest value for every existing/manual/template/seeded row
-- (only the extraction importer populates it). Idempotent; applies on merge —
-- NEVER via MCP apply_migration.

ALTER TABLE public.policy_config_benefits
    ADD COLUMN IF NOT EXISTS field_confidence double precision;

COMMENT ON COLUMN public.policy_config_benefits.field_confidence IS
    'Per-field extraction confidence (0.0-1.0) propagated from policy_benefits.confidence '
    'by the extraction→config-matrix importer (source=extracted_llm). NULL for '
    'manual_hr / template_default / seeded rows. AIQ-873 / N11-FU1.';
