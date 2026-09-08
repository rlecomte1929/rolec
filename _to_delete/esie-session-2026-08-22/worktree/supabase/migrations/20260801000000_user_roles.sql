-- AIQ-1352 — multi-role foundation (subtask 1 of 6).
--
-- One identity, many roles: a person who is both HR and a relocating employee
-- should hold both roles on one account. This creates the N:N junction and
-- backfills one row per existing user from users.role (is_primary=true). The
-- legacy users.role column is intentionally KEPT — the single-role read path
-- still depends on it this stage (the roles[] read layer is AIQ-1353).
--
-- Idempotent + non-destructive: re-running is a no-op; users.role is untouched.
-- Applied out-of-band via MCP execute_sql and reconciled in the ledger at this
-- version (supabase db push is blocked by orphan ledger rows in this project).

CREATE TABLE IF NOT EXISTS public.user_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('EMPLOYEE', 'HR', 'ADMIN')),
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, role)
);

-- CLAUDE.md hard gates for any new public table -------------------------------
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- A user may read their own role rows; admins read all. The backend reads this
-- table via the privileged engine, so this policy is defense-in-depth for any
-- direct PostgREST/anon access.
DROP POLICY IF EXISTS "user_roles_self_or_admin_read" ON public.user_roles;
CREATE POLICY "user_roles_self_or_admin_read" ON public.user_roles
  FOR SELECT USING (public.is_admin() OR user_id = (auth.uid())::text);

REVOKE ALL ON public.user_roles FROM anon;

-- Backfill: one row per existing user from the legacy single role, primary=true.
INSERT INTO public.user_roles (user_id, role, is_primary)
SELECT id, role, true
FROM public.users
WHERE role IS NOT NULL AND btrim(role) <> ''
ON CONFLICT (user_id, role) DO NOTHING;
