import { describe, it, expect } from 'vitest';
import {
  mapComparisonRow,
  mapComparisonRows,
  buildKpis,
  outOfPocketRows,
  formatMoney,
} from '../benefitComparisonModel';
import type { EffectiveServiceComparisonRow } from '../../../types';

function row(partial: Partial<EffectiveServiceComparisonRow>): EffectiveServiceComparisonRow {
  return {
    service_key: 'temporary_housing',
    coverage_status: 'included',
    comparison_status: 'within_envelope',
    policy_limit_snapshot: {},
    selected_value_snapshot: {},
    delta: null,
    explanation: '',
    approval_required: false,
    ...partial,
  };
}

describe('mapComparisonRow — coverage badge mapping', () => {
  it('within_envelope → covered (green)', () => {
    const r = mapComparisonRow(row({ comparison_status: 'within_envelope' }));
    expect(r.coverage).toBe('covered');
    expect(r.canRequestException).toBe(false);
  });

  it('exceeds_envelope → partial (amber) with positive delta as out-of-pocket', () => {
    const r = mapComparisonRow(
      row({
        comparison_status: 'exceeds_envelope',
        policy_limit_snapshot: { max_value: 1000, currency: 'EUR' },
        selected_value_snapshot: { estimated_cost: 1500, currency: 'EUR' },
        delta: 500,
      }),
    );
    expect(r.coverage).toBe('partial');
    expect(r.policyCap).toBe(1000);
    expect(r.ask).toBe(1500);
    expect(r.delta).toBe(500);
    expect(r.outOfPocket).toBe(500);
    expect(r.canRequestException).toBe(true);
    expect(r.currency).toBe('EUR');
  });

  it('excluded → uncovered (red); full ask is out of pocket', () => {
    const r = mapComparisonRow(
      row({
        coverage_status: 'excluded',
        comparison_status: 'excluded',
        selected_value_snapshot: { estimated_cost: 800, currency: 'USD' },
        delta: null,
      }),
    );
    expect(r.coverage).toBe('uncovered');
    expect(r.outOfPocket).toBe(800);
    expect(r.canRequestException).toBe(true);
  });

  it('not_enough_policy_data → info; never fabricates a cap or delta', () => {
    const r = mapComparisonRow(
      row({
        coverage_status: 'conditional',
        comparison_status: 'not_enough_policy_data',
        policy_limit_snapshot: {},
        delta: null,
      }),
    );
    expect(r.coverage).toBe('info');
    expect(r.policyCap).toBeNull();
    expect(r.delta).toBeNull();
    expect(r.outOfPocket).toBeNull();
    expect(r.canRequestException).toBe(false);
  });
});

describe('buildKpis — honest aggregation', () => {
  it('sums known caps/asks and per-category out-of-pocket', () => {
    const rows = mapComparisonRows([
      row({
        service_key: 'temporary_housing',
        comparison_status: 'within_envelope',
        policy_limit_snapshot: { max_value: 2000, currency: 'USD' },
        selected_value_snapshot: { estimated_cost: 1800, currency: 'USD' },
        delta: -200,
      }),
      row({
        service_key: 'school_search',
        comparison_status: 'exceeds_envelope',
        policy_limit_snapshot: { max_value: 1000, currency: 'USD' },
        selected_value_snapshot: { estimated_cost: 2500, currency: 'USD' },
        delta: 1500,
      }),
    ]);
    const k = buildKpis(rows);
    expect(k.totalAllocation).toBe(3000);
    expect(k.totalAsk).toBe(4300);
    expect(k.outOfPocket).toBe(1500); // only the over-cap school delta
    expect(k.currency).toBe('USD');
    expect(k.hasUncomparable).toBe(false);
  });

  it('returns null totals when no numeric caps/asks exist, and flags uncomparable', () => {
    const rows = mapComparisonRows([
      row({ comparison_status: 'information_only', policy_limit_snapshot: {}, delta: null }),
    ]);
    const k = buildKpis(rows);
    expect(k.totalAllocation).toBeNull();
    expect(k.totalAsk).toBeNull();
    expect(k.outOfPocket).toBe(0);
    expect(k.hasUncomparable).toBe(true);
  });
});

describe('outOfPocketRows — only Partial/Uncovered', () => {
  it('excludes covered and info rows', () => {
    const rows = mapComparisonRows([
      row({ service_key: 'temporary_housing', comparison_status: 'within_envelope', delta: -1 }),
      row({
        service_key: 'school_search',
        comparison_status: 'exceeds_envelope',
        policy_limit_snapshot: { max_value: 1 },
        selected_value_snapshot: { estimated_cost: 2 },
        delta: 1,
      }),
      row({ service_key: 'home_search', comparison_status: 'information_only', delta: null }),
      row({ service_key: 'visa_support', coverage_status: 'excluded', comparison_status: 'excluded', delta: null }),
    ]);
    const oop = outOfPocketRows(rows);
    expect(oop.map((r) => r.serviceKey).sort()).toEqual(['school_search', 'visa_support']);
  });
});

describe('formatMoney', () => {
  it('formats with currency and renders em dash for non-numbers', () => {
    expect(formatMoney(1500, 'EUR')).toContain('1,500');
    expect(formatMoney(null)).toBe('—');
    expect(formatMoney(undefined)).toBe('—');
  });
});
