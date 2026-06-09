-- AIQ-909 — Give the policy value-extractor its own output table.
--
-- ROOT CAUSE: `db.replace_policy_benefits` / `list_policy_benefits` (the
-- policy-document value-extraction output) target a table keyed by `policy_id`
-- with extraction columns (service_category, benefit_key, confidence, ...). But
-- the existing prod `policy_benefits` table is the CONFIG-MATRIX / tier-benefits
-- table (keyed by `policy_tier_id`). One table name, two incompatible schemas.
-- `init_db`'s `CREATE TABLE IF NOT EXISTS policy_benefits` was a no-op in prod
-- (the config-matrix table already existed), so the extraction schema never
-- existed → every `POST /api/policies/{id}/extract` ran
-- `DELETE FROM policy_benefits WHERE policy_id = …` → `column "policy_id" does
-- not exist` → 500 → 0 benefits ever written (21 docs stuck, policy_benefits
-- empty). This gives extraction its own table; `database.py` repoints to it.

CREATE TABLE IF NOT EXISTS public.policy_extracted_benefits (
    id               text PRIMARY KEY,
    policy_id        text NOT NULL,          -- references company_policies.id
    service_category text NOT NULL,
    benefit_key      text NOT NULL,
    benefit_label    text NOT NULL,
    eligibility      text,
    limits           text,
    notes            text,
    source_quote     text,
    source_section   text,
    confidence       double precision,
    updated_by       text,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_policy_extracted_benefits_policy
    ON public.policy_extracted_benefits (policy_id);

-- ── Security (hard gates: RLS + policy + revoke anon) ────────────────────────
ALTER TABLE public.policy_extracted_benefits ENABLE ROW LEVEL SECURITY;

-- Tenant scope, mirroring the existing `policy_benefits_via_tier` policy: a row
-- is visible only to a caller whose company owns the parent company_policies
-- row. The backend writes via the service role (which bypasses RLS); this guards
-- direct PostgREST access via the public anon/authenticated keys.
DROP POLICY IF EXISTS policy_extracted_benefits_via_company ON public.policy_extracted_benefits;
CREATE POLICY policy_extracted_benefits_via_company
    ON public.policy_extracted_benefits
    FOR ALL
    USING (
        policy_id IN (
            SELECT cp.id::text
            FROM public.company_policies cp
            WHERE cp.company_id::text = my_company_id()::text
        )
    );

-- Defense-in-depth: the public anon key (shipped in the frontend bundle) must
-- never reach this table directly (SEC-002 class).
REVOKE ALL ON public.policy_extracted_benefits FROM anon;
