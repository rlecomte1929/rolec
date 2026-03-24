import { describe, expect, it } from 'vitest';
import {
  validateBenefitRow,
  validatePolicyConfigForPublish,
  validatePolicyConfigPayload,
} from '../benefitRowValidation';
import type { PolicyConfigBenefitRow, PolicyConfigWorkingPayload } from '../types';

const baseRow = (over: Partial<PolicyConfigBenefitRow> = {}): PolicyConfigBenefitRow => ({
  benefit_key: 'cola',
  benefit_label: 'COLA',
  covered: true,
  value_type: 'currency',
  amount_value: 1000,
  currency_code: 'USD',
  unit_frequency: 'monthly',
  ...over,
});

describe('validateBenefitRow', () => {
  it('save mode allows missing amount on covered currency (WIP)', () => {
    const issues = validateBenefitRow(
      baseRow({ amount_value: null, currency_code: null }),
      'save'
    );
    expect(issues.filter((i) => i.field === 'amount_value')).toHaveLength(0);
  });

  it('publish mode requires amount and currency for covered currency', () => {
    const issues = validateBenefitRow(
      baseRow({ amount_value: null, currency_code: null }),
      'publish'
    );
    expect(issues.some((i) => i.field === 'amount_value')).toBe(true);
  });

  it('rejects negative amounts', () => {
    const issues = validateBenefitRow(baseRow({ amount_value: -1 }), 'save');
    expect(issues.some((i) => i.field === 'amount_value')).toBe(true);
  });

  it('rejects percentage out of range', () => {
    const issues = validateBenefitRow(
      baseRow({ value_type: 'percentage', amount_value: null, currency_code: null, percentage_value: 101 }),
      'save'
    );
    expect(issues.some((i) => i.field === 'percentage_value')).toBe(true);
  });

  it('requires per_dependent for dependent allowance when amount set (save)', () => {
    const issues = validateBenefitRow(
      baseRow({
        benefit_key: 'relocation_allowance_dependent',
        unit_frequency: 'one_time',
      }),
      'save'
    );
    expect(issues.some((i) => i.field === 'unit_frequency')).toBe(true);
  });
});

describe('validatePolicyConfigForPublish', () => {
  it('requires effective_date and policy_version', () => {
    const state: PolicyConfigWorkingPayload = {
      policy_version: '',
      effective_date: '',
      categories: [{ category_key: 'x', benefits: [baseRow()] }],
    };
    const issues = validatePolicyConfigForPublish(state);
    expect(issues.some((i) => i.field === 'effective_date')).toBe(true);
    expect(issues.some((i) => i.field === 'policy_version')).toBe(true);
  });
});

describe('validatePolicyConfigPayload (save)', () => {
  it('does not require global effective date', () => {
    const state: PolicyConfigWorkingPayload = {
      policy_version: 'pv-1',
      effective_date: '',
      categories: [{ category_key: 'x', benefits: [baseRow()] }],
    };
    const issues = validatePolicyConfigPayload(state);
    expect(issues.some((i) => i.field === 'effective_date')).toBe(false);
  });
});
