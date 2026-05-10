-- Normalization persistence marker (transactional pipeline sets final state on commit).
-- Runs after 20260331000000_policy_normalization.sql creates public.policy_versions.
ALTER TABLE public.policy_versions
  ADD COLUMN IF NOT EXISTS normalization_state text;

COMMENT ON COLUMN public.policy_versions.normalization_state IS
  'normalization_in_progress | normalization_failed | normalized_draft | normalized_complete';
