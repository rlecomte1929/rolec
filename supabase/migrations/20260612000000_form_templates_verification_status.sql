-- WS1 content-honesty: a provenance/maturity flag on immigration form templates.
--
-- Every corridor's form set is *representative scaffolding* until a human
-- (ops/legal) verifies it against the issuing authority. Without an explicit
-- signal, the dossier implies this content is authoritative — a real liability
-- for relocation guidance. This column lets the UI tell users the truth.
--
-- 'representative' = honest default (no human verification claimed)
-- 'draft'         = under review / partially checked
-- 'verified'      = an authorised human confirmed it against the source
--
-- Nothing is marked 'verified' here: that status is reserved for a future
-- ops verification workflow and must never be self-declared by seed data.

ALTER TABLE public.form_templates
  ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT 'representative';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'form_templates_verification_status_chk'
  ) THEN
    ALTER TABLE public.form_templates
      ADD CONSTRAINT form_templates_verification_status_chk
      CHECK (verification_status IN ('verified', 'draft', 'representative'));
  END IF;
END $$;

-- Backfill source_url with the official root domain of the issuing authority,
-- keyed by the stable authority_code. Only unambiguous *national* bodies are
-- mapped. Generic providers (retail banks, health insurers, per-city /
-- cantonal / ward offices, state DMVs) are intentionally left NULL: there is
-- no single canonical URL for them and a wrong link is worse than none.
UPDATE public.form_templates ft
SET source_url = m.url
FROM (VALUES
  ('ICP',              'https://icp.gov.ae'),
  ('MOHRE',            'https://www.mohre.gov.ae'),
  ('BZST',             'https://www.bzst.de'),
  ('AUSWAERTIGES-AMT', 'https://www.auswaertiges-amt.de'),
  ('OEX',              'https://extranjeros.inclusion.gob.es'),
  ('POLICIA',          'https://www.policia.es'),
  ('TGSS',             'https://www.seg-social.es'),
  ('DWP',              'https://www.gov.uk/government/organisations/department-for-work-pensions'),
  ('HMRC',             'https://www.gov.uk/government/organisations/hm-revenue-customs'),
  ('NHS',              'https://www.nhs.uk'),
  ('UKVI',             'https://www.gov.uk/government/organisations/uk-visas-and-immigration'),
  ('ISA',              'https://www.isa.go.jp'),
  ('MOFA',             'https://www.mofa.go.jp'),
  ('BELASTINGDIENST',  'https://www.belastingdienst.nl'),
  ('IND',              'https://ind.nl'),
  ('ICA',              'https://www.ica.gov.sg'),
  ('IRAS',             'https://www.iras.gov.sg'),
  ('MOM',              'https://www.mom.gov.sg'),
  ('SSA',              'https://www.ssa.gov'),
  ('USCIS',            'https://www.uscis.gov'),
  ('DOS',              'https://www.state.gov')
) AS m(code, url)
WHERE ft.authority_code = m.code
  AND (ft.source_url IS NULL OR ft.source_url = '');
