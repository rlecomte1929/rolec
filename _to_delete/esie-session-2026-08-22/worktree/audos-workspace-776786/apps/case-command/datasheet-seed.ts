// Personal Relocation Data Sheet — requirements-DB seed + golden-case fixture.
//
// This file is the workspace equivalent of a supabase/seed/*.sql fixture: the
// data sheet engine ONLY reads from the WorkspaceDB tables `requirement_entities`
// and `requirement_facts` at runtime; this module loads those tables (and the
// FR-NO-2026-0081 golden case) idempotently the first time the Data Sheet view
// opens. Unique keys (entity_id, fact_uid, case_reference, external_ref) make
// re-running safe: existing corridors/cases are never re-inserted or mutated.
//
// Corridors seeded:
//   FR-NO — the 5 official steps of the golden corridor (D-number, EEA
//           registration, tax card, Folkeregister, A1 certificate).
//   FR-DE — second-corridor eval fixture (3 steps / 10 fields) proving the
//           engine is data-driven: it renders with NO code changes.
//
// CONSULT PROFESSIONAL fields (professional_review_required = true) are
// regulated tax / legal / social-security determinations. They carry guidance
// text only — the engine NEVER assigns them a value.

interface SeedEntity {
  entity_id: string;
  corridor: string;
  entity_type: string;
  step_order: number;
  name_en: string;
  name_no: string | null;
  authority: string;
  official_source_url: string;
  official_process_note: string;
  status: string;
}

interface SeedFact {
  entity_id: string;
  fact_key: string;
  label_en: string;
  label_no?: string;
  category: string;
  professional_review_required?: boolean;
  hint?: string;
  guidance?: string;
}

// ── FR → NO corridor steps ──────────────────────────────────────────────────

const FRNO_ENTITIES: SeedEntity[] = [
  {
    entity_id: 'frno-d-number',
    corridor: 'FR-NO',
    entity_type: 'process_step',
    step_order: 1,
    name_en: 'D-Number Application',
    name_no: 'Søknad om d-nummer',
    authority: 'Skatteetaten',
    official_source_url: 'skatteetaten.no',
    official_process_note:
      'Submit online at skatteetaten.no — requires passport scan upload. Can be completed in the same Skatteetaten portal session as the tax card (skattekort).',
    status: 'active',
  },
  {
    entity_id: 'frno-eea-registration',
    corridor: 'FR-NO',
    entity_type: 'process_step',
    step_order: 2,
    name_en: 'EEA Registration (Police / UDI)',
    name_no: 'EØS-registrering (politiet / UDI)',
    authority: 'Police / UDI',
    official_source_url: 'udi.no',
    official_process_note:
      'Two stages: complete the UDI online application at udi.no FIRST, then attend the police appointment — within 3 months of arrival. Bring this sheet and original documents.',
    status: 'active',
  },
  {
    entity_id: 'frno-tax-card',
    corridor: 'FR-NO',
    entity_type: 'process_step',
    step_order: 3,
    name_en: 'Tax Card (Skattekort)',
    name_no: 'Skattekort',
    authority: 'Skatteetaten',
    official_source_url: 'skatteetaten.no',
    official_process_note:
      'Requested in the same Skatteetaten portal session as the D-number. Must be active before the first payroll run — otherwise 50% emergency withholding applies.',
    status: 'active',
  },
  {
    entity_id: 'frno-folkeregister',
    corridor: 'FR-NO',
    entity_type: 'process_step',
    step_order: 4,
    name_en: 'National Register (Folkeregister)',
    name_no: 'Folkeregisteret',
    authority: 'Skatteetaten',
    official_source_url: 'skatteetaten.no',
    official_process_note:
      'Register within 6 months of arrival if staying more than 6 months. Requires a confirmed Norwegian residential address.',
    status: 'active',
  },
  {
    entity_id: 'frno-a1-certificate',
    corridor: 'FR-NO',
    entity_type: 'process_step',
    step_order: 5,
    name_en: 'A1 Certificate (French CPAM / URSSAF)',
    name_no: 'A1-attest (fransk CPAM / URSSAF)',
    authority: 'CPAM / URSSAF (France)',
    official_source_url: 'urssaf.fr',
    official_process_note:
      'Initiated by the French employer in France (via CPAM / Net-Entreprises) — NOT a Norwegian process. Should be requested at least 4 weeks before the posting starts.',
    status: 'active',
  },
];

const FRNO_FACTS: SeedFact[] = [
  // 1 · D-Number
  { entity_id: 'frno-d-number', fact_key: 'given_names', label_en: 'Given name(s)', label_no: 'Fornavn', category: 'identity' },
  { entity_id: 'frno-d-number', fact_key: 'family_name', label_en: 'Family name', label_no: 'Etternavn', category: 'identity' },
  { entity_id: 'frno-d-number', fact_key: 'date_of_birth', label_en: 'Date of birth', label_no: 'Fødselsdato', category: 'identity' },
  { entity_id: 'frno-d-number', fact_key: 'nationality', label_en: 'Nationality', label_no: 'Statsborgerskap', category: 'identity' },
  { entity_id: 'frno-d-number', fact_key: 'passport_number', label_en: 'Passport number', label_no: 'Passnummer', category: 'identity' },
  { entity_id: 'frno-d-number', fact_key: 'passport_expiry', label_en: 'Passport expiry', label_no: 'Passutløpsdato', category: 'identity' },
  { entity_id: 'frno-d-number', fact_key: 'employer_name', label_en: 'Norwegian employer', label_no: 'Norsk arbeidsgiver', category: 'employment' },
  { entity_id: 'frno-d-number', fact_key: 'employer_org_number', label_en: 'Norwegian employer org. number', label_no: 'Org.nummer', category: 'employment' },
  { entity_id: 'frno-d-number', fact_key: 'first_work_day', label_en: 'First work day', label_no: 'Første arbeidsdag', category: 'employment' },
  { entity_id: 'frno-d-number', fact_key: 'norwegian_address', label_en: 'Norwegian address', label_no: 'Norsk adresse', category: 'address', hint: 'Street address in Norway once housing is confirmed — a hotel or temporary address is accepted initially.' },
  // 2 · EEA Registration
  { entity_id: 'frno-eea-registration', fact_key: 'given_names', label_en: 'Given name(s)', label_no: 'Fornavn', category: 'identity' },
  { entity_id: 'frno-eea-registration', fact_key: 'family_name', label_en: 'Family name', label_no: 'Etternavn', category: 'identity' },
  { entity_id: 'frno-eea-registration', fact_key: 'nationality', label_en: 'Nationality', label_no: 'Statsborgerskap', category: 'identity' },
  { entity_id: 'frno-eea-registration', fact_key: 'passport_number', label_en: 'Passport number', label_no: 'Passnummer', category: 'identity' },
  { entity_id: 'frno-eea-registration', fact_key: 'home_country_address', label_en: 'Home country address (France)', label_no: 'Hjemstedsadresse (Frankrike)', category: 'address' },
  { entity_id: 'frno-eea-registration', fact_key: 'norwegian_address', label_en: 'Norwegian address', label_no: 'Norsk adresse', category: 'address', hint: 'Street address in Norway once housing is confirmed.' },
  { entity_id: 'frno-eea-registration', fact_key: 'expected_stay_duration', label_en: 'Intended duration of stay', label_no: 'Planlagt varighet', category: 'process' },
  { entity_id: 'frno-eea-registration', fact_key: 'purpose_of_stay', label_en: 'Purpose of stay', label_no: 'Oppholdsformål', category: 'process' },
  { entity_id: 'frno-eea-registration', fact_key: 'employer_confirmation_letter', label_en: 'Employer confirmation letter', label_no: 'Arbeidsgiverbekreftelse', category: 'process', hint: 'Bring a signed letter from the Norwegian employer confirming employment and salary.' },
  // 3 · Tax Card (Skattekort)
  { entity_id: 'frno-tax-card', fact_key: 'given_names', label_en: 'Given name(s)', label_no: 'Fornavn', category: 'identity' },
  { entity_id: 'frno-tax-card', fact_key: 'family_name', label_en: 'Family name', label_no: 'Etternavn', category: 'identity' },
  { entity_id: 'frno-tax-card', fact_key: 'date_of_birth', label_en: 'Date of birth', label_no: 'Fødselsdato', category: 'identity' },
  { entity_id: 'frno-tax-card', fact_key: 'employer_name', label_en: 'Norwegian employer', label_no: 'Norsk arbeidsgiver', category: 'employment' },
  { entity_id: 'frno-tax-card', fact_key: 'employer_org_number', label_en: 'Norwegian employer org. number', label_no: 'Org.nummer', category: 'employment' },
  { entity_id: 'frno-tax-card', fact_key: 'expected_gross_salary', label_en: 'Expected gross salary', label_no: 'Forventet bruttoinntekt', category: 'employment' },
  { entity_id: 'frno-tax-card', fact_key: 'first_work_day', label_en: 'Expected start date', label_no: 'Forventet startdato', category: 'employment' },
  { entity_id: 'frno-tax-card', fact_key: 'norwegian_address', label_en: 'Norwegian address', label_no: 'Norsk adresse', category: 'address', hint: 'Street address in Norway once housing is confirmed.' },
  {
    entity_id: 'frno-tax-card',
    fact_key: 'tax_residency_status',
    label_en: 'Tax residency status',
    label_no: 'Skattemessig bosted',
    category: 'tax',
    professional_review_required: true,
    guidance: 'A tax advisor must determine your Norwegian tax residency under the Norwegian Tax Act §2-1 and the French-Norwegian tax treaty.',
  },
  {
    entity_id: 'frno-tax-card',
    fact_key: 'employer_contribution_rate',
    label_en: 'Employer contribution rate',
    label_no: 'Arbeidsgiveravgiftssats',
    category: 'tax',
    professional_review_required: true,
    guidance: 'Rate depends on the Norwegian zone where the employer is registered — confirm with Skatteetaten or an accountant.',
  },
  // 4 · Folkeregister
  { entity_id: 'frno-folkeregister', fact_key: 'given_names', label_en: 'Given name(s)', label_no: 'Fornavn', category: 'identity' },
  { entity_id: 'frno-folkeregister', fact_key: 'family_name', label_en: 'Family name', label_no: 'Etternavn', category: 'identity' },
  { entity_id: 'frno-folkeregister', fact_key: 'date_of_birth', label_en: 'Date of birth', label_no: 'Fødselsdato', category: 'identity' },
  { entity_id: 'frno-folkeregister', fact_key: 'norwegian_address', label_en: 'Norwegian address', label_no: 'Norsk adresse', category: 'address', hint: 'A confirmed residential address is required for Folkeregister registration.' },
  { entity_id: 'frno-folkeregister', fact_key: 'civil_status', label_en: 'Civil status', label_no: 'Sivilstatus', category: 'identity' },
  { entity_id: 'frno-folkeregister', fact_key: 'expected_stay_duration', label_en: 'Expected length of stay', label_no: 'Forventet oppholdslengde', category: 'process' },
  // 5 · A1 Certificate
  { entity_id: 'frno-a1-certificate', fact_key: 'employee_full_name', label_en: 'Employee name', label_no: 'Ansattnavn', category: 'identity' },
  { entity_id: 'frno-a1-certificate', fact_key: 'french_employer_name', label_en: 'French employer name', label_no: 'Fransk arbeidsgiver', category: 'employment', hint: 'The French employer entity that initiates the A1 request via CPAM / Net-Entreprises.' },
  { entity_id: 'frno-a1-certificate', fact_key: 'employer_name', label_en: 'Norwegian host employer', label_no: 'Norsk vertsarbeidsgiver', category: 'employment' },
  { entity_id: 'frno-a1-certificate', fact_key: 'expected_stay_duration', label_en: 'Expected posting duration', label_no: 'Forventet utstasjoneringsperiode', category: 'process' },
  {
    entity_id: 'frno-a1-certificate',
    fact_key: 'social_security_determination',
    label_en: 'Social security determination',
    label_no: 'Trygdeavklaring',
    category: 'social_security',
    professional_review_required: true,
    guidance: 'Your competent institution under EU Regulation 883/2004 must be determined — typically your French CPAM issues an A1 if you remain under French social security. Confirm with URSSAF.',
  },
  {
    entity_id: 'frno-a1-certificate',
    fact_key: 'shadow_payroll',
    label_en: 'Shadow payroll obligation',
    label_no: 'Skyggelønnsplikt',
    category: 'tax',
    professional_review_required: true,
    guidance: 'Whether the Norwegian employer must run shadow payroll depends on treaty determination — confirm with a Norwegian payroll specialist.',
  },
];

// ── FR → DE second-corridor eval fixture (3 steps / 10 fields) ─────────────────

const FRDE_ENTITIES: SeedEntity[] = [
  {
    entity_id: 'frde-anmeldung',
    corridor: 'FR-DE',
    entity_type: 'process_step',
    step_order: 1,
    name_en: 'Address Registration (Anmeldung)',
    name_no: null,
    authority: 'Bürgeramt',
    official_source_url: 'service.berlin.de',
    official_process_note:
      'In-person appointment at the local Bürgeramt within 14 days of moving in — requires the landlord confirmation (Wohnungsgeberbestätigung).',
    status: 'active',
  },
  {
    entity_id: 'frde-tax-id',
    corridor: 'FR-DE',
    entity_type: 'process_step',
    step_order: 2,
    name_en: 'Tax Identification Number (Steuer-ID)',
    name_no: null,
    authority: 'Bundeszentralamt für Steuern',
    official_source_url: 'bzst.de',
    official_process_note:
      'Issued automatically by post after Anmeldung — usually within 2–3 weeks. The employer needs it before the first payroll run.',
    status: 'active',
  },
  {
    entity_id: 'frde-health-insurance',
    corridor: 'FR-DE',
    entity_type: 'process_step',
    step_order: 3,
    name_en: 'Statutory Health Insurance Enrolment',
    name_no: null,
    authority: 'Krankenkasse (e.g. TK, AOK, Barmer)',
    official_source_url: 'krankenkassen.de',
    official_process_note:
      'Mandatory before the first work day — choose a statutory Krankenkasse and give the membership certificate to the employer.',
    status: 'active',
  },
];

const FRDE_FACTS: SeedFact[] = [
  { entity_id: 'frde-anmeldung', fact_key: 'given_names', label_en: 'Given name(s)', category: 'identity' },
  { entity_id: 'frde-anmeldung', fact_key: 'family_name', label_en: 'Family name', category: 'identity' },
  { entity_id: 'frde-anmeldung', fact_key: 'date_of_birth', label_en: 'Date of birth', category: 'identity' },
  { entity_id: 'frde-anmeldung', fact_key: 'german_address', label_en: 'German residential address', category: 'address', hint: 'Street address in Germany — required with the landlord confirmation (Wohnungsgeberbestätigung).' },
  { entity_id: 'frde-tax-id', fact_key: 'given_names', label_en: 'Given name(s)', category: 'identity' },
  { entity_id: 'frde-tax-id', fact_key: 'german_address', label_en: 'German residential address', category: 'address', hint: 'The Steuer-ID letter is posted to the registered address.' },
  { entity_id: 'frde-tax-id', fact_key: 'civil_status', label_en: 'Marital status', category: 'identity' },
  {
    entity_id: 'frde-tax-id',
    fact_key: 'tax_residency_status',
    label_en: 'Tax residency status',
    category: 'tax',
    professional_review_required: true,
    guidance: 'A tax advisor must determine German tax residency under §8/§9 AO and the French-German tax treaty.',
  },
  { entity_id: 'frde-health-insurance', fact_key: 'employer_name', label_en: 'German employer', category: 'employment' },
  { entity_id: 'frde-health-insurance', fact_key: 'insurance_provider', label_en: 'Chosen Krankenkasse', category: 'process', hint: 'Name of the statutory health insurer you enrol with (e.g. TK, AOK, Barmer).' },
];

// ── Golden case fixture — FR-NO-2026-0081 (Jean Lefebvre) ─────────────────────
// Demonstrates all provenance paths:
//   · intake        — persons row + case row + hr_system/user_input case_facts
//   · passport_ocr  — document_parse case_facts (DOB + passport intentionally
//                     absent from intake so the OCR path is exercised)
//   · prior_form    — facts on the earlier completed case FR-NO-2023-0012
//   · needs_input   — norwegian_address, employer_confirmation_letter,
//                     french_employer_name are deliberately not seeded
// All values are fictional demo fixtures — same footing as the existing
// GIQ-2024-* demo cases in the cases table.

const GOLDEN_CASE_REF = 'FR-NO-2026-0081';
const GOLDEN_PRIOR_CASE_REF = 'FR-NO-2023-0012';
const GOLDEN_PERSON_REF = 'HR-EMP-GOLDEN-0081';

type Db = any;

async function seedRequirements(db: Db): Promise<void> {
  const existing = await db.from('requirement_entities', { shared: true }).limit(1).get();
  if ((existing?.data?.length ?? 0) > 0) return;

  const entityRows = [...FRNO_ENTITIES, ...FRDE_ENTITIES].map((e) => ({
    entity_id: e.entity_id,
    corridor: e.corridor,
    entity_type: e.entity_type,
    step_order: e.step_order,
    name_en: e.name_en,
    name_no: e.name_no,
    authority: e.authority,
    official_source_url: e.official_source_url,
    official_process_note: e.official_process_note,
    status: e.status,
  }));
  await db.from('requirement_entities').bulkInsert(entityRows);

  const corridorOf = (entityId: string) => (entityId.startsWith('frde-') ? 'FR-DE' : 'FR-NO');
  const factRows = [...FRNO_FACTS, ...FRDE_FACTS].map((f, i) => ({
    fact_uid: f.entity_id + ':' + f.fact_key,
    entity_id: f.entity_id,
    corridor: corridorOf(f.entity_id),
    fact_key: f.fact_key,
    label_en: f.label_en,
    label_no: f.label_no ?? null,
    required: true,
    category: f.category,
    professional_review_required: f.professional_review_required === true,
    hint: f.hint ?? null,
    guidance: f.guidance ?? null,
    sort_order: i + 1,
  }));
  await db.from('requirement_facts').bulkInsert(factRows);
}

async function seedGoldenCase(db: Db): Promise<void> {
  const existing = await db.from('cases', { shared: true }).eq('case_reference', GOLDEN_CASE_REF).limit(1).get();
  if ((existing?.data?.length ?? 0) > 0) return;

  // Person — date_of_birth intentionally NOT captured at intake so the
  // passport-OCR provenance path is exercised on the golden case.
  let personId: number;
  const existingPerson = await db.from('persons', { shared: true }).eq('external_ref', GOLDEN_PERSON_REF).limit(1).get();
  if ((existingPerson?.data?.length ?? 0) > 0) {
    personId = existingPerson.data[0].id;
  } else {
    const inserted = await db.from('persons').insert({
      external_ref: GOLDEN_PERSON_REF,
      given_name: 'Jean',
      family_name: 'Lefebvre',
      gender: 'M',
      email: 'jean.lefebvre@example.com',
      phone: '+33611224488',
      preferred_language: 'fr',
      is_active: true,
    });
    personId = inserted?.data?.id ?? inserted?.id;
  }
  if (!personId) {
    const lookup = await db.from('persons', { shared: true }).eq('external_ref', GOLDEN_PERSON_REF).limit(1).get();
    personId = lookup?.data?.[0]?.id;
  }
  if (!personId) throw new Error('Golden case seed: could not resolve person id');

  // Prior completed case — source for prior_form carry-over.
  const priorInserted = await db.from('cases').insert({
    case_reference: GOLDEN_PRIOR_CASE_REF,
    person_id: personId,
    pathway_id: 2, // EEA Free Movement — Employment (Norway)
    origin_country_id: 1, // France
    destination_country_id: 2, // Norway
    move_date: '2023-04-01',
    arrival_date: '2023-04-01',
    expected_duration_days: 365,
    status: 'completed',
    purpose: 'employment',
    employer_name: 'TechnipFMC Norge AS',
    notes: 'Prior completed FR→NO assignment — source of prior_form carry-over for the golden case data sheet.',
  });
  const priorCaseId: number =
    priorInserted?.data?.id ??
    priorInserted?.id ??
    (await db.from('cases', { shared: true }).eq('case_reference', GOLDEN_PRIOR_CASE_REF).limit(1).get())?.data?.[0]?.id;

  if (priorCaseId) {
    await db.from('case_facts').bulkInsert([
      { case_id: priorCaseId, fact_key: 'home_country_address', fact_value: '12 Rue de la République, 69002 Lyon, France', fact_value_type: 'string', source: 'user_input', confidence: 1, recorded_at: '2023-02-10T10:00:00Z' },
      { case_id: priorCaseId, fact_key: 'civil_status', fact_value: 'Married', fact_value_type: 'string', source: 'user_input', confidence: 1, recorded_at: '2023-02-10T10:00:00Z' },
    ]);
  }

  // Golden case itself.
  const goldenInserted = await db.from('cases').insert({
    case_reference: GOLDEN_CASE_REF,
    person_id: personId,
    pathway_id: 2,
    origin_country_id: 1,
    destination_country_id: 2,
    move_date: '2026-10-01',
    expected_duration_days: 730,
    status: 'active',
    purpose: 'employment',
    employer_name: 'Cognite AS',
    notes: 'Golden FR→NO case for the Personal Relocation Data Sheet. Fixture data — all values fictional.',
  });
  const goldenCaseId: number =
    goldenInserted?.data?.id ??
    goldenInserted?.id ??
    (await db.from('cases', { shared: true }).eq('case_reference', GOLDEN_CASE_REF).limit(1).get())?.data?.[0]?.id;
  if (!goldenCaseId) throw new Error('Golden case seed: could not resolve case id');

  await db.from('case_facts').bulkInsert([
    // intake facts (hr_system / user_input)
    { case_id: goldenCaseId, fact_key: 'nationality', fact_value: 'French', fact_value_type: 'string', source: 'hr_system', confidence: 1, recorded_at: '2026-07-01T09:00:00Z' },
    { case_id: goldenCaseId, fact_key: 'employer_org_number', fact_value: '913 704 777', fact_value_type: 'string', source: 'hr_system', confidence: 1, recorded_at: '2026-07-01T09:00:00Z' },
    { case_id: goldenCaseId, fact_key: 'expected_gross_salary', fact_value: 'NOK 920,000 / year', fact_value_type: 'string', source: 'hr_system', confidence: 1, recorded_at: '2026-07-01T09:00:00Z' },
    { case_id: goldenCaseId, fact_key: 'purpose_of_stay', fact_value: 'Employment', fact_value_type: 'string', source: 'user_input', confidence: 1, recorded_at: '2026-07-01T09:05:00Z' },
    // passport OCR facts (document_parse)
    { case_id: goldenCaseId, fact_key: 'date_of_birth', fact_value: '1985-04-12', fact_value_type: 'date', source: 'document_parse', confidence: 0.9, recorded_at: '2026-07-02T14:00:00Z' },
    { case_id: goldenCaseId, fact_key: 'passport_number', fact_value: '17FR34219', fact_value_type: 'string', source: 'document_parse', confidence: 0.9, recorded_at: '2026-07-02T14:00:00Z' },
    { case_id: goldenCaseId, fact_key: 'passport_expiry', fact_value: '2031-06-20', fact_value_type: 'date', source: 'document_parse', confidence: 0.9, recorded_at: '2026-07-02T14:00:00Z' },
  ]);
}

let seedPromise: Promise<void> | null = null;

/**
 * Idempotent one-shot loader. Safe to call on every mount of the Data Sheet
 * view — it no-ops when the requirements tables / golden case already exist,
 * and concurrent calls within one page load share a single promise.
 */
export function ensureDataSheetSeed(): Promise<void> {
  if (!seedPromise) {
    seedPromise = (async () => {
      const db = (window as any).__workspaceDb;
      if (!db) throw new Error('WorkspaceDB SDK not available');
      await seedRequirements(db);
      await seedGoldenCase(db);
    })().catch((err) => {
      seedPromise = null; // allow retry on next mount
      throw err;
    });
  }
  return seedPromise;
}

export { GOLDEN_CASE_REF };
