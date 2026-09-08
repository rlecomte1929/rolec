-- ============================================================
-- [P1-04 follow-up] SEED — EEA-pathway forms for France→Norway
-- Date: 2026-06-04
--
-- The Norway seed (20260521010000) covered the SKILLED-WORKER pathway
-- (UTL-2011 work permit + family + post-arrival registrations). But a French
-- (EU/EEA) national relocating to Norway follows the EEA REGISTRATION scheme,
-- not a work permit (per P0-01). Two forms were missing for that pathway:
--   1. EU/EEA registration (Politiet/UDI registration scheme)
--   2. Civil-document apostille (origin-side French civil documents)
--
-- These trigger on visa_type='eea_registration', which the Trigger Engine now
-- derives when an EEA-origin employee relocates to an EEA country
-- (backend/app/services/trigger_engine.py). D-number (GP-7-04) already triggers
-- on destination_country='NO', so the full France→Norway set now surfaces:
-- EEA registration + D-number + civil-document apostille.
--
-- Idempotent via ON CONFLICT (code, version). source_url is set so the Dossier
-- card shows the Official-source link; matching source_pages rows are seeded so
-- "Last verified" (P1-05d) resolves for these forms too.
-- ============================================================

-- 1. EU/EEA registration (Norwegian Police / UDI registration scheme)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, source_url, fields, trigger_rules)
VALUES (
  'POL-EEA-REG',
  'Registreringsordningen for EU/EØS-borgere (EU/EEA registration)',
  'NO',
  'POL',
  'Politiet (Norwegian Police) — UDI registration scheme',
  'registration',
  '1.0.0',
  'https://www.udi.no/en/want-to-apply/registration-scheme-for-eu-eea-nationals/',
  '[
    {"id":"full_name","label":"Full legal name","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","label":"Date of birth","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nationality","label":"Nationality (ISO)","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":3},
    {"id":"passport_number","label":"Passport or national ID number","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":4},
    {"id":"purpose_of_stay","label":"Purpose of stay","type":"select","required":true,"prefill_source":null,"requires_original":false,"position":5},
    {"id":"employer_name","label":"Employer in Norway","type":"text","required":false,"prefill_source":"contract.employer_name","requires_original":false,"position":6},
    {"id":"address_in_norway","label":"Address in Norway","type":"text","required":false,"prefill_source":null,"requires_original":false,"position":7}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"NO","visa_type":"eea_registration"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":100}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- 2. Civil-document apostille (origin-side French civil documents)
INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, source_url, fields, trigger_rules)
VALUES (
  'APOSTILLE-FR',
  'Apostille des documents d''état civil (civil-document apostille)',
  'FR',
  'FR-COURDAPPEL',
  'Cour d''appel (France) — service-public.fr',
  'civil_documents',
  '1.0.0',
  'https://www.service-public.fr/particuliers/vosdroits/F1402',
  '[
    {"id":"document_type","label":"Civil document type (birth/marriage certificate, …)","type":"select","required":true,"prefill_source":null,"requires_original":true,"position":1},
    {"id":"document_reference","label":"Document reference / number","type":"text","required":true,"prefill_source":null,"requires_original":true,"position":2},
    {"id":"issuing_authority","label":"Issuing authority","type":"text","required":true,"prefill_source":null,"requires_original":false,"position":3},
    {"id":"apostille_date","label":"Apostille date","type":"date","required":false,"prefill_source":null,"requires_original":false,"position":4}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"NO","visa_type":"eea_registration"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":95}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- 3. source_pages rows for the two new official URLs (P1-05d "Last verified").
INSERT INTO public.source_pages (url, tier, last_fetched_at)
SELECT DISTINCT ft.source_url, '1', now()
FROM public.form_templates ft
WHERE ft.code IN ('POL-EEA-REG', 'APOSTILLE-FR') AND ft.source_url IS NOT NULL
ON CONFLICT (url) DO NOTHING;
