-- Ledger reconciliation — no schema change. Recovered, not authored.
--
-- This migration was applied to production out-of-band on 2026-08-05 and the repo file was
-- never committed. It is the ONLY version in the prod ledger with no matching repo file, and
-- that single orphan fails `scripts/check_migration_drift.py` on EVERY migration PR (measured
-- 2026-08-10 against PR #1754: 435 ledger rows, 582 repo files, exactly 1 orphan). See
-- CLAUDE.md "Ledger reconciliation (hotfix only)".
--
-- The body below is the literal `statements` array from
-- `supabase_migrations.schema_migrations WHERE version = '20260805214336'`, joined on newlines.
-- It is NOT edited, tidied or improved: the ledger already records this version as applied, so
-- the file's job is to say truthfully what ran. Anything else reintroduces drift in the other
-- direction — a repo file that does not match the applied schema.
--
-- Re-running it is safe. Verified before committing:
--   * every CREATE TABLE / CREATE INDEX carries IF NOT EXISTS
--   * every ADD COLUMN carries IF NOT EXISTS (checked: zero unguarded)
--   * the seed INSERT is ON CONFLICT (code) DO UPDATE
--   * both CHECK constraints and all four policies are wrapped in pg_constraint / pg_policies
--     existence guards
--   * the view is CREATE OR REPLACE
--
-- Prod state confirmed to match this SQL on 2026-08-10 (read-only):
--   supplier_service_categories  rls=on  policies=1
--   supplier_accreditations      rls=on  policies=2
--   supplier_red_flags           rls=on  policies=1
-- so the new-table security gate in CLAUDE.md is already satisfied on the live database.
--
-- One thing this does NOT fix, recorded so it is not mistaken for resolved: these tables have
-- no reader. `supplier_service_categories`, `supplier_accreditations` and `supplier_red_flags`
-- have zero references anywhere in the repo — no model, no service, no router, no frontend.
-- Committing this file makes the schema honest; it does not make the feature live.

-- BRAIN-3C supplier qualification layer. Additive only. See Notion BRAIN-3C.
-- Extends existing System A (suppliers -> supplier_service_capabilities ->
-- supplier_scoring_metadata; vendor_curation_runs -> vendor_candidates).
-- Does NOT create a parallel supplier system. Does NOT touch vendors_legacy
-- or company_preferred_suppliers (both deprecated).

CREATE TABLE IF NOT EXISTS public.supplier_service_categories (
    code                text PRIMARY KEY,
    display_name        text        NOT NULL,
    brain3c_category    text,
    brain3c_ref         smallint,
    is_live             boolean     NOT NULL DEFAULT false,
    compliance_critical boolean     NOT NULL DEFAULT false,
    accrediting_bodies  text[]      NOT NULL DEFAULT '{}',
    sort_order          smallint    NOT NULL DEFAULT 99,
    created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.supplier_service_categories IS
  'Reference taxonomy bridging the 6 live service_category values to the 10 BRAIN-3C supplier categories. Advisory only - not FK-enforced, because service_category is free text in supplier_service_capabilities, service_catalog_items, corridor_coverage_targets and supplier_service_area_coverage.';
COMMENT ON COLUMN public.supplier_service_categories.compliance_critical IS
  'BRAIN-3C key insight: only Immigration and Tax are required for every assignment type. Everything else is policy-dependent.';

INSERT INTO public.supplier_service_categories
    (code, display_name, brain3c_category, brain3c_ref, is_live, compliance_critical, accrediting_bodies, sort_order)
VALUES
    ('legal_admin','Immigration / Legal Counsel','Immigration / Legal Counsel',1,true,true,
        ARRAY['AILA','OISC','Law Society','national bar','IBA'],1),
    ('rmc','Relocation Management Company','Relocation Management Company',2,false,false,
        ARRAY['FIDI','CERC','EURA'],2),
    ('dsp','Destination Service Provider','Destination Service Provider',3,false,false,
        ARRAY['FIDI FAIM DSP','EURA','ISO 9001'],3),
    ('movers','Household Goods / Moving','Household Goods / International Moving',4,true,false,
        ARRAY['FIDI FAIM','IAM','OMNI','IATA'],4),
    ('housing_agencies','Housing & Temporary Accommodation','Temporary / Corporate Housing',5,true,false,
        ARRAY['CHPA','national letting body'],5),
    ('tax_finance','Tax Advisory & Shadow Payroll','Tax Advisory & Shadow Payroll',6,true,true,
        ARRAY['CPA','CA','national tax institute'],6),
    ('schools','School Search & Education','School Search & Education Consultant',7,true,false,
        ARRAY['IECA','national education body'],7),
    ('healthcare_ipmi','Healthcare & International Insurance','Healthcare & International Insurance (IPMI)',8,false,false,
        ARRAY['FCA','national financial conduct authority'],8),
    ('language_cultural','Language & Cultural Training','Language & Cultural Training',9,false,false,
        ARRAY['Country Navigator licence'],9),
    ('partner_family','Partner & Family Support','Partner & Family Support Services',10,false,false,
        ARRAY['Permits Foundation partner'],10),
    ('banks','Banking & Account Opening',NULL,NULL,true,false,ARRAY[]::text[],11)
ON CONFLICT (code) DO UPDATE SET
    display_name        = EXCLUDED.display_name,
    brain3c_category    = EXCLUDED.brain3c_category,
    brain3c_ref         = EXCLUDED.brain3c_ref,
    compliance_critical = EXCLUDED.compliance_critical,
    accrediting_bodies  = EXCLUDED.accrediting_bodies,
    sort_order          = EXCLUDED.sort_order;

ALTER TABLE public.suppliers
    ADD COLUMN IF NOT EXISTS legal_registration_number text,
    ADD COLUMN IF NOT EXISTS vat_number                text,
    ADD COLUMN IF NOT EXISTS incorporation_country     char(2),
    ADD COLUMN IF NOT EXISTS entity_verified_at        timestamptz,
    ADD COLUMN IF NOT EXISTS entity_verified_source    text,
    ADD COLUMN IF NOT EXISTS issues_corporate_invoice  boolean,
    ADD COLUMN IF NOT EXISTS accepts_purchase_order    boolean,
    ADD COLUMN IF NOT EXISTS payment_terms_days        smallint,
    ADD COLUMN IF NOT EXISTS billing_currency          char(3),
    ADD COLUMN IF NOT EXISTS gdpr_lawful_basis         text,
    ADD COLUMN IF NOT EXISTS data_collected_at         timestamptz;

COMMENT ON COLUMN public.suppliers.issues_corporate_invoice IS
  'BRAIN-3C temp-housing red flag: no corporate invoice means Finance cannot process. NULL = unknown, not false.';
COMMENT ON COLUMN public.suppliers.gdpr_lawful_basis IS
  'Provenance for enterprise security review. e.g. legitimate_interest_b2b, public_register, supplier_submitted.';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='suppliers_payment_terms_days_check') THEN
        ALTER TABLE public.suppliers ADD CONSTRAINT suppliers_payment_terms_days_check
            CHECK (payment_terms_days IS NULL OR (payment_terms_days >= 0 AND payment_terms_days <= 180));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='suppliers_gdpr_lawful_basis_check') THEN
        ALTER TABLE public.suppliers ADD CONSTRAINT suppliers_gdpr_lawful_basis_check
            CHECK (gdpr_lawful_basis IS NULL OR gdpr_lawful_basis = ANY (ARRAY[
                'legitimate_interest_b2b','public_register','supplier_submitted','contract','consent']));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.supplier_accreditations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id         varchar     NOT NULL REFERENCES public.suppliers(id) ON DELETE CASCADE,
    body                text        NOT NULL,
    scheme              text,
    membership_number   text,
    status              text        NOT NULL DEFAULT 'claimed',
    valid_from          date,
    valid_until         date,
    evidence_url        text,
    verification_method text,
    verified_by         text,
    verified_at         timestamptz,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT supplier_accreditations_status_check
        CHECK (status = ANY (ARRAY['claimed','verified','expired','revoked','not_found'])),
    CONSTRAINT supplier_accreditations_verification_method_check
        CHECK (verification_method IS NULL OR verification_method = ANY (ARRAY[
            'public_registry','supplier_document','manual_email','directory_listing'])),
    CONSTRAINT supplier_accreditations_dates_check
        CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CONSTRAINT supplier_accreditations_verified_needs_evidence
        CHECK (status <> 'verified' OR (evidence_url IS NOT NULL AND verified_at IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS supplier_accreditations_unique_claim
    ON public.supplier_accreditations (supplier_id, body, COALESCE(scheme, ''));
CREATE INDEX IF NOT EXISTS supplier_accreditations_supplier_idx
    ON public.supplier_accreditations (supplier_id);
CREATE INDEX IF NOT EXISTS supplier_accreditations_expiry_idx
    ON public.supplier_accreditations (valid_until) WHERE status = 'verified';

COMMENT ON TABLE public.supplier_accreditations IS
  'BRAIN-3C qualification evidence. One row per accreditation claim. status=verified requires evidence_url + verified_at by CHECK constraint, so a verified row is always reproducible by a human.';

CREATE TABLE IF NOT EXISTS public.supplier_red_flags (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id   varchar     NOT NULL REFERENCES public.suppliers(id) ON DELETE CASCADE,
    flag_code     text        NOT NULL,
    severity      text        NOT NULL DEFAULT 'warning',
    detail        text,
    evidence_url  text,
    raised_by     text,
    raised_at     timestamptz NOT NULL DEFAULT now(),
    resolved_at   timestamptz,
    resolution    text,
    CONSTRAINT supplier_red_flags_severity_check
        CHECK (severity = ANY (ARRAY['warning','disqualifying']))
);
CREATE INDEX IF NOT EXISTS supplier_red_flags_open_idx
    ON public.supplier_red_flags (supplier_id) WHERE resolved_at IS NULL;

COMMENT ON TABLE public.supplier_red_flags IS
  'Structured BRAIN-3C red flags. severity=disqualifying should block promotion out of vendor_candidates and block appearance in recommendation slates.';

ALTER TABLE public.supplier_service_capabilities
    ADD COLUMN IF NOT EXISTS local_office_in_country  boolean,
    ADD COLUMN IF NOT EXISTS years_in_market          smallint,
    ADD COLUMN IF NOT EXISTS sla_commitment           text,
    ADD COLUMN IF NOT EXISTS sla_documented           boolean,
    ADD COLUMN IF NOT EXISTS named_single_contact     boolean,
    ADD COLUMN IF NOT EXISTS reference_checked_at     timestamptz,
    ADD COLUMN IF NOT EXISTS brain3c_qualified        boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.supplier_service_capabilities.brain3c_qualified IS
  'True only when the category-specific BRAIN-3C qualification criteria are all met and evidenced. Drives the curated-network view; does not affect legacy listing behaviour.';

ALTER TABLE public.vendor_candidates
    ADD COLUMN IF NOT EXISTS accreditation_body     text,
    ADD COLUMN IF NOT EXISTS accreditation_number   text,
    ADD COLUMN IF NOT EXISTS accreditation_expiry   date,
    ADD COLUMN IF NOT EXISTS legal_name             text,
    ADD COLUMN IF NOT EXISTS vat_number             text,
    ADD COLUMN IF NOT EXISTS corridor               text,
    ADD COLUMN IF NOT EXISTS phone                  text,
    ADD COLUMN IF NOT EXISTS dedupe_key             text;

CREATE INDEX IF NOT EXISTS vendor_candidates_dedupe_key_idx
    ON public.vendor_candidates (dedupe_key);
CREATE INDEX IF NOT EXISTS vendor_candidates_pending_idx
    ON public.vendor_candidates (service_category, country_code) WHERE status = 'pending';

COMMENT ON COLUMN public.vendor_candidates.dedupe_key IS
  'Normalised registrable domain (lowercase, no scheme, no www). Harvester must check this against suppliers.website before inserting.';

ALTER TABLE public.supplier_service_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_accreditations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.supplier_red_flags          ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
        AND tablename='supplier_service_categories' AND policyname='supplier_categories_select') THEN
        CREATE POLICY supplier_categories_select ON public.supplier_service_categories
            FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
        AND tablename='supplier_accreditations' AND policyname='supplier_accreditations_select') THEN
        CREATE POLICY supplier_accreditations_select ON public.supplier_accreditations
            FOR SELECT TO authenticated USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
        AND tablename='supplier_accreditations' AND policyname='svc_all_supplier_accreditations') THEN
        CREATE POLICY svc_all_supplier_accreditations ON public.supplier_accreditations
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
        AND tablename='supplier_red_flags' AND policyname='svc_all_supplier_red_flags') THEN
        CREATE POLICY svc_all_supplier_red_flags ON public.supplier_red_flags
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

REVOKE ALL ON public.supplier_red_flags FROM anon, authenticated;

CREATE OR REPLACE VIEW public.supplier_qualification_status AS
SELECT
    s.id AS supplier_id,
    s.name,
    s.status,
    ssc.service_category,
    cat.brain3c_category,
    cat.compliance_critical,
    s.incorporation_country,
    (s.legal_registration_number IS NOT NULL OR s.vat_number IS NOT NULL) AS entity_identified,
    COALESCE(s.issues_corporate_invoice, false) AS can_invoice_corporate,
    ssc.local_office_in_country,
    ssc.sla_documented,
    ssc.brain3c_qualified,
    acc.verified_accreditations,
    acc.expiring_within_90d,
    COALESCE(rf.open_disqualifying, 0) AS open_disqualifying_flags,
    sm.last_verified_at
FROM public.suppliers s
-- LEFT JOIN, not INNER: 2 of 67 live suppliers have no capability row
-- (verified 2026-08-05). Those are exactly the records curation must see.
LEFT JOIN public.supplier_service_capabilities ssc ON ssc.supplier_id = s.id
LEFT JOIN public.supplier_service_categories cat ON cat.code = ssc.service_category
LEFT JOIN public.supplier_scoring_metadata sm ON sm.supplier_id = s.id
LEFT JOIN LATERAL (
    SELECT
        count(*) FILTER (WHERE a.status='verified'
            AND (a.valid_until IS NULL OR a.valid_until >= current_date)) AS verified_accreditations,
        count(*) FILTER (WHERE a.status='verified'
            AND a.valid_until BETWEEN current_date AND current_date + 90) AS expiring_within_90d
    FROM public.supplier_accreditations a WHERE a.supplier_id = s.id
) acc ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS open_disqualifying FROM public.supplier_red_flags f
    WHERE f.supplier_id = s.id AND f.resolved_at IS NULL AND f.severity='disqualifying'
) rf ON true;

COMMENT ON VIEW public.supplier_qualification_status IS
  'One row per supplier x service category. Read-only BRAIN-3C readiness summary for the admin curation UI and the corridor coverage report.';
