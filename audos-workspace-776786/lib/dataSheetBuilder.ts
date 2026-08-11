// Personal Relocation Data Sheet — builder service.
//
// STEP-0 RECONNAISSANCE FINDINGS (what exists in this workspace and what this
// build reuses):
//   · Requirements DB: no requirement_entities / requirement_facts tables
//     existed — they were created as WorkspaceDB tables for this feature and
//     are seeded idempotently by apps/case-command/datasheet-seed.ts (the
//     workspace equivalent of a supabase seed fixture). Corridor steps and
//     fields are read from those tables at runtime — nothing is hardcoded here.
//   · Case data model: real WorkspaceDB tables `cases` (case_reference,
//     person_id, origin/destination_country_id, move_date, employer_name,
//     purpose), `persons` (given_name, family_name, date_of_birth),
//     `person_identities` (document_number, document_expiry_date,
//     nationality_country_id) and `case_facts` — an EAV store with
//     provenance columns (source: user_input | hr_system | document_parse |
//     authority_response | inference, confidence 0-1).
//   · Source mapping: user_input / hr_system / authority_response → intake;
//     document_parse → passport_ocr; facts on an earlier case of the same
//     person → prior_form.
//   · PDF infra: no FormTemplate / PDF-overlay engine exists in this
//     workspace — the Export button in the UI is a print-based placeholder.
//   · UI stack: React + TypeScript, Tailwind utility classes + --space-*
//     design tokens, lucide-react icons; prior validated UX prototypes at
//     apps/FRNODataSheet (hardcoded) and apps/CorridorDataSheetEngine
//     (hardcoded) — this service replaces their mock data with live case data.
//   · Runtime data access: the platform-injected WorkspaceDB SDK
//     (window.__workspaceDb). MCP/agent-seeded rows carry session_id=NULL, so
//     every read here uses { shared: true }.
//
// GUARDRAILS ENFORCED HERE:
//   · CONSULT PROFESSIONAL fields (professional_review_required / category
//     tax|legal|social_security / fallback fact-key list) are classified
//     BEFORE any value lookup — they can never carry a value.
//   · No value is ever invented: a field with no mapped case data is returned
//     blank with source 'needs_input'.

import type {
  DataSheetCaseSummary,
  DataSheetFieldValue,
  DataSheetSection,
  FieldSource,
  PersonalRelocationDataSheet,
  RequirementEntityRow,
  RequirementFactRow,
} from './datasheet-types';

const db = () => {
  const client = (window as any).__workspaceDb;
  if (!client) throw new Error('WorkspaceDB SDK not available');
  return client;
};

// Fallback consult-professional classification for the golden FR→NO case,
// used when a requirements row lacks professional_review_required/category.
const CONSULT_FACT_KEYS = new Set([
  'tax_residency_status',
  'social_security_determination',
  'shadow_payroll',
  'employer_contribution_rate',
]);

const CONSULT_CATEGORIES = new Set(['tax', 'legal', 'social_security']);

const INTAKE_SOURCES = new Set(['user_input', 'hr_system', 'authority_response']);

interface CaseFactRow {
  id: number;
  case_id: number;
  fact_key: string;
  fact_value: string;
  source: string | null;
  confidence: string | number | null;
}

interface ResolvedValue {
  source: FieldSource;
  value: string;
  confidence: number;
}

const isoDate = (v: string | null | undefined): string | null => {
  if (!v) return null;
  const s = String(v);
  return s.length >= 10 ? s.slice(0, 10) : s;
};

const num = (v: string | number | null | undefined, fallback: number): number => {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return typeof n === 'number' && isFinite(n) ? n : fallback;
};

async function getAll(table: string, build?: (q: any) => any): Promise<any[]> {
  let q = db().from(table, { shared: true }).limit(500);
  if (build) q = build(q);
  const res = await q.get();
  return res?.data ?? [];
}

// ── Case picker ─────────────────────────────────────────────────────────────

export async function listDataSheetCases(): Promise<DataSheetCaseSummary[]> {
  const [cases, persons, countries] = await Promise.all([
    getAll('cases'),
    getAll('persons'),
    getAll('countries'),
  ]);
  const personById = new Map(persons.map((p: any) => [p.id, p]));
  const countryById = new Map(countries.map((c: any) => [c.id, c]));

  return cases
    .map((c: any): DataSheetCaseSummary | null => {
      const person = personById.get(c.person_id);
      const origin = countryById.get(c.origin_country_id);
      const dest = countryById.get(c.destination_country_id);
      if (!origin || !dest) return null;
      return {
        case_id: c.id,
        case_ref: c.case_reference,
        employee_name: person ? `${person.given_name} ${person.family_name}` : 'Unknown employee',
        corridor: `${origin.iso_alpha2}-${dest.iso_alpha2}`,
        corridor_label: `${origin.name} → ${dest.name}`,
        status: c.status,
      };
    })
    .filter((c): c is DataSheetCaseSummary => c !== null)
    .sort((a, b) => a.case_ref.localeCompare(b.case_ref));
}

/** Distinct corridors that have steps in the requirements DB. */
export async function listRequirementCorridors(): Promise<string[]> {
  const entities = await getAll('requirement_entities');
  return Array.from(new Set(entities.map((e: any) => e.corridor))).sort();
}

// ── Pre-fill resolution ─────────────────────────────────────────────────────

/**
 * Build the intake value map from structured case columns (case + person +
 * primary identity). These are all values captured at case intake — they are
 * read verbatim from the case data model, never computed or guessed.
 */
function buildStructuredIntakeMap(
  caseRow: any,
  person: any,
  identity: any,
  countryById: Map<number, any>,
): Map<string, string> {
  const m = new Map<string, string>();
  const set = (key: string, v: string | null | undefined) => {
    if (v !== null && v !== undefined && String(v).trim() !== '') m.set(key, String(v));
  };

  if (person) {
    set('given_names', person.given_name);
    set('family_name', person.family_name);
    if (person.given_name && person.family_name) {
      set('employee_full_name', `${person.given_name} ${person.family_name}`);
    }
    set('date_of_birth', isoDate(person.date_of_birth));
    set('email', person.email);
    set('phone', person.phone);
  }
  if (identity) {
    set('passport_number', identity.document_number);
    set('passport_expiry', isoDate(identity.document_expiry_date));
    const nat = countryById.get(identity.nationality_country_id);
    if (nat) set('nationality', nat.name);
  }
  if (caseRow) {
    set('employer_name', caseRow.employer_name);
    set('first_work_day', isoDate(caseRow.move_date));
    if (caseRow.expected_duration_days != null) {
      const days = Number(caseRow.expected_duration_days);
      set('expected_stay_duration', `${days} days (≈ ${Math.round(days / 30.44)} months)`);
    }
    if (caseRow.purpose) {
      set('purpose_of_stay', String(caseRow.purpose).charAt(0).toUpperCase() + String(caseRow.purpose).slice(1));
    }
  }
  return m;
}

/** Latest-wins fact map for one case, split by provenance bucket. */
function bucketCaseFacts(facts: CaseFactRow[]): {
  intake: Map<string, CaseFactRow>;
  ocr: Map<string, CaseFactRow>;
} {
  const intake = new Map<string, CaseFactRow>();
  const ocr = new Map<string, CaseFactRow>();
  const sorted = [...facts].sort((a, b) => a.id - b.id); // later rows overwrite
  for (const f of sorted) {
    const src = f.source ?? 'user_input';
    if (INTAKE_SOURCES.has(src)) intake.set(f.fact_key, f);
    else if (src === 'document_parse') ocr.set(f.fact_key, f);
    // 'inference' and unknown sources are deliberately ignored — the sheet
    // never surfaces computed/inferred values as if they were provided data.
  }
  return { intake, ocr };
}

// ── Main builder ────────────────────────────────────────────────────────────

/**
 * Given a caseId and corridor (e.g. 'FR-NO'), assemble the Personal Relocation
 * Data Sheet: corridor steps + fields from the requirements DB, each field
 * pre-filled from case data and tagged with its provenance.
 */
export async function buildDataSheet(
  caseId: number,
  corridor: string,
): Promise<PersonalRelocationDataSheet> {
  const [entities, reqFacts, caseRows, countries] = await Promise.all([
    getAll('requirement_entities', (q) => q.eq('corridor', corridor)),
    getAll('requirement_facts', (q) => q.eq('corridor', corridor)),
    getAll('cases', (q) => q.eq('id', caseId)),
    getAll('countries'),
  ]);

  const caseRow = caseRows[0];
  if (!caseRow) throw new Error(`Case ${caseId} not found`);

  const countryById = new Map(countries.map((c: any) => [c.id, c]));

  const [personRows, identityRows, caseFacts, allPersonCases] = await Promise.all([
    getAll('persons', (q) => q.eq('id', caseRow.person_id)),
    getAll('person_identities', (q) => q.eq('person_id', caseRow.person_id)),
    getAll('case_facts', (q) => q.eq('case_id', caseId)),
    getAll('cases', (q) => q.eq('person_id', caseRow.person_id)),
  ]);

  const person = personRows[0];
  const identity =
    identityRows.find((i: any) => i.is_primary) ?? identityRows[0] ?? null;

  // Prior cases of the same employee (any case that is not this one), newest
  // move first, for prior_form carry-over.
  const priorCases = allPersonCases
    .filter((c: any) => c.id !== caseId)
    .sort((a: any, b: any) => String(b.move_date ?? '').localeCompare(String(a.move_date ?? '')));

  const priorFactsArrays = await Promise.all(
    priorCases.map((c: any) => getAll('case_facts', (q) => q.eq('case_id', c.id))),
  );
  const priorFacts = new Map<string, CaseFactRow>();
  // Iterate oldest→newest so the most recent prior case wins.
  for (let i = priorFactsArrays.length - 1; i >= 0; i--) {
    for (const f of priorFactsArrays[i].sort((a: any, b: any) => a.id - b.id)) {
      priorFacts.set(f.fact_key, f);
    }
  }

  const structuredIntake = buildStructuredIntakeMap(caseRow, person, identity, countryById);
  const { intake: intakeFacts, ocr: ocrFacts } = bucketCaseFacts(caseFacts as CaseFactRow[]);

  const isConsult = (rf: RequirementFactRow): boolean =>
    rf.professional_review_required === true ||
    (rf.category != null && CONSULT_CATEGORIES.has(rf.category)) ||
    CONSULT_FACT_KEYS.has(rf.fact_key);

  // Pre-fill resolution order (spec): intake → passport OCR → prior form.
  const resolveValue = (factKey: string): ResolvedValue | null => {
    const intakeFact = intakeFacts.get(factKey);
    if (intakeFact) return { source: 'intake', value: intakeFact.fact_value, confidence: num(intakeFact.confidence, 1) };
    const structured = structuredIntake.get(factKey);
    if (structured) return { source: 'intake', value: structured, confidence: 1 };
    const ocrFact = ocrFacts.get(factKey);
    if (ocrFact) return { source: 'passport_ocr', value: ocrFact.fact_value, confidence: num(ocrFact.confidence, 0.9) };
    const priorFact = priorFacts.get(factKey);
    if (priorFact) return { source: 'prior_form', value: priorFact.fact_value, confidence: 0.8 };
    return null;
  };

  const factsByEntity = new Map<string, RequirementFactRow[]>();
  for (const rf of reqFacts as RequirementFactRow[]) {
    const list = factsByEntity.get(rf.entity_id) ?? [];
    list.push(rf);
    factsByEntity.set(rf.entity_id, list);
  }

  const sections: DataSheetSection[] = (entities as RequirementEntityRow[])
    .filter((e) => (e.status ?? 'active') !== 'retired')
    .sort((a, b) => (a.step_order ?? 999) - (b.step_order ?? 999))
    .map((entity) => {
      const rows = (factsByEntity.get(entity.entity_id) ?? []).sort(
        (a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999),
      );

      let fields: DataSheetFieldValue[];
      if (rows.length === 0) {
        // Step exists in the requirements DB but its field list is not authored
        // yet — render a NEEDS INPUT placeholder rather than inventing fields.
        fields = [
          {
            fact_key: `${entity.entity_id}__placeholder`,
            label_en: 'Required fields not yet defined for this step',
            source: 'needs_input',
            value: null,
            confidence: 0,
            hint: 'The requirements database has no field list for this step yet — complete it directly with the authority for now.',
            is_consult_professional: false,
            is_placeholder: true,
          },
        ];
      } else {
        fields = rows.map((rf): DataSheetFieldValue => {
          // CONSULT PROFESSIONAL is classified BEFORE any value lookup — these
          // fields never carry a value, even if case data exists for the key.
          if (isConsult(rf)) {
            return {
              fact_key: rf.fact_key,
              label_en: rf.label_en,
              label_no: rf.label_no ?? undefined,
              source: 'consult_professional',
              value: null,
              confidence: 0,
              guidance:
                rf.guidance ??
                'A regulated professional must determine this — ReloPass cannot make tax, legal, or social security determinations.',
              is_consult_professional: true,
            };
          }
          const resolved = resolveValue(rf.fact_key);
          if (resolved) {
            return {
              fact_key: rf.fact_key,
              label_en: rf.label_en,
              label_no: rf.label_no ?? undefined,
              source: resolved.source,
              value: resolved.value,
              confidence: resolved.confidence,
              is_consult_professional: false,
            };
          }
          return {
            fact_key: rf.fact_key,
            label_en: rf.label_en,
            label_no: rf.label_no ?? undefined,
            source: 'needs_input',
            value: null,
            confidence: 0,
            hint: rf.hint ?? 'Provide this value before your appointment.',
            is_consult_professional: false,
          };
        });
      }

      return {
        step_id: entity.entity_id,
        step_name_en: entity.name_en,
        step_name_no: entity.name_no ?? undefined,
        authority: entity.authority ?? undefined,
        official_source_url: entity.official_source_url ?? '',
        official_process_note: entity.official_process_note ?? '',
        fields,
      };
    });

  const nonConsult = sections.flatMap((s) => s.fields).filter((f) => !f.is_consult_professional);
  const filled = nonConsult.filter((f) => f.value !== null && f.value !== '');
  const completionPct = nonConsult.length === 0 ? 0 : Math.round((filled.length / nonConsult.length) * 100);

  // Label derives from the REQUESTED corridor (which may differ from the
  // case's own corridor, e.g. when rendering the FR-DE fixture for eval).
  const [originIso, destIso] = corridor.split('-');
  const byIso = (iso: string) => countries.find((c: any) => c.iso_alpha2 === iso);
  const origin = byIso(originIso);
  const dest = byIso(destIso);

  return {
    case_ref: caseRow.case_reference,
    case_id: caseRow.id,
    employee_name: person ? `${person.given_name} ${person.family_name}` : 'Unknown employee',
    corridor,
    corridor_label:
      origin && dest ? `${origin.name} → ${dest.name}` : corridor.replace('-', ' → '),
    generated_at: new Date().toISOString(),
    locale: 'en',
    display_mode: 'full',
    sections,
    completion_pct: completionPct,
    needs_input_count: nonConsult.length - filled.length,
  };
}

// ── Inline edit persistence ─────────────────────────────────────────────────

/**
 * Persist a user-provided value for a NEEDS INPUT field as a case fact with
 * source 'user_input' (→ renders as `intake` on the next build). Guarded:
 * consult-professional keys are rejected — the UI never offers editing for
 * them, and this keeps the invariant even if called directly.
 */
export async function saveDataSheetFieldValue(
  caseId: number,
  factKey: string,
  value: string,
): Promise<void> {
  if (CONSULT_FACT_KEYS.has(factKey)) {
    throw new Error('Consult-professional fields cannot be filled in ReloPass — a regulated advisor must determine them.');
  }
  const trimmed = value.trim();
  if (!trimmed) return;
  await db().from('case_facts').insert({
    case_id: caseId,
    fact_key: factKey,
    fact_value: trimmed,
    fact_value_type: 'string',
    source: 'user_input',
    confidence: 1,
    recorded_at: new Date().toISOString(),
  });
}
