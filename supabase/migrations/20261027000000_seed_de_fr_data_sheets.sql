-- [S4/S5] The two DE/FR relocation data sheets: FR->DE and DE->FR.
--
-- Modelled on 20261015000000_seed_frno_data_sheet.sql (RP-NO-DATASHEET) and sections-first
-- from the start, now that form_templates.sections exists (20261026000000, applied).
--
-- WHY A DATA SHEET AND NOT A FILLED PDF. Romain ruled on 2026-08-11 that France uses CERFA
-- *06 — the authentic current edition, which has ZERO AcroForm fields (printed to PDF from
-- an ODT, which flattens interactive fields). The only fillable French file,
-- ls_14571-05_fr_09 with 172 fields, is an edition behind, and filling a superseded CERFA
-- is worse than not filling one. Germany publishes no blank PDF at all (Videx is an online
-- wizard). So both corridors take the prefilled-data-sheet shape, which is what
-- docs/form-autofill/FINDINGS.md Appendix A.1 concluded independently. See
-- docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md.
--
-- EVERY FACT BELOW IS TRANSCRIBED FROM ReloPass_DE-FR_Requirements_VERIFICATION.md, which
-- checked 11 items against primary sources in August 2026: 8 CONFIRMED, 2 PARTIAL, 1
-- REFUTED-AS-STATED. What that report forbids is as important as what it authorises, and
-- the omissions below are deliberate, not gaps:
--
--   * NO "four weeks" Steuer-IdNr lead time. It circulates widely and appears on no BZSt
--     page. The only official timing is the THREE-MONTH point at which you may chase it.
--   * NO Article 16 ceiling for an extended posting. The commonly cited ~5 years is not
--     corridor-confirmed for FR<->DE any more than it was for FR->NO.
--   * NO Jahresarbeitsentgeltgrenze figure. The BMG page does not state the threshold, so
--     statutory-vs-private is a determination.
--   * NO Steuerklasse VI claim (report item 10). It would be excellent sheet content — the
--     DE analogue of Norway's 50% withholding — but the BZSt employer FAQ does not say it,
--     and an unsourced withholding-penalty claim is exactly the confident-and-wrong content
--     that destroys trust.
--   * Report item 9 (employer registers the employee for social security) is NOT seeded as
--     a cited fact: make-it-in-germany.com sits behind bot protection and no verbatim
--     official quote could be fetched.
--
-- THE SHAPE THAT ONLY EXISTS BECAUSE OF S1. Both sheets open with a section that has NO
-- FIELDS:
--   * DE->FR: France has no arrival registration at all — no titre de sejour obligation and
--     no mairie duty. The ABSENCE is the headline fact, and the report calls it "the highest
--     content risk in the DE->FR sheet": left as a silent gap, an employee reasonably
--     assumes ReloPass forgot it.
--   * FR->DE: there is no residence title and no certificate for an EU citizen. The old
--     Freizuegigkeitsbescheinigung no longer exists, so any step telling an EU employee to
--     visit the Auslaenderbehoerde instructs them to request something the law does not
--     provide. That defect WAS live in prod (RESID-PERMIT-DE) and was fixed in AIQ-1795.
-- Before S1 a section had to be a set of inputs, so neither could be said at all.
--
-- ORDERING RULE — `fields` IS WRITTEN BEFORE `sections`. The golden harness parses the
-- FIRST '[{...}]'::jsonb literal in the migration it reads
-- (backend/tests/test_golden_case_fr_no_datasheet.py). Writing sections first would make it
-- parse sections AS fields and its "0 blank / 0 wrong" assertions would silently stop
-- covering anything. Every later seed must follow this.
--
-- DIACRITICS. Unlike the FR->NO seed, which stripped Norwegian diacritics ("Fodselsdato"),
-- the German and French labels here are spelled correctly. The column is UTF-8 jsonb and
-- the already-seeded section callouts contain non-ASCII punctuation; a label an employee
-- reads should be spelled the way their authority spells it. ASCII is retained inside SQL
-- COMMENT bodies and identifiers only.
--
-- Additive and idempotent: ON CONFLICT (code, version) DO UPDATE, so re-running refreshes
-- rather than duplicating. RLS is already enabled on public.form_templates with policies.

-- ═══════════════════════════════════════════════════════════════════════════════════════
-- FR -> DE  ·  RP-DE-DATASHEET
-- ═══════════════════════════════════════════════════════════════════════════════════════

INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version,
   source_language, verification_status, fields, trigger_rules)
VALUES (
  'RP-DE-DATASHEET',
  'Personal Relocation Data Sheet (France to Germany)',
  'DE',
  'RELOPASS',
  'ReloPass (aggregates Bürgeramt, BZSt, Krankenkasse, URSSAF)',
  'data_sheet',
  '1.0.0',
  'de',
  'representative',
  '[
    {
      "id": "full_name",
      "label": "Full legal name",
      "label_de": "Vollständiger rechtlicher Name",
      "type": "text",
      "section": "anmeldung",
      "position": 1,
      "required": true,
      "prefill_source": "profile.legal_full_name",
      "requires_original": false,
      "note": "The Anmeldung is the GATE for this corridor, not one step among many. BMG § 17: \"Anyone who moves into a residence is required to register with the registration authority within two weeks of moving in.\" The Steuer-IdNr is triggered only by it, and the Meldebestätigung is the document the bank and the employer ask for. Miss it and the downstream chain does not start.",
      "portal_url": "https://www.gesetze-im-internet.de/englisch_bmg/englisch_bmg.html"
    },
    {
      "id": "date_of_birth",
      "label": "Date of birth",
      "label_de": "Geburtsdatum",
      "type": "date",
      "section": "anmeldung",
      "position": 2,
      "required": true,
      "prefill_source": "profile.date_of_birth",
      "requires_original": false
    },
    {
      "id": "nationality",
      "label": "Nationality",
      "label_de": "Staatsangehörigkeit",
      "type": "text",
      "section": "anmeldung",
      "position": 3,
      "required": true,
      "prefill_source": "profile.nationality",
      "requires_original": false
    },
    {
      "id": "id_document_number",
      "label": "Passport or EU ID card number",
      "label_de": "Pass- oder EU-Personalausweisnummer",
      "type": "text",
      "section": "anmeldung",
      "position": 4,
      "required": true,
      "prefill_source": "profile.passport_number",
      "requires_original": true,
      "note": "A valid identity document is enough — an EU national identity card is accepted, not only a passport."
    },
    {
      "id": "german_address",
      "label": "Address in Germany",
      "label_de": "Anschrift in Deutschland",
      "type": "text",
      "section": "anmeldung",
      "position": 5,
      "required": true,
      "requires_original": false,
      "note": "Often unknown at intake and not derivable from the profile or contract. You will also need a Wohnungsgeberbestätigung — the landlord''s written confirmation that you moved in."
    },
    {
      "id": "move_in_date",
      "label": "Date you moved into the residence",
      "label_de": "Einzugsdatum",
      "type": "date",
      "section": "anmeldung",
      "position": 6,
      "required": true,
      "prefill_source": "case.arrival_date",
      "requires_original": false,
      "note": "This date — not your arrival in the country — starts the two-week clock. Pre-filled from the case move date; confirm it against the actual move-in before relying on it."
    },
    {
      "id": "intended_stay_months",
      "label": "Intended length of stay (months)",
      "label_de": "Geplante Aufenthaltsdauer (Monate)",
      "type": "number",
      "section": "anmeldung",
      "position": 7,
      "required": true,
      "prefill_source": "case.intended_stay_months",
      "requires_original": false,
      "note": "Keys off the ACTUAL intended stay, not the assignment label. BMG: persons who usually live abroad and are not registered in Germany do not have to register if they stay in Germany for less than three months — so a genuinely short assignment may be out of scope for the Anmeldung entirely."
    },
    {
      "id": "employer_name",
      "label": "Employer in Germany",
      "label_de": "Arbeitgeber in Deutschland",
      "type": "text",
      "section": "steuer_id",
      "position": 8,
      "required": true,
      "prefill_source": "contract.employer_name",
      "requires_original": false,
      "note": "Your employer needs the Steuer-IdNr to run wage-tax deduction (ELStAM). BZSt: the individual must supply the IdNr to the bodies obliged to transmit data, on request."
    },
    {
      "id": "employment_start_date",
      "label": "Employment start date",
      "label_de": "Beginn des Arbeitsverhältnisses",
      "type": "date",
      "section": "steuer_id",
      "position": 9,
      "required": true,
      "prefill_source": "contract.employment_start_date",
      "requires_original": false
    },
    {
      "id": "meldebestaetigung_ref",
      "label": "Meldebestätigung reference (once registered)",
      "label_de": "Aktenzeichen der Meldebestätigung (nach Anmeldung)",
      "type": "text",
      "section": "steuer_id",
      "position": 10,
      "required": false,
      "requires_original": false,
      "note": "Keep this. If no IdNr has reached you three months after registering, BZSt lets you send a copy of your identity document and your Meldebestätigung to chase it — that three-month point is the only timing BZSt publishes.",
      "portal_url": "https://www.bzst.de/EN/Private_individuals/Tax_identification_number/tax_identification_number_node.html"
    },
    {
      "id": "health_insurance_choice",
      "label": "Statutory or private health cover (determination)",
      "label_de": "Gesetzliche oder private Krankenversicherung (Feststellung)",
      "type": "text",
      "section": "krankenversicherung",
      "position": 11,
      "required": false,
      "requires_original": false,
      "consult_professional": true,
      "note": "Health insurance is compulsory: \"All citizens who reside in Germany are required to take out health insurance.\" SHI members must also be insured in the social long-term care insurance. Whether you may opt out of the statutory scheme into private cover depends on an income threshold the ministry page does not state, and it interacts with your A1 position — so this is a determination, not a form field.",
      "portal_url": "https://www.bundesgesundheitsministerium.de/en/themen/krankenversicherung/online-ratgeber-krankenversicherung/krankenversicherung/statutory-health-insurance-shi"
    },
    {
      "id": "a1_determination",
      "label": "A1 / social-security coordination determination (A1 issued by France, URSSAF)",
      "label_de": "A1-Bescheinigung / Koordinierung der Sozialversicherung (A1 wird von Frankreich, URSSAF, ausgestellt)",
      "type": "text",
      "section": "a1",
      "position": 12,
      "required": false,
      "requires_original": false,
      "consult_professional": true,
      "note": "The A1 is issued by FRANCE (URSSAF) and requested by your French employer — not by you. Workers must be insured in their home country for at least three months before being posted abroad, and after 24 months of posting there must be a break of at least two months before another posting (Art. 12, Reg. 883/2004). An Article 16 exception agreement can extend beyond 24 months, but confirm the ceiling with URSSAF/CLEISS or DVKA — ReloPass quotes no figure.",
      "portal_url": "https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html"
    },
    {
      "id": "contract_classification",
      "label": "Contract classification (posting/secondment vs local hire)",
      "label_de": "Vertragseinordnung (Entsendung vs lokale Anstellung)",
      "type": "text",
      "section": "a1",
      "position": 13,
      "required": false,
      "requires_original": false,
      "consult_professional": true,
      "note": "This determination gates the A1: it covers only a GENUINE posting, where the French employer sends you abroad and you keep working for them. A French national hired locally in Germany is not posted and joins the German schemes."
    }
  ]'::jsonb,
  '[
    {
      "event": "roadmap.destination_confirmed",
      "priority": 100,
      "conditions": {
        "origin_country": "FR",
        "destination_country": "DE",
        "visa_type": "eea_registration"
      },
      "for_persons": ["employee"],
      "blocked_by_template_code": null
    }
  ]'::jsonb
)
ON CONFLICT (code, version) DO UPDATE
  SET name                = EXCLUDED.name,
      authority_name      = EXCLUDED.authority_name,
      category            = EXCLUDED.category,
      source_language     = EXCLUDED.source_language,
      verification_status = EXCLUDED.verification_status,
      fields              = EXCLUDED.fields,
      trigger_rules       = EXCLUDED.trigger_rules,
      updated_at          = now();

-- ═══════════════════════════════════════════════════════════════════════════════════════
-- DE -> FR  ·  RP-FR-DATASHEET
-- ═══════════════════════════════════════════════════════════════════════════════════════

INSERT INTO public.form_templates
  (code, name, country, authority_code, authority_name, category, version,
   source_language, verification_status, fields, trigger_rules)
VALUES (
  'RP-FR-DATASHEET',
  'Personal Relocation Data Sheet (Germany to France)',
  'FR',
  'RELOPASS',
  'ReloPass (aggregates CPAM, URSSAF, préfecture)',
  'data_sheet',
  '1.0.0',
  'fr',
  'representative',
  '[
    {
      "id": "full_name",
      "label": "Full legal name",
      "label_fr": "Nom et prénoms (état civil)",
      "type": "text",
      "section": "securite_sociale",
      "position": 1,
      "required": true,
      "prefill_source": "profile.legal_full_name",
      "requires_original": false,
      "note": "You first receive a numéro d''identification d''attente (NIA), which already carries interim entitlement. The stated instruction time for the definitive social security number is 9 months — an official published figure, not an estimate. You are not blocked from working or from care in the meantime.",
      "portal_url": "https://www.ameli.fr/assure/droits-demarches/europe-international/protection-sociale-france/ne-etranger-demander-numero-securite-sociale"
    },
    {
      "id": "date_of_birth",
      "label": "Date of birth",
      "label_fr": "Date de naissance",
      "type": "date",
      "section": "securite_sociale",
      "position": 2,
      "required": true,
      "prefill_source": "profile.date_of_birth",
      "requires_original": false
    },
    {
      "id": "birth_certificate_with_filiation",
      "label": "Birth certificate showing parents'' names",
      "label_fr": "Extrait d''acte de naissance avec filiation",
      "type": "text",
      "section": "securite_sociale",
      "position": 3,
      "required": true,
      "requires_original": true,
      "note": "This is the French-specific demand that catches people out. A plain birth certificate is NOT enough: CPAM asks for an \"extrait d''acte de naissance avec filiation (avec le nom de vos parents)\" or a \"copie intégrale d''acte de naissance\". Order it from your German Standesamt early — it is the long-lead item on this corridor."
    },
    {
      "id": "birth_certificate_translation",
      "label": "Sworn translation of the birth certificate (determination)",
      "label_fr": "Traduction assermentée de l''acte de naissance (à déterminer)",
      "type": "text",
      "section": "securite_sociale",
      "position": 4,
      "required": false,
      "requires_original": false,
      "consult_professional": true,
      "note": "Whether a sworn translation of a German birth certificate is required is NOT stated on the ameli.fr page, and ReloPass does not assert it either way. Confirm with the CPAM of your place of residence before paying for one."
    },
    {
      "id": "nationality",
      "label": "Nationality",
      "label_fr": "Nationalité",
      "type": "text",
      "section": "securite_sociale",
      "position": 5,
      "required": true,
      "prefill_source": "profile.nationality",
      "requires_original": false,
      "note": "As an EU national you may instead be asked for a \"formulaire S1 ou un autre formulaire normalisé en matière de sécurité sociale\"."
    },
    {
      "id": "french_address",
      "label": "Address in France (once known)",
      "label_fr": "Adresse en France (dès qu''elle est connue)",
      "type": "text",
      "section": "securite_sociale",
      "position": 6,
      "required": false,
      "requires_original": false,
      "note": "Determines which CPAM handles your file — it is the CPAM of your place of residence that issues the number. Often unknown at intake."
    },
    {
      "id": "employer_name",
      "label": "Employer in France",
      "label_fr": "Employeur en France",
      "type": "text",
      "section": "dpae",
      "position": 7,
      "required": true,
      "prefill_source": "contract.employer_name",
      "requires_original": false,
      "note": "THE DPAE IS YOUR EMPLOYER''S OBLIGATION, NOT YOURS. They file the déclaration préalable à l''embauche with URSSAF in the 8 days before your start date. It is shown here so you can check it has happened, because your own social security application depends on it — not as a task for you.",
      "portal_url": "https://www.ameli.fr/entreprise/vos-salaries/embaucher-salarie/numero-securite-sociale-salarie"
    },
    {
      "id": "employment_start_date",
      "label": "Employment start date",
      "label_fr": "Date de prise de fonction",
      "type": "date",
      "section": "dpae",
      "position": 8,
      "required": true,
      "prefill_source": "contract.employment_start_date",
      "requires_original": false,
      "note": "The 8-day DPAE window is counted back from this date."
    },
    {
      "id": "a1_determination",
      "label": "A1 / social-security coordination determination (A1 issued by Germany)",
      "label_fr": "Formulaire A1 / coordination de sécurité sociale (A1 délivré par l''Allemagne)",
      "type": "text",
      "section": "a1",
      "position": 9,
      "required": false,
      "requires_original": false,
      "consult_professional": true,
      "note": "On this corridor the A1 is issued by GERMANY and requested by your German employer — the mirror of the FR→DE case. Workers must be insured in their home country for at least three months before being posted abroad, and after 24 months of posting there must be a break of at least two months before another posting (Art. 12, Reg. 883/2004). An Article 16 exception agreement can extend beyond 24 months, but confirm the ceiling with DVKA or URSSAF/CLEISS — ReloPass quotes no figure.",
      "portal_url": "https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html"
    },
    {
      "id": "contract_classification",
      "label": "Contract classification (posting/secondment vs local hire)",
      "label_fr": "Qualification du contrat (détachement vs embauche locale)",
      "type": "text",
      "section": "a1",
      "position": 10,
      "required": false,
      "requires_original": false,
      "consult_professional": true,
      "note": "This determination gates the A1: it covers only a GENUINE posting, where the German employer sends you abroad and you keep working for them. A German national hired locally in France is not posted and joins the French scheme."
    }
  ]'::jsonb,
  '[
    {
      "event": "roadmap.destination_confirmed",
      "priority": 100,
      "conditions": {
        "origin_country": "DE",
        "destination_country": "FR",
        "visa_type": "eea_registration"
      },
      "for_persons": ["employee"],
      "blocked_by_template_code": null
    }
  ]'::jsonb
)
ON CONFLICT (code, version) DO UPDATE
  SET name                = EXCLUDED.name,
      authority_name      = EXCLUDED.authority_name,
      category            = EXCLUDED.category,
      source_language     = EXCLUDED.source_language,
      verification_status = EXCLUDED.verification_status,
      fields              = EXCLUDED.fields,
      trigger_rules       = EXCLUDED.trigger_rules,
      updated_at          = now();

-- ═══════════════════════════════════════════════════════════════════════════════════════
-- Sections — written AFTER fields, per the ordering rule at the top of this file.
-- ═══════════════════════════════════════════════════════════════════════════════════════

-- FR -> DE. Ordered as the employee meets them: register, then wait for the tax number,
-- then the thing that does NOT exist, then insurance, then the home-country A1.
UPDATE public.form_templates
SET sections = '[
  {
    "id": "anmeldung",
    "number": 1,
    "title": "Address registration (Bürgeramt)",
    "authority": "Bürgeramt / Meldebehörde",
    "portal_url": "https://www.gesetze-im-internet.de/englisch_bmg/englisch_bmg.html",
    "deadline_hint": "Within two weeks of moving in (BMG § 17)",
    "session_group": null,
    "callout_top": "TWO WEEKS, not three months. If you are reasoning by analogy from a Nordic corridor you will be six weeks late — Norway allows three months to register with the police; Germany allows two weeks from the day you move in.",
    "callout_bottom": "This is the gate for everything else on this sheet. Your Steuer-IdNr is triggered by this registration, and the Meldebestätigung it produces is what your bank and your employer will ask you for.",
    "field_ids": ["full_name", "date_of_birth", "nationality", "id_document_number", "german_address", "move_in_date", "intended_stay_months"]
  },
  {
    "id": "steuer_id",
    "number": 2,
    "title": "Tax identification number (Steuer-IdNr, BZSt)",
    "authority": "Bundeszentralamt für Steuern (BZSt)",
    "portal_url": "https://www.bzst.de/EN/Private_individuals/Tax_identification_number/tax_identification_number_node.html",
    "deadline_hint": "No deadline — you may chase it three months after registering",
    "session_group": null,
    "callout_top": "THERE IS NOTHING TO APPLY FOR. The registration office transmits your data, BZSt assigns the number, and it reaches you BY POST at your registered address — for data protection reasons it cannot be communicated any other way. Expect a letter; do not go looking for a form.",
    "callout_bottom": "ReloPass gives no lead-time figure, because BZSt publishes none. Shorter waiting times are widely quoted elsewhere and none of them appear on an official BZSt page. The one timing BZSt does publish is the chase point: if no number has reached you three months after you registered, you may send them a copy of your identity document and your Meldebestätigung.",
    "field_ids": ["employer_name", "employment_start_date", "meldebestaetigung_ref"]
  },
  {
    "id": "no_residence_document",
    "number": 3,
    "title": "Residence document — none required",
    "authority": null,
    "portal_url": "https://www.gesetze-im-internet.de/englisch_freiz_gg_eu/englisch_freiz_gg_eu.html",
    "deadline_hint": null,
    "session_group": null,
    "callout_top": "As an EU citizen you need no visa and no residence title: \"EU citizens shall not require a visa in order to enter the federal territory or a residence title in order to stay in the federal territory\" (§ 2(4) FreizügG/EU). There is no ordinary certificate either — the old Freizügigkeitsbescheinigung no longer exists.",
    "callout_bottom": "This section is deliberately empty. It is here because the absence is a fact worth stating: if you are ever directed to the Ausländerbehörde to collect a residence document, that instruction is wrong — German law does not issue one to you. (A residence card exists for non-EU family members, and a permanent-residence certificate can be requested after five years of residence; both are different things.)",
    "field_ids": []
  },
  {
    "id": "krankenversicherung",
    "number": 4,
    "title": "Health insurance (Krankenversicherung)",
    "authority": "Krankenkasse",
    "portal_url": "https://www.bundesgesundheitsministerium.de/en/themen/krankenversicherung/online-ratgeber-krankenversicherung/krankenversicherung/statutory-health-insurance-shi",
    "deadline_hint": null,
    "session_group": null,
    "callout_top": "Cover is compulsory: \"All citizens who reside in Germany are required to take out health insurance.\" Members of the statutory scheme must also be insured in the social long-term care insurance.",
    "callout_bottom": "Whether you may opt out of the statutory scheme into private cover turns on an income threshold, and ReloPass does not state a figure — the ministry page does not publish one. It also interacts with your A1 position below, so treat it as a decision to take advice on.",
    "field_ids": ["health_insurance_choice"]
  },
  {
    "id": "a1",
    "number": 5,
    "title": "A1 social-security certificate",
    "authority": "URSSAF / CLEISS (France)",
    "portal_url": "https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html",
    "deadline_hint": null,
    "session_group": null,
    "callout_top": "The A1 is issued by FRANCE (URSSAF), not by Germany, and is requested by your French employer — not by you. ReloPass shows the information your employer will need but cannot determine whether French or German social security applies to you.",
    "callout_bottom": null,
    "field_ids": ["a1_determination", "contract_classification"]
  }
]'::jsonb,
    updated_at = now()
WHERE code = 'RP-DE-DATASHEET';

-- DE -> FR. Opens with the absence, because that is the headline fact of the corridor.
UPDATE public.form_templates
SET sections = '[
  {
    "id": "no_arrival_registration",
    "number": 1,
    "title": "Nothing to register on arrival",
    "authority": null,
    "portal_url": "https://www.service-public.gouv.fr/particuliers/vosdroits/F16003",
    "deadline_hint": null,
    "session_group": null,
    "callout_top": "France has NO arrival registration. There is no Anmeldung, no town-hall registration, and no obligation to hold a residence permit: \"Si vous êtes Européen et venez travailler en France, vous pouvez demander un titre de séjour même si ce n''est pas obligatoire.\" You may request a carte de séjour, but it is optional.",
    "callout_bottom": "This section is deliberately empty — the absence of a step is a fact, not an omission on our part. If you are arriving from Germany, this is the single biggest difference between the two corridors: Germany gives you two weeks to register, France asks nothing of you. Permanent residence accrues after five years of continuous legal residence, and its card is likewise optional.",
    "field_ids": []
  },
  {
    "id": "securite_sociale",
    "number": 2,
    "title": "Social security number (CPAM)",
    "authority": "CPAM (Assurance Maladie)",
    "portal_url": "https://www.ameli.fr/assure/droits-demarches/europe-international/protection-sociale-france/ne-etranger-demander-numero-securite-sociale",
    "deadline_hint": "Stated instruction time for the definitive number: 9 months",
    "session_group": null,
    "callout_top": "This is the long pole on this corridor. You are issued a numéro d''identification d''attente (NIA) first, which carries interim entitlement, and the published \"délai d''instruction\" for the definitive number is 9 MONTHS. That is an official figure, not our estimate. You are not blocked from working or from healthcare while you wait.",
    "callout_bottom": "Order your birth certificate from the German Standesamt before you leave. CPAM requires an extract SHOWING YOUR PARENTS'' NAMES — a plain birth certificate is refused — and that request takes time from abroad.",
    "field_ids": ["full_name", "date_of_birth", "birth_certificate_with_filiation", "birth_certificate_translation", "nationality", "french_address"]
  },
  {
    "id": "dpae",
    "number": 3,
    "title": "Pre-hire declaration (DPAE) — your employer''s duty",
    "authority": "URSSAF (filed by the employer)",
    "portal_url": "https://www.ameli.fr/entreprise/vos-salaries/embaucher-salarie/numero-securite-sociale-salarie",
    "deadline_hint": "Filed by the employer within the 8 days before your start date",
    "session_group": null,
    "callout_top": "NOTHING IN THIS SECTION IS YOURS TO DO. Your employer files the déclaration préalable à l''embauche with URSSAF in the 8 days before you start. It appears on your sheet because your own social security application depends on it having happened — so it is worth checking, not doing.",
    "callout_bottom": "Employers also have a fully digital channel: the Assurance Maladie offers an online service for submitting foreign employees'' registration requests and supporting documents.",
    "field_ids": ["employer_name", "employment_start_date"]
  },
  {
    "id": "a1",
    "number": 4,
    "title": "A1 social-security certificate",
    "authority": "DVKA (Germany)",
    "portal_url": "https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html",
    "deadline_hint": null,
    "session_group": null,
    "callout_top": "On this corridor the A1 is issued by GERMANY and requested by your German employer — the mirror of a France-to-Germany move. ReloPass shows the information your employer will need but cannot determine whether German or French social security applies to you.",
    "callout_bottom": null,
    "field_ids": ["a1_determination", "contract_classification"]
  }
]'::jsonb,
    updated_at = now()
WHERE code = 'RP-FR-DATASHEET';
