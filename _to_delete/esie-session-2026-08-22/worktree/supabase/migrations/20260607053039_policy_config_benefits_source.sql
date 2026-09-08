-- AIQ-838: Wire default_policy_templates.snapshot_json as a gap-fill source.
--
-- Adds a `source` provenance marker to policy_config_benefits so a benefit row
-- can record where its value came from:
--   'extracted'        — taken from the uploaded policy document (LLM extraction)
--   'template_default' — gap-filled from default_policy_templates.snapshot_json
--                        because the document was silent on this field
--   'manual'           — entered/overridden by an HR user
--
-- Existing table, so this is a plain additive ALTER (no new table → no RLS gate).
-- Nullable with no default: existing rows keep NULL (unknown provenance) rather
-- than being silently relabelled 'extracted'.

ALTER TABLE public.policy_config_benefits
    ADD COLUMN IF NOT EXISTS source text;

COMMENT ON COLUMN public.policy_config_benefits.source IS
    'Provenance of this benefit value: extracted | template_default | manual (NULL = legacy/unknown). See AIQ-838.';
