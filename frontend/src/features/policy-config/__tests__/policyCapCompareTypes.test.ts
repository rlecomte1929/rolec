import { describe, expect, it } from 'vitest';
import { derivePolicyCapCompareUiStatus, type PolicyCapCompareResultRow } from '../policyCapCompareTypes';

describe('derivePolicyCapCompareUiStatus', () => {
  it('returns no_cap when cap not matched', () => {
    const row: PolicyCapCompareResultRow = {
      benefit_key: 'housing',
      matched_cap: false,
      supported_comparison: false,
    };
    expect(derivePolicyCapCompareUiStatus(row)).toBe('no_cap');
  });

  it('returns within when supported and within_cap', () => {
    const row: PolicyCapCompareResultRow = {
      benefit_key: 'housing',
      matched_cap: true,
      supported_comparison: true,
      within_cap: true,
    };
    expect(derivePolicyCapCompareUiStatus(row)).toBe('within');
  });

  it('returns exceeds when supported and not within_cap', () => {
    const row: PolicyCapCompareResultRow = {
      benefit_key: 'housing',
      matched_cap: true,
      supported_comparison: true,
      within_cap: false,
    };
    expect(derivePolicyCapCompareUiStatus(row)).toBe('exceeds');
  });
});
