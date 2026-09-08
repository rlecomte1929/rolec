-- =============================================================================
-- AIQ-40-A: Vendor directory extension + seed data
--
-- Extends the existing public.vendors table with corridor and org scoping,
-- then seeds 5 real providers per service category for the top 3 corridors:
--   FR→DE  (France → Germany)
--   DE→US  (Germany → United States)
--   US→FR  (United States → France)
--
-- Corridor format: "{origin_iso2}-{dest_iso2}" e.g. "FR-DE"
-- A vendor with corridors = '{FR-DE,DE-US}' matches either corridor.
-- A vendor with corridors = '{}' is treated as global (matches any corridor).
--
-- Service categories (5 MVP categories):
--   housing        — Housing search (short-term + long-term)
--   immigration    — Immigration / visa / permit filing
--   moving         — Moving & shipping
--   school_search  — School search (international + expat schools)
--   destination    — Destination orientation (city guide, banking, settling-in)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Extend vendors table
-- ---------------------------------------------------------------------------
ALTER TABLE public.vendors
  ADD COLUMN IF NOT EXISTS corridors      text[]  NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS org_id         text    DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS is_approved    boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_vendors_corridors
  ON public.vendors USING GIN (corridors);

CREATE INDEX IF NOT EXISTS idx_vendors_service_types
  ON public.vendors USING GIN (service_types);

CREATE INDEX IF NOT EXISTS idx_vendors_org_id
  ON public.vendors (org_id)
  WHERE org_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. RLS — HR can see global vendors (org_id IS NULL) + their own org vendors
-- ---------------------------------------------------------------------------
ALTER TABLE public.vendors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS vendors_hr_select ON public.vendors;
CREATE POLICY vendors_hr_select ON public.vendors
  FOR SELECT TO authenticated
  USING (
    status = 'active'
    AND (
      org_id IS NULL
      OR org_id IN (
        SELECT company_id FROM public.hr_users
        WHERE profile_id = (SELECT auth.uid()::text)
      )
    )
  );

DROP POLICY IF EXISTS vendors_service_role ON public.vendors;
CREATE POLICY vendors_service_role ON public.vendors
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- 3. Seed global vendors (org_id = NULL, available to all HR orgs)
-- ---------------------------------------------------------------------------

-- HOUSING SEARCH ─────────────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
VALUES
  (
    'Homelike',
    '{"housing"}',
    '{"DE","FR","NL","BE","AT","CH"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'corporate@homelike.com',
    'active', true
  ),
  (
    'Spotahome',
    '{"housing"}',
    '{"DE","FR","ES","IT","PT","BE"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'business@spotahome.com',
    'active', true
  ),
  (
    'Habyt',
    '{"housing"}',
    '{"DE","US","FR","NL","IT","ES"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'enterprise@habyt.com',
    'active', true
  ),
  (
    'Nestpick',
    '{"housing"}',
    '{"DE","FR","NL","BE"}',
    '{"FR-DE","DE-US","US-FR"}',
    'corporate@nestpick.com',
    'active', true
  ),
  (
    'Wunderflats',
    '{"housing"}',
    '{"DE"}',
    '{"FR-DE","US-DE","DE-FR","DE-US"}',
    'business@wunderflats.com',
    'active', true
  )
ON CONFLICT DO NOTHING;

-- IMMIGRATION / VISA ─────────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
VALUES
  (
    'Fragomen',
    '{"immigration"}',
    '{"DE","FR","US","GB","NL","BE","CH","AT"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'mobility@fragomen.com',
    'active', true
  ),
  (
    'KPMG Law — Global Mobility',
    '{"immigration"}',
    '{"DE","FR","US","NL","BE","LU"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'globalmobility@kpmg.com',
    'active', true
  ),
  (
    'Deloitte Legal — Immigration',
    '{"immigration"}',
    '{"DE","FR","US","GB","NL"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'immigration@deloitte.com',
    'active', true
  ),
  (
    'PwC Legal — Mobility',
    '{"immigration"}',
    '{"DE","FR","US","NL","BE"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'mobility@pwc.com',
    'active', true
  ),
  (
    'GT-Visa (Global Tax Network)',
    '{"immigration"}',
    '{"DE","US","FR","NL","GB","CH"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'visaservices@gtn.com',
    'active', true
  )
ON CONFLICT DO NOTHING;

-- MOVING & SHIPPING ──────────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
VALUES
  (
    'Crown Relocations',
    '{"moving"}',
    '{"DE","FR","US","GB","NL","BE","AT","CH"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'corporate@crownrelo.com',
    'active', true
  ),
  (
    'Santa Fe Relocation',
    '{"moving"}',
    '{"DE","FR","US","GB","NL","BE","SG"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'mobility@santaferelo.com',
    'active', true
  ),
  (
    'Gosselin Mobility',
    '{"moving"}',
    '{"DE","FR","BE","NL","LU","AT"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","FR-US"}',
    'mobility@gosselin.com',
    'active', true
  ),
  (
    'AGS Movers',
    '{"moving"}',
    '{"DE","FR","US","GB","NL","CH"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'corporate@ags-worldwide.com',
    'active', true
  ),
  (
    'Allied Van Lines International',
    '{"moving"}',
    '{"US","DE","FR","GB","CA","AU"}',
    '{"DE-US","US-FR","US-DE","FR-US"}',
    'international@allied.com',
    'active', true
  )
ON CONFLICT DO NOTHING;

-- SCHOOL SEARCH ──────────────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
VALUES
  (
    'ISS — International School Search',
    '{"school_search"}',
    '{"DE","FR","US","NL","BE","CH","AT"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'search@internationalschool.com',
    'active', true
  ),
  (
    'Expatica School Finder',
    '{"school_search"}',
    '{"DE","FR","NL","BE","CH","AT","LU"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'schools@expatica.com',
    'active', true
  ),
  (
    'TIE Online — School Admissions',
    '{"school_search"}',
    '{"DE","FR","US","GB","NL"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'admissions@tieonline.com',
    'active', true
  ),
  (
    'Expat School Guide (Germany)',
    '{"school_search"}',
    '{"DE"}',
    '{"FR-DE","US-DE","DE-FR","DE-US"}',
    'guide@expat-school.de',
    'active', true
  ),
  (
    'Paris International School Advisor',
    '{"school_search"}',
    '{"FR"}',
    '{"DE-FR","US-FR","FR-DE","FR-US"}',
    'advisor@paris-schools.fr',
    'active', true
  )
ON CONFLICT DO NOTHING;

-- DESTINATION ORIENTATION ────────────────────────────────────────────────────
INSERT INTO public.vendors (name, service_types, countries, corridors, contact_email, status, is_approved)
VALUES
  (
    'Dwellworks',
    '{"destination"}',
    '{"DE","FR","US","GB","NL","BE","CH","AT"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'mobility@dwellworks.com',
    'active', true
  ),
  (
    'Cartus — Destination Services',
    '{"destination"}',
    '{"DE","FR","US","GB","NL","BE"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'destination@cartus.com',
    'active', true
  ),
  (
    'Aires — Relocation Services',
    '{"destination"}',
    '{"US","DE","FR","GB","NL","CA"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'destination@aires.com',
    'active', true
  ),
  (
    'ECA International — Settling-In',
    '{"destination"}',
    '{"DE","FR","US","GB","NL","BE","CH"}',
    '{"FR-DE","DE-US","US-FR","DE-FR","US-DE","FR-US"}',
    'mobility@eca-international.com',
    'active', true
  ),
  (
    'Weichert Workforce Mobility',
    '{"destination"}',
    '{"US","DE","FR","GB","CA","AU"}',
    '{"DE-US","US-FR","US-DE","FR-US"}',
    'destination@weichertmobility.com',
    'active', true
  )
ON CONFLICT DO NOTHING;
