import { describe, it, expect } from 'vitest';
import {
  canvasPolicyToConfigDraft,
  type MapInCategoryDef,
  type MapInTier,
  type MapInBenefitValue,
} from './canvasPolicyToConfigDraft';

// Minimal catalog fixture (subset of the real CATEGORIES).
const CATEGORIES: MapInCategoryDef[] = [
  {
    key: 'compensation',
    benefits: [
      { k: 'host_housing_cap', lbl: 'Host country housing cap' },
      { k: 'mobility_premium', lbl: 'Mobility premium' },
      { k: 'home_leave_trips', lbl: 'Home leave trips' },
    ],
  },
  {
    key: 'tax',
    benefits: [{ k: 'tax_equalisation', lbl: 'Tax equalisation' }],
  },
];

function bv(partial: Partial<MapInBenefitValue>): MapInBenefitValue {
  return {
    covered: true,
    value_type: 'currency',
    amount: 0,
    freq: 'one_time',
    lump_inc: null,
    cap: false,
    conditions: false,
    ...partial,
  };
}

describe('canvasPolicyToConfigDraft', () => {
  it('maps a caps-mode tier to per-benefit rows with translated targeting + enums', () => {
    const tiers: MapInTier[] = [
      {
        id: 't1',
        name: 'Manager',
        mode: 'caps',
        lump: 0,
        targeting: { level: ['manager'], type: ['long_term', 'permanent'], family: ['married', 'accompanied_family'] },
        benefits: {
          host_housing_cap: bv({ value_type: 'currency', amount: 2500, freq: 'monthly', cap: true }),
          mobility_premium: bv({ value_type: 'percentage', amount: 15 }),
          home_leave_trips: bv({ value_type: 'text', amount: 2, freq: 'yearly' }),
          tax_equalisation: bv({ value_type: 'none' }),
        },
      },
    ];

    const { body, rowCount, warnings } = canvasPolicyToConfigDraft({
      tiers,
      categories: CATEGORIES,
      effectiveDate: '2026-06-07',
      currency: 'EUR',
      policyVersion: 'draft-123',
    });

    expect(body.policy_version).toBe('draft-123');
    expect(body.effective_date).toBe('2026-06-07');
    expect(rowCount).toBe(4);
    expect(warnings).toHaveLength(0);

    const comp = body.categories.find((c) => c.category_key === 'compensation_allowances');
    const tax = body.categories.find((c) => c.category_key === 'tax_payroll');
    expect(comp).toBeDefined();
    expect(tax).toBeDefined();

    const housing = comp!.benefits.find((b) => b.benefit_key === 'host_housing_cap')!;
    // targeting enum translation: married→spouse_partner, accompanied_family→dependents
    expect(housing.assignment_types).toEqual(['long_term', 'permanent']);
    expect(housing.family_statuses).toEqual(['spouse_partner', 'dependents']);
    expect(housing.employee_levels).toEqual(['manager']);
    // currency row carries currency_code (backend requires it)
    expect(housing.value_type).toBe('currency');
    expect(housing.amount_value).toBe(2500);
    expect(housing.currency_code).toBe('EUR');
    expect(housing.unit_frequency).toBe('monthly');
    expect(housing.cap_rule_json).toEqual({ capped: true });

    const premium = comp!.benefits.find((b) => b.benefit_key === 'mobility_premium')!;
    expect(premium.value_type).toBe('percentage');
    expect(premium.percentage_value).toBe(15);
    expect(premium.amount_value).toBeNull();
    expect(premium.currency_code).toBeNull();

    const trips = comp!.benefits.find((b) => b.benefit_key === 'home_leave_trips')!;
    expect(trips.value_type).toBe('text');
    expect(trips.notes).toContain('2');
  });

  it('omits canvas-only assignment types and warns', () => {
    const tiers: MapInTier[] = [
      {
        id: 't1',
        name: 'Commuters',
        mode: 'caps',
        lump: 0,
        targeting: { level: [], type: ['commuter', 'extended_business_trip', 'short_term'], family: [] },
        benefits: { host_housing_cap: bv({ value_type: 'currency', amount: 1000 }) },
      },
    ];
    const { body, warnings } = canvasPolicyToConfigDraft({
      tiers,
      categories: CATEGORIES,
      effectiveDate: '2026-06-07',
      currency: 'EUR',
      policyVersion: 'd',
    });
    const row = body.categories[0].benefits[0];
    expect(row.assignment_types).toEqual(['short_term']); // commuter + EBT dropped
    expect(warnings.join(' ')).toMatch(/commuter/);
  });

  it('handles lump-mode tiers: excluded skipped, optional noted, budget preserved', () => {
    const tiers: MapInTier[] = [
      {
        id: 't1',
        name: 'VP',
        mode: 'lump',
        lump: 68000,
        targeting: { level: ['vp'], type: ['long_term'], family: ['single'] },
        benefits: {
          host_housing_cap: bv({ lump_inc: 'included' }),
          mobility_premium: bv({ lump_inc: 'optional' }),
          home_leave_trips: bv({ lump_inc: 'excluded' }),
        },
      },
    ];
    const { body, rowCount } = canvasPolicyToConfigDraft({
      tiers,
      categories: CATEGORIES,
      effectiveDate: '2026-06-07',
      currency: 'USD',
      policyVersion: 'd',
    });
    expect(rowCount).toBe(2); // excluded one dropped
    const rows = body.categories[0].benefits;
    const housing = rows.find((b) => b.benefit_key === 'host_housing_cap')!;
    expect(housing.value_type).toBe('none');
    expect(housing.conditions_json).toMatchObject({ lump_sum_budget: 68000, lump_currency: 'USD' });
    const premium = rows.find((b) => b.benefit_key === 'mobility_premium')!;
    expect(premium.notes).toMatch(/Optional/);
  });

  it('drops duplicate (benefit, identical-targeting) pairs across tiers', () => {
    const sameTargeting = { level: ['manager'], type: ['long_term'], family: ['single'] };
    const tiers: MapInTier[] = [
      {
        id: 't1', name: 'A', mode: 'caps', lump: 0, targeting: { ...sameTargeting },
        benefits: { host_housing_cap: bv({ value_type: 'currency', amount: 1000 }) },
      },
      {
        id: 't2', name: 'B', mode: 'caps', lump: 0, targeting: { ...sameTargeting },
        benefits: { host_housing_cap: bv({ value_type: 'currency', amount: 2000 }) },
      },
    ];
    const { rowCount, warnings } = canvasPolicyToConfigDraft({
      tiers,
      categories: CATEGORIES,
      effectiveDate: '2026-06-07',
      currency: 'EUR',
      policyVersion: 'd',
    });
    expect(rowCount).toBe(1);
    expect(warnings.join(' ')).toMatch(/Duplicate/);
  });
});
