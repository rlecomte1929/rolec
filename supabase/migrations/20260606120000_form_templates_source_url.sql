-- ============================================================
-- [P1-05 / AIQ-199] form_templates.source_url
-- Date: 2026-06-04
--
-- Adds the official "Tier 1" source URL to each government form template,
-- so the Dossier & Forms tab can link the employee straight to the official
-- page where the form is completed/submitted (V1 has no pre-fill proxy —
-- all submissions go directly to the official source).
--
-- This is a nullable column add on an EXISTING table (form_templates already
-- has RLS + policies from 20260521000000_dossier_forms_core.sql), so no new
-- RLS gate is required here.
--
-- The UPDATEs below seed Tier-1 URLs for the 8 Norway templates seeded in
-- 20260521010000_seed_norway_form_templates.sql. They are idempotent (keyed
-- by code) and only fill rows where source_url is still NULL, so re-running
-- never clobbers an ops-verified URL.
--
-- ⚠️ Reviewer note: these URLs are authority-official but should be
-- ops/legal-verified against the live page. The "Last verified" surface
-- (P1-05d, source freshness) tracks that verification once it lands.
-- ============================================================

ALTER TABLE public.form_templates
  ADD COLUMN IF NOT EXISTS source_url text;

COMMENT ON COLUMN public.form_templates.source_url IS
  'Official Tier-1 authority URL where this form is completed/submitted (e.g. the UDI/Skatteetaten page). Surfaced on the Dossier & Forms card. V1 links out directly — no submission proxy.';

-- ---- Seed Tier-1 source URLs for the Norway form set (idempotent) ----

UPDATE public.form_templates SET source_url =
  'https://www.udi.no/en/want-to-apply/work-immigration/skilled-workers/'
  WHERE code = 'UTL-2011' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.udi.no/en/want-to-apply/family-immigration/who-can-apply/spouse/'
  WHERE code = 'UTL-2011F' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.udi.no/en/want-to-apply/family-immigration/who-can-apply/children/'
  WHERE code = 'UTL-2011B' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.skatteetaten.no/en/person/national-registry/moving/move-to-norway/'
  WHERE code = 'RF-1234' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.skatteetaten.no/en/person/foreign/norwegian-identification-number/d-number/'
  WHERE code = 'GP-7-04' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.helfo.no/en/national-insurance/membership-of-the-national-insurance-scheme'
  WHERE code = 'HELFO-1' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.skatteetaten.no/en/person/taxes/tax-deduction-cards-and-advance-tax/'
  WHERE code = 'RF-1209' AND country = 'NO' AND source_url IS NULL;

UPDATE public.form_templates SET source_url =
  'https://www.nav.no/en/home/rules-and-regulations/account-number-for-payments-from-nav'
  WHERE code = 'NAV-08' AND country = 'NO' AND source_url IS NULL;
