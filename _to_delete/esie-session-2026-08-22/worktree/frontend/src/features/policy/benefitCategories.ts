/**
 * Maps benefit keys to display categories for the employee policy view.
 * Aligned with backend policy_taxonomy.py groups.
 */
export type DisplayCategory =
  | 'housing'
  | 'movers'
  | 'schooling'
  | 'immigration'
  | 'travel'
  | 'banking'
  | 'medical'
  | 'tax_other';

export const DISPLAY_CATEGORY_ORDER: DisplayCategory[] = [
  'housing',
  'movers',
  'schooling',
  'immigration',
  'travel',
  'banking',
  'medical',
  'tax_other',
];

export const DISPLAY_CATEGORY_LABELS: Record<DisplayCategory, string> = {
  housing: 'Housing',
  movers: 'Movers / Shipment / Storage',
  schooling: 'Schooling',
  immigration: 'Immigration',
  travel: 'Travel / Transport / Home leave',
  banking: 'Banking / Setup',
  medical: 'Medical / Insurance',
  tax_other: 'Tax / Other',
};

/** benefit_key -> backend group -> display category */
const GROUP_TO_CATEGORY: Record<string, DisplayCategory> = {
  housing: 'housing',
  relocation: 'movers',
  education: 'schooling',
  immigration: 'immigration',
  travel: 'travel',
  setup: 'banking',
  health: 'medical',
  tax: 'tax_other',
  compensation: 'tax_other',
  family: 'tax_other',
  integration: 'tax_other',
  other: 'tax_other',
};

/** Direct benefit_key -> group from backend policy_taxonomy */
const BENEFIT_TO_GROUP: Record<string, string> = {
  immigration: 'immigration',
  tax: 'tax',
  housing: 'housing',
  temporary_housing: 'housing',
  movers: 'relocation',
  shipment: 'relocation',
  storage: 'relocation',
  schooling: 'education',
  transport: 'travel',
  home_leave: 'travel',
  spouse_support: 'family',
  language_training: 'integration',
  relocation_services: 'relocation',
  banking_setup: 'setup',
  medical: 'health',
  insurance: 'health',
  pension: 'compensation',
  settling_in_allowance: 'relocation',
  mobility_premium: 'compensation',
  location_allowance: 'compensation',
  cola: 'compensation',
  remote_premium: 'compensation',
  household_goods: 'relocation',
  tuition: 'education',
  scouting_trip: 'travel',
};

export function getBenefitDisplayCategory(benefitKey: string): DisplayCategory {
  const key = benefitKey.toLowerCase().replace(/-/g, '_');
  const group = BENEFIT_TO_GROUP[key] ?? 'other';
  return GROUP_TO_CATEGORY[group] ?? 'tax_other';
}

export function formatBenefitLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
