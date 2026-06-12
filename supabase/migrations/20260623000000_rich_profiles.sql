-- rich_profiles — verbatim store for the platform-v2 employee "Rich Profile &
-- Preferences" page (EmployeeRichProfilePage). Distinct from relocation_profiles
-- (which holds the strongly-typed RelocationProfilePayload) and from the PII
-- immigration profile. The page persists its own ProfileData shape opaquely as
-- JSONB, keyed by case_id. Mirrors the relocation_profiles table 1:1, including
-- its RLS posture (employee owns its row; service_role full access; anon denied).

CREATE TABLE IF NOT EXISTS public.rich_profiles (
  case_id    text PRIMARY KEY,
  user_id    text,
  data       jsonb       NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 1) Enable RLS (hard gate)
ALTER TABLE public.rich_profiles ENABLE ROW LEVEL SECURITY;

-- 2) Policies — mirror relocation_profiles (idempotent: drop-then-create)
DROP POLICY IF EXISTS "Employee reads own rich profile"   ON public.rich_profiles;
CREATE POLICY "Employee reads own rich profile" ON public.rich_profiles
  FOR SELECT USING ((auth.uid())::text = user_id);

DROP POLICY IF EXISTS "Employee writes own rich profile"  ON public.rich_profiles;
CREATE POLICY "Employee writes own rich profile" ON public.rich_profiles
  FOR INSERT WITH CHECK ((auth.uid())::text = user_id);

DROP POLICY IF EXISTS "Employee updates own rich profile" ON public.rich_profiles;
CREATE POLICY "Employee updates own rich profile" ON public.rich_profiles
  FOR UPDATE USING ((auth.uid())::text = user_id);

DROP POLICY IF EXISTS "Service role full access rich_profiles" ON public.rich_profiles;
CREATE POLICY "Service role full access rich_profiles" ON public.rich_profiles
  FOR ALL USING (auth.role() = 'service_role'::text);

-- 3) Revoke anon access (defense-in-depth — the anon key ships in the bundle)
REVOKE ALL ON public.rich_profiles FROM anon;
