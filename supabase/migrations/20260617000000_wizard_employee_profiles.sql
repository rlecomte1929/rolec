-- ---------------------------------------------------------------------------
-- AIQ-868 — Relocate wizard-profile storage off the collided employee_profiles.
--
-- Background: the immigration-core migration (20260518120000, finalised by
-- 20260604400000_employee_profiles_replay_safe.sql) redefined
-- public.employee_profiles with the immigration vault shape
-- (case_id, employee_id, passport_*). That overwrote the original wizard
-- profile store (assignment_id, profile_json), breaking the wizard read/write
-- path (get_/save_employee_profile, main.py bulk dashboard read). PR #457
-- stop-gapped the read to None; this migration gives wizard profiles their own
-- table so save + read work again. Immigration's employee_profiles is left
-- untouched.
--
-- Idempotent (CREATE TABLE IF NOT EXISTS, DROP POLICY IF EXISTS). Committed and
-- applied on merge via the main-push workflow — never via MCP apply_migration.
-- ---------------------------------------------------------------------------

BEGIN;

CREATE TABLE IF NOT EXISTS public.wizard_employee_profiles (
  assignment_id  TEXT PRIMARY KEY,
  profile_json   TEXT NOT NULL,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.wizard_employee_profiles IS
  'Wizard / employee-intake profile blob (assignment_id + profile_json), keyed '
  'by case_assignments.id. Relocated from public.employee_profiles after the '
  'immigration-core migration took that table over (AIQ-868).';

-- SEC hard gate: RLS + tenant-scoped policies + REVOKE anon.
ALTER TABLE public.wizard_employee_profiles ENABLE ROW LEVEL SECURITY;

-- Employee who owns the assignment can read + write their own profile.
DROP POLICY IF EXISTS wizard_employee_profiles_employee_all ON public.wizard_employee_profiles;
CREATE POLICY wizard_employee_profiles_employee_all
  ON public.wizard_employee_profiles FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.id = wizard_employee_profiles.assignment_id
        AND ca.employee_user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.id = wizard_employee_profiles.assignment_id
        AND ca.employee_user_id = auth.uid()::text
    )
  );

-- HR assigned to the case can read the profile.
DROP POLICY IF EXISTS wizard_employee_profiles_hr_select ON public.wizard_employee_profiles;
CREATE POLICY wizard_employee_profiles_hr_select
  ON public.wizard_employee_profiles FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.case_assignments ca
      WHERE ca.id = wizard_employee_profiles.assignment_id
        AND ca.hr_user_id = auth.uid()::text
    )
  );

-- Service role (backend pooler connection, Edge Functions) full access.
DROP POLICY IF EXISTS wizard_employee_profiles_service_role ON public.wizard_employee_profiles;
CREATE POLICY wizard_employee_profiles_service_role
  ON public.wizard_employee_profiles FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
REVOKE ALL ON public.wizard_employee_profiles FROM anon;

COMMIT;
