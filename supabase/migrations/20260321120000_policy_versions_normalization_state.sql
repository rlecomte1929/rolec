-- Normalization persistence marker (transactional pipeline sets final state on commit).
ALTER TABLE public.policy_versions
  ADD COLUMN IF NOT EXISTS normalization_state text;

COMMENT ON COLUMN public.policy_versions.normalization_state IS
  'normalization_in_progress | normalization_failed | normalized_draft | normalized_complete';
