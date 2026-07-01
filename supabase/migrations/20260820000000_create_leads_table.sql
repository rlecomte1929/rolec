-- Person-level inbound lead CRM (GTM-internal). No company_id tenant scoping
-- (not customer/tenant data), but RLS is still mandatory per the repo hard gate.
CREATE TABLE IF NOT EXISTS public.leads (
    id             text PRIMARY KEY,
    email          text NOT NULL,
    first_name     text,
    last_name      text,
    company_domain text,            -- FK-by-value to prospect_candidates.company_domain
    source         text NOT NULL DEFAULT 'marketing_site',  -- marketing_site | manual | referral
    status         text NOT NULL DEFAULT 'new',             -- new|contacted|qualified|converted|lost
    tags           jsonb NOT NULL DEFAULT '[]'::jsonb,       -- JSON array; SQLAlchemy generic JSON (jsonb on PG, TEXT on SQLite test env)
    message        text,
    utm_source     text,
    utm_campaign   text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_leads_email          ON public.leads (email);
CREATE INDEX IF NOT EXISTS idx_leads_status         ON public.leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_company_domain ON public.leads (company_domain);
CREATE INDEX IF NOT EXISTS idx_leads_created_at     ON public.leads (created_at DESC);

-- Security gate (all three mandatory)
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "leads admin all" ON public.leads;
CREATE POLICY "leads admin all" ON public.leads
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

REVOKE ALL ON public.leads FROM anon;
