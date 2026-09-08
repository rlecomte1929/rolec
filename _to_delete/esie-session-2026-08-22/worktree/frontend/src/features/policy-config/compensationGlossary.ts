/**
 * Concise, operational definitions for Compensation & Allowance terms (not legal advice).
 * Used for tooltips and the in-page glossary.
 */
export type CompensationGlossaryId =
  | 'mobility_premium'
  | 'cola'
  | 'location_allowance'
  | 'living_allowance'
  | 'tax_equalisation'
  | 'split_payroll'
  | 'settling_in_services'
  | 'dual_career_support';

export type CompensationGlossaryEntry = {
  id: CompensationGlossaryId;
  term: string;
  definition: string;
};

export const COMPENSATION_GLOSSARY: CompensationGlossaryEntry[] = [
  {
    id: 'mobility_premium',
    term: 'Mobility premium',
    definition:
      'Additional compensation paid for accepting an international assignment. Often a fixed allowance or percentage on top of base pay for the assignment period.',
  },
  {
    id: 'cola',
    term: 'COLA',
    definition:
      'Cost-of-living allowance to offset differences in everyday living costs between home and host location. Usually indexed or reviewed on a schedule your company defines.',
  },
  {
    id: 'location_allowance',
    term: 'Location allowance',
    definition:
      'A recurring allowance tied to working in a particular location or hardship tier. Distinct from COLA: it often reflects location classification rather than a price index.',
  },
  {
    id: 'living_allowance',
    term: 'Living allowance / per diem',
    definition:
      'Day-to-day subsistence support while on assignment (meals, incidental costs). May be paid as a per diem, capped reimbursement, or fixed periodic amount.',
  },
  {
    id: 'tax_equalisation',
    term: 'Tax equalisation',
    definition:
      'A framework where the employee is kept close to a “stay-at-home” tax burden, with the employer settling the difference through payments or settlements. Operational rules vary by programme.',
  },
  {
    id: 'split_payroll',
    term: 'Split payroll',
    definition:
      'Pay delivered through more than one payroll or country (e.g. part in home, part in host). Used for compliance, cash-flow, or benefit delivery—not the same as a single gross-up.',
  },
  {
    id: 'settling_in_services',
    term: 'Settling-in services',
    definition:
      'Practical support on arrival (orientation, local registration help, initial setup). Often a capped benefit or service package rather than ongoing cash.',
  },
  {
    id: 'dual_career_support',
    term: 'Dual-career support',
    definition:
      'Programmes that help a partner or spouse pursue employment or transition (coaching, job-search support, allowances). Scope and caps are company-specific.',
  },
];

const BY_ID: Record<CompensationGlossaryId, CompensationGlossaryEntry> = Object.fromEntries(
  COMPENSATION_GLOSSARY.map((e) => [e.id, e])
) as Record<CompensationGlossaryId, CompensationGlossaryEntry>;

export function getCompensationGlossaryEntry(id: CompensationGlossaryId): CompensationGlossaryEntry {
  return BY_ID[id];
}

/** Map published benefit_key → glossary entry (when the title should carry a tooltip). */
export const BENEFIT_KEY_TO_GLOSSARY_ID: Partial<Record<string, CompensationGlossaryId>> = {
  mobility_premium: 'mobility_premium',
  cola: 'cola',
  location_allowance: 'location_allowance',
  living_allowance: 'living_allowance',
  tax_equalisation: 'tax_equalisation',
  payroll_structure: 'split_payroll',
  settling_in_services: 'settling_in_services',
  dual_career_support: 'dual_career_support',
};

export function glossaryIdForBenefitKey(benefitKey: string | undefined | null): CompensationGlossaryId | null {
  if (!benefitKey) return null;
  return BENEFIT_KEY_TO_GLOSSARY_ID[benefitKey] ?? null;
}
