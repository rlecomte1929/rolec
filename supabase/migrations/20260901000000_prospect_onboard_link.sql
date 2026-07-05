-- Track B (commercial conversion): link a prospect_candidate to the company it was
-- onboarded into, so the funnel has a real prospect → live-customer path.
-- Additive columns only on an existing table (prospect_candidates already has RLS via
-- the service-role defense-in-depth policies), so no new RLS/policy/revoke gates apply.
ALTER TABLE public.prospect_candidates
  ADD COLUMN IF NOT EXISTS onboarded_company_id text,
  ADD COLUMN IF NOT EXISTS onboarded_at timestamptz;
