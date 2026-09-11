-- [AIQ-2271] Employee reimbursement ledger + dated FX snapshot.
-- case_id is text with no FK to relocation_cases (created out-of-band).
-- company_id is denormalized for tenant scoping. All three public tables
-- take the hard gates: ENABLE RLS + policy + REVOKE anon.

-- ── 1. expense_claims ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.expense_claims (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id            text NOT NULL,
    company_id         text NOT NULL,
    employee_user_id   text,
    status             text NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'paid')),
    hr_note            text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    submitted_at       timestamptz,
    resolved_at        timestamptz,
    resolved_by_user_id text
);

CREATE INDEX IF NOT EXISTS idx_expense_claims_case
    ON public.expense_claims (case_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_expense_claims_company
    ON public.expense_claims (company_id, status);

COMMENT ON TABLE public.expense_claims IS
    'Employee reimbursement claims that draw down against published policy caps. '
    'No FK to relocation_cases; case_id is text. company_id is denormalized for tenant scoping.';

-- ── 2. expense_claim_lines ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.expense_claim_lines (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id                uuid NOT NULL REFERENCES public.expense_claims(id) ON DELETE CASCADE,
    benefit_key             text NOT NULL,
    amount                  numeric NOT NULL,
    currency                text NOT NULL,
    cap_currency            text,
    fx_rate_to_cap          numeric,
    fx_rate_date            date,
    amount_in_cap_currency  numeric,
    receipt_ocr_id          text,
    vendor_name             text,
    expense_date            date,
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expense_claim_lines_claim
    ON public.expense_claim_lines (claim_id);

CREATE INDEX IF NOT EXISTS idx_expense_claim_lines_benefit
    ON public.expense_claim_lines (benefit_key);

COMMENT ON TABLE public.expense_claim_lines IS
    'Line items for an expense claim. FX is snapshotted at submit '
    '(fx_rate_to_cap, fx_rate_date, amount_in_cap_currency) so drawdown is reproducible.';

-- ── 3. fx_rates — dated immutable snapshot (authoring/cron writes) ───────────

CREATE TABLE IF NOT EXISTS public.fx_rates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    as_of_date      date NOT NULL,
    base_currency   text NOT NULL,
    quote_currency  text NOT NULL,
    rate            numeric NOT NULL,
    source          text NOT NULL DEFAULT 'frankfurter',
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (as_of_date, base_currency, quote_currency)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_latest
    ON public.fx_rates (base_currency, quote_currency, as_of_date DESC);

COMMENT ON TABLE public.fx_rates IS
    'Dated FX snapshot (1 base = rate quote). Written by cron from ECB/Frankfurter. '
    'No PII. Serving path reads the latest row and falls back to a hardcoded table.';

-- ── 4. updated_at trigger ────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.set_expense_claims_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_expense_claims_updated_at ON public.expense_claims;
CREATE TRIGGER trg_expense_claims_updated_at
BEFORE UPDATE ON public.expense_claims
FOR EACH ROW EXECUTE PROCEDURE public.set_expense_claims_updated_at();

-- ── 5. RLS — three hard gates per table ──────────────────────────────────────

ALTER TABLE public.expense_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.expense_claim_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fx_rates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS expense_claims_service_role_only ON public.expense_claims;
CREATE POLICY expense_claims_service_role_only
    ON public.expense_claims
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS expense_claim_lines_service_role_only ON public.expense_claim_lines;
CREATE POLICY expense_claim_lines_service_role_only
    ON public.expense_claim_lines
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS fx_rates_service_role_only ON public.fx_rates;
CREATE POLICY fx_rates_service_role_only
    ON public.fx_rates
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'is_admin' AND pronamespace = 'public'::regnamespace
    ) THEN
        DROP POLICY IF EXISTS expense_claims_admin_read ON public.expense_claims;
        CREATE POLICY expense_claims_admin_read
            ON public.expense_claims FOR SELECT USING (public.is_admin());
        DROP POLICY IF EXISTS expense_claim_lines_admin_read ON public.expense_claim_lines;
        CREATE POLICY expense_claim_lines_admin_read
            ON public.expense_claim_lines FOR SELECT USING (public.is_admin());
        DROP POLICY IF EXISTS fx_rates_admin_read ON public.fx_rates;
        CREATE POLICY fx_rates_admin_read
            ON public.fx_rates FOR SELECT USING (public.is_admin());
    ELSE
        RAISE NOTICE 'public.is_admin() absent — expense claim tables are service_role-only here.';
    END IF;
END $$;

REVOKE ALL ON public.expense_claims FROM anon, authenticated, public;
REVOKE ALL ON public.expense_claim_lines FROM anon, authenticated, public;
REVOKE ALL ON public.fx_rates FROM anon, authenticated, public;

GRANT ALL ON public.expense_claims TO service_role;
GRANT ALL ON public.expense_claim_lines TO service_role;
GRANT ALL ON public.fx_rates TO service_role;
