-- [S1] form_templates.sections — sections become data instead of two hardcoded code maps.
--
-- WHY. A section is currently a bare string on each field, and every heading lives twice:
-- _SECTION_LABELS in backend/app/services/data_sheet_pdf.py and SECTION_LABELS in
-- frontend/src/pages/employee/FormEditorPage.tsx, kept in step by a comment. Everything else a
-- section knows — which authority runs it, its portal, its deadline, its warnings — had nowhere
-- to live, so the FR->NO seed crammed those facts into individual field `note` values. The
-- OUTPUT-vs-INPUT warning about the police certificate sits inside employer_name's note.
--
-- Two things the DE/FR corridors need and the current shape cannot express:
--
--   1. A SECTION WITH NO FIELDS. France's headline fact is the ABSENCE of an arrival
--      registration — there is no titre de séjour obligation and no mairie registration. That is
--      a section that is a statement. Both renderers group BY FIELD, so today it cannot exist,
--      and a silent gap reads to the employee as "ReloPass forgot this".
--   2. SESSION GROUPING. docs/form-autofill/FINDINGS.md Appendix A.3, ratified 2026-07-30:
--      "the production build should present [D-number and skattekort] as one portal visit".
--      Accepted and never built, because there was nowhere to put it. `session_group` is that
--      place; Germany's Anmeldung -> Steuer-IdNr dependency is the next case.
--
-- SHAPE. Ordered array; ARRAY ORDER IS DISPLAY ORDER — do not re-derive it from field position.
--   id             machine key, matches fields[].section so the fallback path stays truthful
--   number         explicit, not baked into the title string
--   title          what the reader sees
--   authority      the body that runs this step, as its own value rather than prose
--   portal_url     a real href
--   deadline_hint  the timing constraint, if there is a real one
--   session_group  sections sharing a key are ONE visit (Appendix A.3)
--   callout_top    rendered ABOVE the fields
--   callout_bottom rendered BELOW them
--   field_ids      ids in fields[]. MAY BE EMPTY. A field may appear in several sections —
--                  each appointment needs its own packet — and must NOT be duplicated in
--                  fields[] to achieve that: n copies would write n case_form_field_values
--                  rows for one datum and let them drift.
--
-- TITLES DELIBERATELY MATCH TODAY'S OUTPUT. The five titles below are byte-identical to what
-- _SECTION_LABELS already prints. This migration changes where the title COMES FROM, not what
-- renders, so the no-regression gate can be a real diff of the rendered PDF text. The richer
-- values (authority, portal_url, deadline_hint, callouts) are STORED here and deliberately NOT
-- yet rendered — surfacing them changes output and belongs in its own change, with its own
-- before/after.
--
-- `sections` is written AFTER `fields` in this file on purpose:
-- backend/tests/test_golden_case_fr_no_datasheet.py:143-146 parses the FIRST '[{…}]'::jsonb
-- literal in the migration it reads. Putting sections first would make that harness parse
-- sections AS fields, and its "0 blank / 0 wrong" assertions would silently stop covering
-- anything. (That harness reads 20261015000000, not this file, so it is unaffected either way —
-- the ordering rule is stated here because it is the convention every later seed must follow.)
--
-- Additive and idempotent. public.form_templates already has RLS enabled with policies, so a
-- new column adds no security surface and needs no new policy.

ALTER TABLE public.form_templates
  ADD COLUMN IF NOT EXISTS sections jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.form_templates.sections IS
  'Ordered array of section objects: {id, number, title, authority, portal_url, deadline_hint, session_group, callout_top, callout_bottom, field_ids}. Array order IS display order. field_ids reference fields[].id and MAY be empty — a section can be a statement with no inputs (France has no arrival registration). One field may be referenced by several sections; never duplicate it in fields[] to achieve that. Empty array means "fall back to grouping by fields[].section", which is what every template except RP-NO-DATASHEET does.';

-- RP-NO-DATASHEET: its five sections, in the order the employee meets them. Facts transcribed
-- from ReloPass_FR-NO_Requirements_VERIFICATION.md; portal URLs are the authority root/section
-- URLs already seeded on the fields, never invented deep links.
UPDATE public.form_templates
SET sections = '[
  {
    "id": "d_number",
    "number": 1,
    "title": "D-number (Skatteetaten)",
    "authority": "Skatteetaten",
    "portal_url": "https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/",
    "deadline_hint": "The card must exist before the first payroll run",
    "session_group": "skatteetaten",
    "callout_top": "The D-number and the tax deduction card are ONE Skatteetaten session. Start the D-number application first; the skattekort request follows in the same session.",
    "callout_bottom": null,
    "field_ids": ["full_name", "date_of_birth", "nationality", "id_document_number", "id_document_expiry"]
  },
  {
    "id": "eea_registration",
    "number": 2,
    "title": "EEA registration (Politiet)",
    "authority": "Politiet / UDI",
    "portal_url": "https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/",
    "deadline_hint": "Register no later than three months after arriving; registration is free",
    "session_group": null,
    "callout_top": null,
    "callout_bottom": "The registration certificate is issued BY the police at your appointment — it is not something you pre-fill. The fields above are what you need for the UDI online application and at the desk. SUA Oslo waiting times are a real constraint on the three-month deadline.",
    "field_ids": ["employer_name", "employer_org_number", "job_title", "employment_start_date", "arrival_date"]
  },
  {
    "id": "skattekort",
    "number": 3,
    "title": "Tax card / skattekort (Skatteetaten)",
    "authority": "Skatteetaten",
    "portal_url": "https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/",
    "deadline_hint": "Must be in place before the first paycheck",
    "session_group": "skatteetaten",
    "callout_top": null,
    "callout_bottom": "Without a tax deduction card on file the employer must deduct 50 percent tax. It is the employer who retrieves the card and applies the deduction.",
    "field_ids": ["salary_amount_nok", "tax_residency_status", "shadow_payroll_requirement", "pe_risk"]
  },
  {
    "id": "folkeregister",
    "number": 4,
    "title": "National registry / folkeregister (Skatteetaten)",
    "authority": "Skatteetaten",
    "portal_url": "https://www.skatteetaten.no/en/person/national-registry/identitetsnummer-og-elektronisk-id/fodselsnummer/",
    "deadline_hint": "Required when staying at least six months consecutively",
    "session_group": null,
    "callout_top": null,
    "callout_bottom": "The split keys off the ACTUAL intended stay, not the assignment label. The fodselsnummer supersedes any D-number.",
    "field_ids": ["intended_stay_months", "norwegian_address"]
  },
  {
    "id": "a1",
    "number": 5,
    "title": "A1 social-security certificate",
    "authority": "CPAM / URSSAF (France)",
    "portal_url": "https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html",
    "deadline_hint": null,
    "session_group": null,
    "callout_top": "The A1 is issued by FRANCE (URSSAF), not by Norway, and is requested by your French employer — not by you. ReloPass shows the information your employer will need but cannot determine whether French or Norwegian social security applies.",
    "callout_bottom": null,
    "field_ids": ["a1_determination", "contract_classification"]
  }
]'::jsonb,
    updated_at = now()
WHERE code = 'RP-NO-DATASHEET';
