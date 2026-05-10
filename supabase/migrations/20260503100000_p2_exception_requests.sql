-- ─────────────────────────────────────────────────────────────────────────────
-- P2 migration: exception_requests table
--
-- An ExceptionRequest is created whenever a relocation case falls outside
-- standard policy parameters and requires explicit HR / mobility-lead sign-off
-- before the case can proceed.
--
-- Common triggers:
--   • US L1B: employee < 1 year tenure with company
--   • US L1B: no confirmed US legal entity as petitioner
--   • Any route: timeline too short for standard processing
--   • Any route: estimated cost above company policy threshold
--   • Japan COE: role category ambiguous for visa sub-status
--
-- Touch policy: NEW TABLE. No existing table is altered.
-- Apply manually via Supabase SQL Editor or Supabase CLI.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.exception_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             TEXT        NOT NULL,
    assignment_id       TEXT        NULL,       -- optional — filled when linked to an assignment

    -- Classification
    exception_type      TEXT        NOT NULL    -- see CHECK below
        CHECK (exception_type IN (
            'tenure_insufficient',              -- employee < 1 yr at company (L1B etc.)
            'no_sponsoring_entity',             -- no legal entity to petition / sponsor
            'timeline_breach',                  -- move date < minimum processing window
            'cost_threshold',                   -- estimated cost > policy cap
            'role_category_ambiguous',          -- visa sub-category unclear (Japan COE etc.)
            'dual_intent_conflict',             -- visa type prohibits dual intent
            'policy_custom'                     -- catch-all for HR-defined exceptions
        )),

    reason              TEXT        NOT NULL,   -- human-readable explanation
    severity            TEXT        NOT NULL DEFAULT 'warning'
        CHECK (severity IN ('warning', 'blocker')),

    -- Lifecycle
    status              TEXT        NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'denied', 'escalated', 'withdrawn')),

    -- Resolution
    resolved_at         TIMESTAMPTZ NULL,
    resolved_by         TEXT        NULL,       -- user ID or name of HR approver
    resolution_notes    TEXT        NULL,

    -- Audit
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_exception_requests_case_id
    ON public.exception_requests (case_id);

CREATE INDEX IF NOT EXISTS idx_exception_requests_assignment_id
    ON public.exception_requests (assignment_id)
    WHERE assignment_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_exception_requests_status
    ON public.exception_requests (status)
    WHERE status IN ('pending', 'escalated');

CREATE INDEX IF NOT EXISTS idx_exception_requests_created_at
    ON public.exception_requests (created_at DESC);

-- ── updated_at trigger ────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.set_exception_requests_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_exception_requests_updated_at ON public.exception_requests;
CREATE TRIGGER trg_exception_requests_updated_at
    BEFORE UPDATE ON public.exception_requests
    FOR EACH ROW EXECUTE FUNCTION public.set_exception_requests_updated_at();

-- ── Row-Level Security ────────────────────────────────────────────────────────
-- HR and admin roles can read all exception requests for their cases.
-- Employees cannot see exception requests (they see the outcome via case status).

ALTER TABLE public.exception_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS exception_requests_service_role ON public.exception_requests;
CREATE POLICY exception_requests_service_role
    ON public.exception_requests
    USING (TRUE)
    WITH CHECK (TRUE);
-- Note: tighter employee / HR RLS policies to be added in a subsequent migration
-- once the auth claims shape is finalised.
