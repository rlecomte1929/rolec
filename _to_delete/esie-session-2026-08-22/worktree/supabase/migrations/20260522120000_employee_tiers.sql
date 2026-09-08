-- ============================================================
-- [P1-6] Employee tier assignment
-- Date: 2026-05-22
--
-- Purpose: persist which policy tier each employee is currently on.
-- Previously a case-scoped concept (cases.policy_tier_id) — but tier is the
-- key personalisation primitive for AI assistant retrieval, policy summary,
-- and benefit comparison, even when no case is open.
--
-- Model
--   employee_tiers (employee_id, company_id, policy_tier_id, tier_name,
--                   assigned_by, assigned_at, end_date)
--   - One **current** row per employee — enforced by a UNIQUE partial index
--     on (employee_id) WHERE end_date IS NULL.
--   - Updates create a new row and archive the previous one
--     (end_date = now()), preserving history for audit_log.
--
-- tier_name is denormalised next to policy_tier_id so audit log keeps the
-- name as it was at assignment time (HR can rename a policy_tier later).
--
-- RLS
--   - HR/admin in the same company can read + write.
--   - Employees can read only their own tier row.
-- ============================================================

BEGIN;

-- ---------------------------------------------------------------
-- 1. Table
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.employee_tiers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id     uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id      uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  policy_tier_id  uuid NOT NULL REFERENCES public.policy_tiers(id) ON DELETE RESTRICT,
  -- Denormalised tier_name captures the value at assignment time so the
  -- audit trail survives later renames of the underlying policy_tier.
  tier_name       text NOT NULL,
  assigned_by     uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  assigned_at     timestamptz NOT NULL DEFAULT now(),
  -- NULL = current assignment; non-NULL timestamp = archived
  end_date        timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.employee_tiers IS
  '[P1-6] Current and historical policy_tier assignments per employee. One row WHERE end_date IS NULL = active assignment.';

-- ---------------------------------------------------------------
-- 2. Indexes
-- ---------------------------------------------------------------
-- At most one active assignment per employee.
CREATE UNIQUE INDEX IF NOT EXISTS employee_tiers_current_unique
  ON public.employee_tiers (employee_id)
  WHERE end_date IS NULL;

CREATE INDEX IF NOT EXISTS idx_employee_tiers_company_id
  ON public.employee_tiers (company_id);

CREATE INDEX IF NOT EXISTS idx_employee_tiers_policy_tier_id
  ON public.employee_tiers (policy_tier_id);

-- ---------------------------------------------------------------
-- 3. RLS
-- ---------------------------------------------------------------
ALTER TABLE public.employee_tiers ENABLE ROW LEVEL SECURITY;

-- Read: HR/admin in same company OR the employee themselves
DROP POLICY IF EXISTS employee_tiers_read ON public.employee_tiers;
CREATE POLICY employee_tiers_read ON public.employee_tiers
  FOR SELECT TO authenticated
  USING (
    employee_id = (SELECT auth.uid())
    OR EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = employee_tiers.company_id
        AND p.role IN ('hr', 'admin')
    )
  );

-- Write: HR/admin only, within the same company
DROP POLICY IF EXISTS employee_tiers_write ON public.employee_tiers;
CREATE POLICY employee_tiers_write ON public.employee_tiers
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = employee_tiers.company_id
        AND p.role IN ('hr', 'admin')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = (SELECT auth.uid())
        AND p.company_id = employee_tiers.company_id
        AND p.role IN ('hr', 'admin')
    )
  );

COMMIT;
