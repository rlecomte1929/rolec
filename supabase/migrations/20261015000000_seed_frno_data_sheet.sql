-- Auto-fill vertical slice — SEED: France -> Norway Personal Relocation Data Sheet.
--
-- Models the Audos-validated "data-sheet" (NOT a fillable government PDF): for a
-- FRENCH EEA CITIZEN moving to Norway, the official steps are online-portal /
-- in-person processes, so the deliverable is one reviewable data-sheet the
-- employee carries to appointments and copies into the UDI / Skatteetaten
-- portals. See docs/form-autofill/FINDINGS.md (F1/F2) + Appendix A.
--
-- ONE consolidated public.form_templates row (code RP-NO-DATASHEET). Each field
-- carries a `section`, bilingual labels (label = EN, label_nb = NO) for the
-- EN/NO toggle, and either a `prefill_source` (auto-fillable) OR
-- `consult_professional: true` (a determination that must be made by a regulated
-- advisor and is NEVER pre-populated). Unknown field attributes are ignored by
-- the prefill engine (it only reads id + prefill_source) and consumed by the
-- dossier UI task.
--
-- DEPENDENCY: apply migration 20261011000000_autofill_prefill_provenance_and_
-- source_language.sql FIRST (this seed sets form_templates.source_language via a
-- column-existence-guarded UPDATE, so it is safe to run even if that column is
-- not yet present, but the toggle needs it).
--
-- ACCURACY GATE (do not skip):
--   * verification_status = 'representative' — NOT authoritative. Every legal
--     fact (deadlines, authorities, the D-number<6mo / national-ID>=6mo split,
--     the 50% withholding rule, A1 issued by France) MUST be reconciled against
--     repo ReloPass_FR-NO_Requirements_VERIFICATION.md and signed off by Romain
--     on a golden FR->NO case before flipping to 'verified'.
--   * Norwegian labels (label_nb) are best-effort and need native review.
--   * Portal links use authority ROOT domains only (a wrong deep link is worse
--     than none); exact form paths are left to the verification pass.
--   * Idempotent via ON CONFLICT (code, version) DO NOTHING. No MCP apply.

INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version, fields, trigger_rules)
VALUES (
  'RP-NO-DATASHEET',
  'Personal Relocation Data Sheet (France to Norway)',
  'NO',
  'RELOPASS',
  'ReloPass (aggregates Skatteetaten, politiet, UDI, URSSAF)',
  'data_sheet',
  '1.0.0',
  '[
    {"id":"full_name","section":"d_number","label":"Full legal name","label_nb":"Fullt juridisk navn","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1},
    {"id":"date_of_birth","section":"d_number","label":"Date of birth","label_nb":"Fodselsdato","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nationality","section":"d_number","label":"Nationality","label_nb":"Statsborgerskap","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":3},
    {"id":"id_document_number","section":"d_number","label":"Passport or EEA ID card number","label_nb":"Pass- eller EOS-ID-kortnummer","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":4},
    {"id":"id_document_expiry","section":"d_number","label":"ID document expiry date","label_nb":"Utlopsdato for ID-dokument","type":"date","required":true,"prefill_source":"profile.passport_expiry","requires_original":false,"position":5},
    {"id":"employer_name","section":"eea_registration","label":"Employer in Norway","label_nb":"Arbeidsgiver i Norge","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":6},
    {"id":"employer_org_number","section":"eea_registration","label":"Employer organisation number","label_nb":"Organisasjonsnummer","type":"text","required":true,"prefill_source":"contract.employer_org_number","requires_original":false,"position":7},
    {"id":"job_title","section":"eea_registration","label":"Job title","label_nb":"Stillingstittel","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":8},
    {"id":"employment_start_date","section":"eea_registration","label":"Employment start date","label_nb":"Startdato for arbeidsforhold","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":9},
    {"id":"arrival_date","section":"eea_registration","label":"Date of arrival in Norway","label_nb":"Ankomstdato i Norge","type":"date","required":true,"requires_original":false,"position":10},
    {"id":"salary_amount_nok","section":"skattekort","label":"Gross annual salary (NOK)","label_nb":"Bruttolonn per ar (NOK)","type":"number","required":true,"prefill_source":"contract.salary_amount_nok","requires_original":false,"position":11},
    {"id":"intended_stay_months","section":"folkeregister","label":"Intended length of stay (months)","label_nb":"Planlagt oppholdslengde (maneder)","type":"number","required":true,"requires_original":false,"position":12},
    {"id":"norwegian_address","section":"folkeregister","label":"Address in Norway (once known)","label_nb":"Adresse i Norge (nar kjent)","type":"text","required":false,"requires_original":false,"position":13},
    {"id":"tax_residency_status","section":"consult","label":"Tax-residency status determination","label_nb":"Fastsettelse av skattemessig bosted","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":14},
    {"id":"a1_determination","section":"consult","label":"A1 / social-security coordination determination (A1 issued by France, URSSAF)","label_nb":"A1-/trygdekoordinering (A1 utstedes av Frankrike, URSSAF)","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":15},
    {"id":"contract_classification","section":"consult","label":"Contract classification (posting/secondment vs local hire)","label_nb":"Kontraktsklassifisering (utsending vs lokal ansettelse)","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":16},
    {"id":"shadow_payroll_requirement","section":"consult","label":"Shadow-payroll requirement","label_nb":"Krav om skyggelonn","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":17},
    {"id":"pe_risk","section":"consult","label":"Permanent-establishment (PE) risk","label_nb":"Risiko for fast driftssted","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":18}
  ]'::jsonb,
  '[
    {"event":"roadmap.destination_confirmed","conditions":{"destination_country":"NO","origin_country":"FR","movement_basis":"eea_free_movement"},"for_persons":["employee"],"blocked_by_template_code":null,"priority":100}
  ]'::jsonb
)
ON CONFLICT (code, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Set the template language to Norwegian so the dossier EN/NO toggle appears.
-- Guarded so this seed stays applicable even if the source_language column
-- (migration 20261011000000) has not been applied yet.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'form_templates'
      AND column_name = 'source_language'
  ) THEN
    UPDATE public.form_templates
      SET source_language = 'nb'
      WHERE code = 'RP-NO-DATASHEET' AND version = '1.0.0';
  END IF;
END $$;

-- Provenance/maturity: explicitly NOT verified. Guarded in case the
-- verification_status column (migration 20260612000000) is present.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'form_templates'
      AND column_name = 'verification_status'
  ) THEN
    UPDATE public.form_templates
      SET verification_status = 'representative'
      WHERE code = 'RP-NO-DATASHEET' AND version = '1.0.0';
  END IF;
END $$;
