-- Migration: policy_cap_exceptions
-- P3-3: Exception request workflow — policy cap requests + per-employee overrides
--
-- Creates:
--   policy_cap_requests      — employee-initiated cap exception requests (HR resolves)
--   employee_cap_overrides   — per-employee approved cap grants (never mutates base policy)
--
-- Idempotent: IF NOT EXISTS guards on CREATE TABLE; ALTER TABLE for new columns
-- is safe on a fresh table. On an existing table the column already exists from
-- a prior migration and Postgres will skip via the IF NOT EXISTS clause.

-- ---------------------------------------------------------------------------
-- 1. policy_cap_requests
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS policy_cap_requests (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id              UUID NOT NULL,
    organization_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category             TEXT NOT NULL CHECK (char_length(category) BETWEEN 1 AND 100),
    requested_amount     NUMERIC(12, 2) NOT NULL CHECK (requested_amount >= 0),
    cap_amount           NUMERIC(12, 2) NOT NULL CHECK (cap_amount >= 0),
    currency             CHAR(3) NOT NULL,
    reason               TEXT NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 2000),
    status               TEXT NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'approved', 'rejected', 'countered')),
    hr_note              TEXT CHECK (hr_note IS NULL OR char_length(hr_note) <= 2000),
    counter_amount       NUMERIC(12, 2) CHECK (counter_amount IS NULL OR counter_amount >= 0),
    -- GAP-7 enriched fields (nullable for backward compat)
    benefit_key          TEXT,
    type_label           TEXT,
    current_value        JSONB,
    requested_value      JSONB,
    ai_insight           TEXT,
    requested_by_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resolved_by_user_id  UUID REFERENCES auth.users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at          TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enforce: counter_amount must be set when status = 'countered'
ALTER TABLE policy_cap_requests
    DROP CONSTRAINT IF EXISTS chk_counter_amount_on_countered;
ALTER TABLE policy_cap_requests
    ADD CONSTRAINT chk_counter_amount_on_countered
        CHECK (status <> 'countered' OR counter_amount IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_policy_cap_requests_org
    ON policy_cap_requests (organization_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_policy_cap_requests_case
    ON policy_cap_requests (case_id, organization_id);

-- ---------------------------------------------------------------------------
-- 2. employee_cap_overrides
-- ---------------------------------------------------------------------------
-- Approved cap grants for individual employees — read by the policy assistant
-- when answering cap questions for a specific employee.

CREATE TABLE IF NOT EXISTS employee_cap_overrides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_code   TEXT NOT NULL CHECK (char_length(category_code) BETWEEN 1 AND 100),
    approved_cap    NUMERIC(12, 2) NOT NULL CHECK (approved_cap >= 0),
    currency        CHAR(3) NOT NULL,
    approved_by     UUID NOT NULL REFERENCES auth.users(id),
    approved_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expiry_date     DATE,
    exception_id    UUID REFERENCES policy_cap_requests(id)
);

CREATE INDEX IF NOT EXISTS idx_employee_cap_overrides_employee
    ON employee_cap_overrides (employee_id, company_id, category_code);

-- ---------------------------------------------------------------------------
-- 3. Row-Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE policy_cap_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_cap_overrides ENABLE ROW LEVEL SECURITY;

-- policy_cap_requests: employees see only their own; HR/Admin see their company's
DROP POLICY IF EXISTS "employees_see_own_requests" ON policy_cap_requests;
CREATE POLICY "employees_see_own_requests"
    ON policy_cap_requests FOR SELECT
    USING (
        requested_by_user_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::uuid = auth.uid()
              AND p.company_id = organization_id
              AND p.role IN ('HR', 'ADMIN')
        )
    );

DROP POLICY IF EXISTS "employees_insert_own_requests" ON policy_cap_requests;
CREATE POLICY "employees_insert_own_requests"
    ON policy_cap_requests FOR INSERT
    WITH CHECK (requested_by_user_id = auth.uid());

DROP POLICY IF EXISTS "hr_update_company_requests" ON policy_cap_requests;
CREATE POLICY "hr_update_company_requests"
    ON policy_cap_requests FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::uuid = auth.uid()
              AND p.company_id = organization_id
              AND p.role IN ('HR', 'ADMIN')
        )
    );

-- employee_cap_overrides: employees see their own; HR/Admin see their company's
DROP POLICY IF EXISTS "employees_see_own_overrides" ON employee_cap_overrides;
CREATE POLICY "employees_see_own_overrides"
    ON employee_cap_overrides FOR SELECT
    USING (
        employee_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::uuid = auth.uid()
              AND p.company_id = company_id
              AND p.role IN ('HR', 'ADMIN')
        )
    );

DROP POLICY IF EXISTS "hr_insert_overrides" ON employee_cap_overrides;
CREATE POLICY "hr_insert_overrides"
    ON employee_cap_overrides FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::uuid = auth.uid()
              AND p.company_id = company_id
              AND p.role IN ('HR', 'ADMIN')
        )
    );

-- ---------------------------------------------------------------------------
-- 4. updated_at trigger for policy_cap_requests
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_policy_cap_requests_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_policy_cap_requests_updated_at ON policy_cap_requests;
CREATE TRIGGER trg_policy_cap_requests_updated_at
    BEFORE UPDATE ON policy_cap_requests
    FOR EACH ROW EXECUTE FUNCTION update_policy_cap_requests_updated_at();
