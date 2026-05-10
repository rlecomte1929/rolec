/**
 * Structured “program details” live under cap_rule_json.program_details for stable API serialization.
 * Other cap_rule keys (e.g. cap_amount) are preserved when updating helpers.
 */
import type { PolicyConfigBenefitRow } from './types';

export const PROGRAM_DETAILS_KEY = 'program_details';

export type ProgramDetails = {
  /** pre_assignment_visit */
  visit_days?: number | null;
  travel_class?: string | null;
  /** cultural_training / language_training */
  training_hours?: number | null;
  /** shipment_of_goods */
  shipment_volume_cap?: string | null;
  /** storage */
  storage_duration_months?: number | null;
  storage_volume_cap?: string | null;
  /** temporary_living */
  temporary_living_max_days?: number | null;
  /** home_leave_trips */
  home_leave_trips_per_year?: number | null;
  /** extra_holiday_days */
  extra_holiday_days_count?: number | null;
  /** payroll_structure */
  payroll_structure_mode?: 'home' | 'split' | 'host' | '' | null;
  /** banking_assistance */
  banking_monthly_transfer_reimbursement?: boolean | null;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

export function readProgramDetails(row: PolicyConfigBenefitRow): ProgramDetails {
  const cap = row.cap_rule_json;
  if (!isRecord(cap)) return {};
  const raw = cap[PROGRAM_DETAILS_KEY];
  if (!isRecord(raw)) return {};
  return { ...raw } as ProgramDetails;
}

export function patchProgramDetails(
  row: PolicyConfigBenefitRow,
  patch: Partial<ProgramDetails>
): PolicyConfigBenefitRow {
  const cap: Record<string, unknown> = isRecord(row.cap_rule_json) ? { ...row.cap_rule_json } : {};
  const prev = readProgramDetails(row);
  const merged: ProgramDetails = { ...prev, ...patch };
  const cleaned = Object.fromEntries(
    Object.entries(merged).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  ) as ProgramDetails;
  if (Object.keys(cleaned).length === 0) {
    delete cap[PROGRAM_DETAILS_KEY];
  } else {
    cap[PROGRAM_DETAILS_KEY] = cleaned;
  }
  return { ...row, cap_rule_json: cap };
}

/** Long-form eligibility / tuition wording — conditions_json.eligibility_notes */
const ELIGIBILITY_NOTES_KEY = 'eligibility_notes';

export function readEligibilityNotes(row: PolicyConfigBenefitRow): string {
  const c = row.conditions_json;
  if (!isRecord(c)) return '';
  const v = c[ELIGIBILITY_NOTES_KEY];
  return typeof v === 'string' ? v : '';
}

export function patchEligibilityNotes(row: PolicyConfigBenefitRow, text: string): PolicyConfigBenefitRow {
  const cond: Record<string, unknown> = isRecord(row.conditions_json) ? { ...row.conditions_json } : {};
  const t = text.trim();
  if (!t) delete cond[ELIGIBILITY_NOTES_KEY];
  else cond[ELIGIBILITY_NOTES_KEY] = t;
  return { ...row, conditions_json: cond };
}

const ADDITIONAL_TERMS_KEY = 'additional_terms';

export function readAdditionalTerms(row: PolicyConfigBenefitRow): string {
  const c = row.conditions_json;
  if (!isRecord(c)) return '';
  const v = c[ADDITIONAL_TERMS_KEY];
  return typeof v === 'string' ? v : '';
}

export function patchAdditionalTerms(row: PolicyConfigBenefitRow, text: string): PolicyConfigBenefitRow {
  const cond: Record<string, unknown> = isRecord(row.conditions_json) ? { ...row.conditions_json } : {};
  const t = text.trim();
  if (!t) delete cond[ADDITIONAL_TERMS_KEY];
  else cond[ADDITIONAL_TERMS_KEY] = t;
  return { ...row, conditions_json: cond };
}
