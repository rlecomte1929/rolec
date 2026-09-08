-- AIQ-839 (W5): source provenance defaults + auto_generated flag on policy_config_benefits.
--
-- Builds on AIQ-838, which added the nullable `source` column. This task:
--   1. Gives `source` a default of 'seeded' and backfills existing NULL rows to 'seeded'
--      (existing rows are template-seeded / pre-provenance, so 'seeded' is the honest label).
--   2. Adds `auto_generated` so downstream code can tell AI/template-produced values
--      (true) from hand-typed HR values (false) without parsing the source string.
--
-- Canonical `source` vocabulary (W5): 'extracted_llm' | 'template_default' | 'manual_hr' | 'seeded'.
-- Existing table → plain additive ALTERs, no new-table RLS gate.

ALTER TABLE public.policy_config_benefits
    ALTER COLUMN source SET DEFAULT 'seeded';

UPDATE public.policy_config_benefits
    SET source = 'seeded'
    WHERE source IS NULL;

ALTER TABLE public.policy_config_benefits
    ADD COLUMN IF NOT EXISTS auto_generated boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN public.policy_config_benefits.source IS
    'Provenance: extracted_llm | template_default | manual_hr | seeded (default). See AIQ-838/AIQ-839.';
COMMENT ON COLUMN public.policy_config_benefits.auto_generated IS
    'false = value entered by an HR user (source=manual_hr); true = AI/template/seeded origin. AIQ-839.';
