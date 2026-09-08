-- ============================================================
-- [P1-4] Add publish-related columns to policy_versions
-- Date: 2026-05-22
--
-- The P1-1 schema for `policy_versions` (applied directly to Supabase,
-- see /Users/romainlecomte/Documents/policy_schema_migration.sql) covers
-- everything except the HR-controlled publish metadata:
--   - effective_date   — when this version starts being authoritative
--   - expiry_date      — optional sunset; drives the policy-summary
--                        "under review" amber banner
--   - published_by     — HR user who clicked Publish
--   - published_at     — server timestamp of the publish action
--
-- Idempotent — ADD COLUMN IF NOT EXISTS so reruns are safe.
-- ============================================================

BEGIN;

ALTER TABLE public.policy_versions
  ADD COLUMN IF NOT EXISTS effective_date date,
  ADD COLUMN IF NOT EXISTS expiry_date    date,
  ADD COLUMN IF NOT EXISTS published_by   uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS published_at   timestamptz;

COMMENT ON COLUMN public.policy_versions.effective_date IS
  '[P1-4] HR-chosen date when this published version starts being authoritative.';
COMMENT ON COLUMN public.policy_versions.expiry_date IS
  '[P1-4] Optional sunset date. After this date the policy is considered "under review" and the policy-summary surface flips an amber banner.';
COMMENT ON COLUMN public.policy_versions.published_by IS
  '[P1-4] HR user (profiles.id) who clicked Publish.';
COMMENT ON COLUMN public.policy_versions.published_at IS
  '[P1-4] Server timestamp at the moment of publish.';

-- Speeds up "find the currently published version per policy" — the hot
-- read path for policy summary, AI assistant retrieval, etc.
CREATE INDEX IF NOT EXISTS idx_policy_versions_policy_status
  ON public.policy_versions (policy_id, status);

COMMIT;
