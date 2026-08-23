-- Who FUNDS a relocation case — and an append-only record of every entitlement grant.
--
-- WHY THIS EXISTS
-- The paywall must eventually differ by segment: an SME employee sees no wall (their
-- employer pays per move), an individual self-funder sees a reveal-then-pay wall, and a
-- sponsored mover — a refugee programme, an NGO or university scheme — sees no wall ever.
-- `roadmap_entitlement.py` already resolves entitlement server-side from
-- `relocation_cases.access_tier`, but nothing anywhere records WHO IS PAYING, so no policy
-- can tell those three cases apart.
--
-- WHAT THIS DELIBERATELY DOES NOT MODEL
-- Not the person. There is no `is_refugee`, no status category, no vulnerability flag, and
-- none may be added later. Such a column is a protected-characteristic inference — it can
-- reveal national origin or asylum status, which puts it in GDPR Art. 9 territory — and once
-- it becomes an access-control input it is logged on every decision, exported under every
-- DSAR, and copied into analytics forever.
--
-- The product does not need it. It needs to know that a case is funded by a programme that
-- charges nothing. `funding_source = 'sponsor'` carries exactly that and nothing more, and
-- the same four values serve refugee programmes, NGO partnerships, university schemes,
-- pro-bono work and internal test cases. It also makes the user-facing sentence honest:
-- "Your move is covered by <programme>", never a label about the person reading it.
--
-- WHY THE DEFAULT IS 'employer'
-- Measured on production 2026-08-23: 2,165 relocation_cases, of which **2,153 carry a
-- company_id** and 12 do not. Every live case is employer-originated. Defaulting to 'self'
-- would silently reclassify all of them as individually funded, and the first policy
-- rollout would then paywall the entire book. The 12 company-less rows also default to
-- 'employer'; they are orphans rather than self-serve signups, and 'employer' is the
-- non-paywalling answer for them, which is the safe direction to be wrong in.
--
-- BEHAVIOUR CHANGE: NONE. Nothing reads these columns. The policy that will read them
-- (`resolve_paywall_policy`) is a separate, later change, and it ships wired to "no gate"
-- so that enabling a gate is always its own reviewed step.

-- ── 1. funding_source + sponsor_id on the canonical case ────────────────────────────────

ALTER TABLE public.relocation_cases
    ADD COLUMN IF NOT EXISTS funding_source text NOT NULL DEFAULT 'employer';

ALTER TABLE public.relocation_cases
    ADD COLUMN IF NOT EXISTS sponsor_id text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'relocation_cases_funding_source_check'
    ) THEN
        ALTER TABLE public.relocation_cases
            ADD CONSTRAINT relocation_cases_funding_source_check
            CHECK (funding_source IN ('employer', 'self', 'sponsor', 'internal'));
    END IF;
END $$;

-- A sponsor_id is meaningful only for a sponsored case, and a sponsored case must name its
-- sponsor. Without this pairing "who is covering this move?" has no reliable answer at the
-- moment the UI has to say it out loud.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'relocation_cases_sponsor_id_pairing_check'
    ) THEN
        ALTER TABLE public.relocation_cases
            ADD CONSTRAINT relocation_cases_sponsor_id_pairing_check
            CHECK (
                (funding_source = 'sponsor' AND sponsor_id IS NOT NULL)
                OR (funding_source <> 'sponsor' AND sponsor_id IS NULL)
            );
    END IF;
END $$;

COMMENT ON COLUMN public.relocation_cases.funding_source IS
    'Who pays for this case: employer | self | sponsor | internal. A FUNDING ARRANGEMENT, '
    'never a property of the person. Do not add a column recording the mover''s status.';
COMMENT ON COLUMN public.relocation_cases.sponsor_id IS
    'The programme covering a sponsored case. Required when funding_source = ''sponsor'', '
    'NULL otherwise.';

CREATE INDEX IF NOT EXISTS idx_relocation_cases_funding_source
    ON public.relocation_cases (funding_source);

-- ── 2. append-only entitlement grant log ────────────────────────────────────────────────
--
-- An `access_tier` is the CURRENT answer; this is the history of how it got there. It exists
-- because a policy change must never silently revoke access somebody already has: a grant is
-- an event that happened, not a value to recompute. On 2026-08-23 a flag flip left 1,845
-- cases denied their own roadmap with no record of who decided that or why — this table is
-- what makes that answerable next time.

CREATE TABLE IF NOT EXISTS public.case_entitlement_grants (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id       text NOT NULL,
    granted_tier  text NOT NULL,
    reason        text NOT NULL,
    granted_by    text,
    policy_key    text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_entitlement_grants_case
    ON public.case_entitlement_grants (case_id, created_at DESC);

COMMENT ON TABLE public.case_entitlement_grants IS
    'Append-only log of entitlement grants. Never UPDATE or DELETE a row: a grant is an '
    'event that happened. `reason` and `policy_key` must make any grant explainable later.';

-- ── 3. RLS — the three hard gates for a new public table ────────────────────────────────
-- Grant history is tenant data and is never read by the browser: the employee sees their
-- entitlement, not its audit trail. service_role for the backend, admin where is_admin()
-- exists, nothing for anon or authenticated.

ALTER TABLE public.case_entitlement_grants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS case_entitlement_grants_service_role_only ON public.case_entitlement_grants;
CREATE POLICY case_entitlement_grants_service_role_only
    ON public.case_entitlement_grants
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Admin read, when public.is_admin() exists. Guarded because is_admin() is defined
-- out-of-band and a hard dependency would make this migration unapplyable on an environment
-- that has not got it yet — same guard as the candidate_beam migration, for the same reason.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'is_admin' AND pronamespace = 'public'::regnamespace
    ) THEN
        DROP POLICY IF EXISTS case_entitlement_grants_admin_read ON public.case_entitlement_grants;
        CREATE POLICY case_entitlement_grants_admin_read
            ON public.case_entitlement_grants
            FOR SELECT
            USING (public.is_admin());
    ELSE
        RAISE NOTICE 'public.is_admin() absent — case_entitlement_grants is service_role-only here.';
    END IF;
END $$;

REVOKE ALL ON public.case_entitlement_grants FROM anon, authenticated, public;
GRANT ALL ON public.case_entitlement_grants TO service_role;

-- Append-only is enforced by grant, not only by convention: service_role may INSERT and
-- SELECT, and nothing may UPDATE or DELETE. A policy alone would not stop the backend from
-- rewriting its own history.
REVOKE UPDATE, DELETE ON public.case_entitlement_grants FROM service_role;
