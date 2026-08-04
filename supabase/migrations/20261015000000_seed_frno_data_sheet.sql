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
-- EXACTLY FIVE SECTIONS, in the order the employee encounters them:
--   d_number         D-number application               [Skatteetaten]
--   eea_registration EEA registration certificate       [UDI apply -> politiet issue]
--   skattekort       Tax deduction card                 [Skatteetaten]
--   folkeregister    National ID number (>= 6 months)   [Skatteetaten / folkeregister]
--   a1               A1 certificate                     [issued by FRANCE - URSSAF/CLEISS]
-- The five CONSULT_PROFESSIONAL determinations are distributed across these five
-- sections rather than living in a sixth "consult" bucket, so the section count
-- matches the spec and each determination sits with the process it governs.
--
-- ACCURACY GATE (do not skip):
--   * verification_status = 'representative' — NOT authoritative. Every legal
--     fact (deadlines, authorities, the D-number<6mo / national-ID>=6mo split,
--     the 50% withholding rule, A1 issued by France) MUST be reconciled against
--     repo ReloPass_FR-NO_Requirements_VERIFICATION.md and signed off by Romain
--     on a golden FR->NO case before flipping to 'verified'.
--   * Norwegian labels (label_nb) are best-effort and need native review.
--   * Portal links use authority ROOT/section domains taken VERBATIM from the
--     Source lines of ReloPass_FR-NO_Requirements_VERIFICATION.md. A wrong deep
--     link is worse than none; no URL here is invented.
--   * NO Article 16 extension ceiling is quoted. The verification report says to
--     confirm the exact FR-NO figure with URSSAF/CLEISS first (a ~5-year number
--     is commonly cited but NOT corridor-confirmed), so only the 24-month
--     standard limit and the existence of an Art. 16 exception are stated.
--   * Idempotent via ON CONFLICT DO NOTHING. No MCP apply.

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
    {"id":"full_name","section":"d_number","label":"Full legal name","label_nb":"Fullt juridisk navn","type":"text","required":true,"prefill_source":"profile.legal_full_name","requires_original":false,"position":1,"portal_url":"https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/","note":"D-number and skattekort are ONE Skatteetaten session: the tax deduction card is not issued until the worker has attended the in-person ID check, and the D-number is assigned within that same tax-card process. Typically requires an in-person appointment (narrow exemptions exist for continental-shelf-only workers and seafarers on NO-registered ships)."},
    {"id":"date_of_birth","section":"d_number","label":"Date of birth","label_nb":"Fodselsdato","type":"date","required":true,"prefill_source":"profile.date_of_birth","requires_original":false,"position":2},
    {"id":"nationality","section":"d_number","label":"Nationality","label_nb":"Statsborgerskap","type":"text","required":true,"prefill_source":"profile.nationality","requires_original":false,"position":3},
    {"id":"id_document_number","section":"d_number","label":"Passport or EEA ID card number","label_nb":"Pass- eller EOS-ID-kortnummer","type":"text","required":true,"prefill_source":"profile.passport_number","requires_original":true,"position":4,"note":"A valid identity/travel document — an EEA national identity card is accepted, not only a passport."},
    {"id":"id_document_expiry","section":"d_number","label":"ID document expiry date","label_nb":"Utlopsdato for ID-dokument","type":"date","required":true,"prefill_source":"profile.passport_expiry","requires_original":false,"position":5},
    {"id":"employer_name","section":"eea_registration","label":"Employer in Norway","label_nb":"Arbeidsgiver i Norge","type":"text","required":true,"prefill_source":"contract.employer_name","requires_original":false,"position":6,"portal_url":"https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/","note":"OUTPUT vs INPUT: the registration certificate itself is issued BY THE POLICE and is an OUTPUT of this step — it cannot be pre-filled. The pre-fillable INPUT is the UDI online registration application, completed before the police appointment. EU/EEA nationals may start work immediately but must register no later than three months after arriving; registration is free. The appointment is an in-person police ID check, and SUA Oslo waiting times are a real practical constraint on that three-month deadline."},
    {"id":"employer_org_number","section":"eea_registration","label":"Employer organisation number","label_nb":"Organisasjonsnummer","type":"text","required":true,"prefill_source":"contract.employer_org_number","requires_original":false,"position":7},
    {"id":"job_title","section":"eea_registration","label":"Job title","label_nb":"Stillingstittel","type":"text","required":true,"prefill_source":"contract.job_title","requires_original":false,"position":8},
    {"id":"employment_start_date","section":"eea_registration","label":"Employment start date","label_nb":"Startdato for arbeidsforhold","type":"date","required":true,"prefill_source":"contract.employment_start_date","requires_original":false,"position":9,"note":"Bring the employment contract or an employment certificate carrying the same information — the police require one of them at registration."},
    {"id":"arrival_date","section":"eea_registration","label":"Date of arrival in Norway","label_nb":"Ankomstdato i Norge","type":"date","required":true,"prefill_source":"case.arrival_date","requires_original":false,"position":10,"note":"Pre-filled from the case move date (actual_move_date once the move has happened, otherwise target_move_date). Starts the three-month registration clock — confirm it against the real arrival before relying on it."},
    {"id":"salary_amount_nok","section":"skattekort","label":"Gross annual salary (NOK)","label_nb":"Bruttolonn per ar (NOK)","type":"number","required":true,"prefill_source":"contract.salary_amount_nok","requires_original":false,"position":11,"portal_url":"https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/","note":"Without a tax deduction card on file the employer must deduct 50 percent tax. It is the employer who retrieves the card and applies the deduction, so the card must exist before the first payroll run."},
    {"id":"tax_residency_status","section":"skattekort","label":"Tax-residency status determination","label_nb":"Fastsettelse av skattemessig bosted","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":12},
    {"id":"shadow_payroll_requirement","section":"skattekort","label":"Shadow-payroll requirement","label_nb":"Krav om skyggelonn","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":13},
    {"id":"pe_risk","section":"skattekort","label":"Permanent-establishment (PE) risk","label_nb":"Risiko for fast driftssted","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":14},
    {"id":"intended_stay_months","section":"folkeregister","label":"Intended length of stay (months)","label_nb":"Planlagt oppholdslengde (maneder)","type":"number","required":true,"requires_original":false,"prefill_source":"case.intended_stay_months","position":15,"portal_url":"https://www.skatteetaten.no/en/person/national-registry/identitetsnummer-og-elektronisk-id/fodselsnummer/","note":"Pre-filled from the case expected_duration_months. The split keys off ACTUAL intended stay, not the assignment label: report a move to Norway and obtain a national identity number if staying at least six months consecutively or more permanently; below that the D-number applies. The fodselsnummer supersedes any D-number."},
    {"id":"norwegian_address","section":"folkeregister","label":"Address in Norway (once known)","label_nb":"Adresse i Norge (nar kjent)","type":"text","required":false,"requires_original":false,"position":16,"note":"Often unknown at intake; not derivable from the profile or contract."},
    {"id":"a1_determination","section":"a1","label":"A1 / social-security coordination determination (A1 issued by France, URSSAF)","label_nb":"A1-/trygdekoordinering (A1 utstedes av Frankrike, URSSAF)","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":17,"portal_url":"https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html","note":"The A1 is issued by FRANCE (URSSAF), not by Norway. EU coordination rules apply to Norway via the EEA Agreement, so a genuinely posted French worker can remain in the French system and be exempt from Norwegian contributions. Standard posting limit is 24 months (Art. 12, Reg. 883/2004); an Art. 16 exception agreement between France and Norway can extend it — confirm the exact ceiling with URSSAF/CLEISS before relying on a figure. Without a posting, an EU/EEA citizen working in Norway joins the Norwegian National Insurance Scheme from the first day of work."},
    {"id":"contract_classification","section":"a1","label":"Contract classification (posting/secondment vs local hire)","label_nb":"Kontraktsklassifisering (utsending vs lokal ansettelse)","type":"text","required":false,"consult_professional":true,"requires_original":false,"position":18,"note":"This determination gates the A1: it covers only a GENUINE posting, where the French employer sends the worker abroad to keep working for them. A French national hired locally in Norway is not posted and pays folketrygden."}
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

-- ---------------------------------------------------------------------------
-- form_field_mappings — the corridor_to='NO' machine mapping.
--
-- IMPORTANT: this table feeds a DIFFERENT engine from the template above.
--   * form_templates.fields[].prefill_source uses DOTTED paths, resolved by
--     prefill_engine._resolve_path against a {profile, contract, banking,
--     person} context.
--   * form_field_mappings.vault_field_path is resolved by form_prefill_service
--     with a FLAT lookup — `profile.get(vault_path)` — where `profile` is
--     `SELECT * FROM public.imm_employee_profiles`. So the value here MUST be a
--     bare COLUMN NAME of that table. A dotted path would silently resolve to
--     None and report every field BLANK.
--
-- Three names therefore differ from the template's dotted paths, deliberately:
--   employer_org_number -> employer_reg_number   (actual vault column name)
--   salary_amount_nok   -> salary_amount         (currency is a separate column)
--   full_name           -> NOT MAPPED            (see below)
--
-- `full_name` has no 1:1 vault column — imm_employee_profiles stores
-- legal_first_name + legal_last_name separately — so it is intentionally absent
-- here rather than mapped to a wrong column. It still pre-fills in the dossier
-- engine via profile.legal_full_name, which that context does provide.
--
-- Deterministic ids (md5 of a stable key, cast to uuid) so a re-run is a no-op.
-- ---------------------------------------------------------------------------
INSERT INTO public.form_field_mappings
  (id, form_id, form_name, corridor_to, visa_type, form_url,
   form_field_id, form_field_label, vault_field_path, exact_match_required, field_instruction)
SELECT
  md5('RP-NO-DATASHEET:' || v.form_field_id)::uuid::text,
  'NO_datasheet_v2026',
  'Personal Relocation Data Sheet (France to Norway)',
  'NO',
  'eea_free_movement',
  v.form_url,
  v.form_field_id,
  v.form_field_label,
  v.vault_field_path,
  v.exact_match_required,
  v.field_instruction
FROM (VALUES
  ('date_of_birth', 'Date of birth', 'date_of_birth', false,
   'https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/',
   'D-number section. Assigned by Skatteetaten inside the tax-card process.'),
  ('nationality', 'Nationality', 'nationality', false,
   'https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/',
   'D-number section.'),
  ('id_document_number', 'Passport or EEA ID card number', 'passport_number', true,
   'https://www.udi.no/en/word-definitions/d-number/',
   'An EEA national identity card is accepted as a valid identity/travel document, not only a passport. Exact match matters — this is copied into an official register.'),
  ('id_document_expiry', 'ID document expiry date', 'passport_expiry', false,
   'https://www.udi.no/en/word-definitions/d-number/',
   'D-number section.'),
  ('employer_name', 'Employer in Norway', 'employer_name', false,
   'https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/',
   'EEA registration. Pre-fills the UDI ONLINE APPLICATION (the input); the police-issued certificate is the output and cannot be pre-filled.'),
  ('employer_org_number', 'Employer organisation number', 'employer_reg_number', true,
   'https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/',
   'Vault column is employer_reg_number. Exact match — an organisation number is validated against the registry.'),
  ('job_title', 'Job title', 'job_title', false,
   'https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/',
   'EEA registration.'),
  ('employment_start_date', 'Employment start date', 'employment_start_date', false,
   'https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/',
   'Bring the employment contract or an employment certificate with the same information to the police appointment.'),
  ('salary_amount_nok', 'Gross annual salary (NOK)', 'salary_amount', false,
   'https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/',
   'Vault column is salary_amount; salary_currency is stored separately — confirm the currency is NOK before relying on this value. With no tax deduction card on file the employer must deduct 50 percent.')
) AS v(form_field_id, form_field_label, vault_field_path, exact_match_required, form_url, field_instruction)
ON CONFLICT (id) DO NOTHING;
