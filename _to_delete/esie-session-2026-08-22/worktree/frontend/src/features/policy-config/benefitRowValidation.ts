import type { PolicyConfigBenefitRow } from './types';
import type { PolicyConfigWorkingPayload } from './types';
import { readProgramDetails } from './benefitProgramDetails';
import { normalizeCategoryBlocks } from './policyConfigUtils';

export type BenefitValidationIssue = {
  field: string;
  message: string;
};

export type BenefitValidationMode = 'save' | 'publish';

const DEPENDENT_ALLOWANCE_KEYS = new Set(['relocation_allowance_dependent', 'repatriation_allowance_dependent']);

const PERCENT_MIN = 0;
const PERCENT_MAX = 100;

function readCapRuleAmount(row: PolicyConfigBenefitRow): number | null {
  const raw = row.cap_rule_json?.cap_amount;
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string' && raw.trim() !== '') {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * @param mode — `save`: block invalid numbers/negatives/ranges when values are present; allow WIP empty fields.
 *               `publish`: also require amounts/percentages/notes when covered and value_type expects them.
 */
export function validateBenefitRow(row: PolicyConfigBenefitRow, mode: BenefitValidationMode = 'save'): BenefitValidationIssue[] {
  const issues: BenefitValidationIssue[] = [];
  const vt = (row.value_type || 'none').toLowerCase();
  const covered = Boolean(row.covered);
  const enforceValues = mode === 'publish';

  if (!covered) {
    return issues;
  }

  if (vt === 'currency') {
    const amt = row.amount_value;
    if (amt != null && !Number.isFinite(amt)) {
      issues.push({ field: 'amount_value', message: 'Enter a valid number for the amount or cap.' });
    }
    if (amt != null && Number.isFinite(amt) && amt < 0) {
      issues.push({ field: 'amount_value', message: 'Amount cannot be negative.' });
    }
    if (enforceValues && (amt == null || !Number.isFinite(amt))) {
      issues.push({
        field: 'amount_value',
        message: 'Enter an amount or cap when the benefit is covered and expressed as money.',
      });
    }
    if (amt != null && Number.isFinite(amt) && !(row.currency_code || '').trim()) {
      issues.push({ field: 'currency_code', message: 'Select a currency when you enter an amount.' });
    }
    const capAmt = readCapRuleAmount(row);
    if (capAmt != null && capAmt < 0) {
      issues.push({ field: 'cap_amount', message: 'Cap amount cannot be negative.' });
    }
  }

  if (vt === 'percentage') {
    const p = row.percentage_value;
    if (p != null && !Number.isFinite(p)) {
      issues.push({ field: 'percentage_value', message: 'Enter a valid percentage.' });
    }
    if (p != null && Number.isFinite(p) && (p < PERCENT_MIN || p > PERCENT_MAX)) {
      issues.push({
        field: 'percentage_value',
        message: `Percentage should be between ${PERCENT_MIN} and ${PERCENT_MAX} (percent of reference).`,
      });
    }
    if (enforceValues && (p == null || !Number.isFinite(p))) {
      issues.push({
        field: 'percentage_value',
        message: 'Enter a percentage when the benefit is covered and expressed as a percent.',
      });
    }
  }

  if (vt === 'text' && enforceValues) {
    const text = `${row.notes ?? ''}`.trim() || `${row.maximum_budget_explanation ?? ''}`.trim();
    if (!text) {
      issues.push({
        field: 'notes',
        message: 'Add notes (or a short description) when the benefit is covered and expressed in words only.',
      });
    }
  }

  const depKey = String(row.benefit_key || '');
  const dependentCashRow =
    DEPENDENT_ALLOWANCE_KEYS.has(depKey) && vt === 'currency' && (enforceValues || (row.amount_value != null && Number.isFinite(row.amount_value)));
  if (dependentCashRow) {
    const uf = (row.unit_frequency || '').toLowerCase();
    if (uf !== 'per_dependent') {
      issues.push({
        field: 'unit_frequency',
        message: 'For dependent-specific cash allowances, set “How often it applies” to Per dependent.',
      });
    }
  }

  const pd = readProgramDetails(row);
  if (pd.visit_days != null && (!Number.isFinite(pd.visit_days) || pd.visit_days < 0)) {
    issues.push({ field: 'visit_days', message: 'Enter a valid non-negative number of days.' });
  }
  if (pd.training_hours != null && (!Number.isFinite(pd.training_hours) || pd.training_hours < 0)) {
    issues.push({ field: 'training_hours', message: 'Enter a valid non-negative number of hours.' });
  }
  if (
    pd.storage_duration_months != null &&
    (!Number.isFinite(pd.storage_duration_months) || pd.storage_duration_months < 0)
  ) {
    issues.push({ field: 'storage_duration_months', message: 'Duration cannot be negative.' });
  }
  if (
    pd.temporary_living_max_days != null &&
    (!Number.isFinite(pd.temporary_living_max_days) || pd.temporary_living_max_days < 0)
  ) {
    issues.push({ field: 'temporary_living_max_days', message: 'Days cannot be negative.' });
  }
  if (
    pd.home_leave_trips_per_year != null &&
    (!Number.isFinite(pd.home_leave_trips_per_year) || pd.home_leave_trips_per_year < 0)
  ) {
    issues.push({ field: 'home_leave_trips_per_year', message: 'Trips per year cannot be negative.' });
  }
  if (
    pd.extra_holiday_days_count != null &&
    (!Number.isFinite(pd.extra_holiday_days_count) || pd.extra_holiday_days_count < 0)
  ) {
    issues.push({ field: 'extra_holiday_days_count', message: 'Days cannot be negative.' });
  }

  return issues;
}

export function collectBenefitsFromPayload(state: PolicyConfigWorkingPayload): PolicyConfigBenefitRow[] {
  return normalizeCategoryBlocks(state.categories).flatMap((b) => b.benefits ?? []);
}

/** Save draft: invalid / inconsistent numbers only; allows incomplete covered rows. */
export function validatePolicyConfigPayload(state: PolicyConfigWorkingPayload): BenefitValidationIssue[] {
  return validateAllBenefits(collectBenefitsFromPayload(state), 'save');
}

/** Publish: includes required effective date, version id, and full covered-row value rules. */
export function validatePolicyConfigForPublish(state: PolicyConfigWorkingPayload): BenefitValidationIssue[] {
  const issues: BenefitValidationIssue[] = [];
  if (!(state.policy_version || '').trim()) {
    issues.push({ field: 'policy_version', message: 'Policy version is required before publish.' });
  }
  const ed = (state.effective_date || '').trim().slice(0, 10);
  if (!ed) {
    issues.push({ field: 'effective_date', message: 'Effective date is required before publish.' });
  }
  issues.push(...validateAllBenefits(collectBenefitsFromPayload(state), 'publish'));
  return issues;
}

export function validateAllBenefits(rows: PolicyConfigBenefitRow[], mode: BenefitValidationMode): BenefitValidationIssue[] {
  const all: BenefitValidationIssue[] = [];
  rows.forEach((row, i) => {
    const rowIssues = validateBenefitRow(row, mode);
    rowIssues.forEach((iss) =>
      all.push({
        field: `${row.benefit_key || 'row'}_${iss.field}`,
        message: `${row.benefit_label || row.benefit_key || `Row ${i + 1}`}: ${iss.message}`,
      })
    );
  });
  return all;
}
