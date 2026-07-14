/**
 * AIQ-1526 — the HR payer view must never invent a per-item cost.
 *
 * Before this, a multi-item quote whose line count didn't match the RFQ items had its total
 * DIVIDED EVENLY across the items. That made a reduced-scope quote look identical to a
 * full-scope one — the precise thing HR most needs to see when signing a payment.
 *
 * The contract now: attribute only when we honestly can (single item, or the supplier's own
 * one-line-per-item breakdown), otherwise refuse and say why.
 */
import { describe, expect, it } from 'vitest';
import { buildQuoteCapAttribution, quoteRowsToCompareEstimates } from '../buildQuoteEstimatesForCapCompare';

const EUR = 'EUR';

describe('buildQuoteCapAttribution', () => {
  it('single RFQ item: the whole total belongs to it, unambiguously', () => {
    const res = buildQuoteCapAttribution(
      { total_amount: 4000, currency: EUR },
      [{ service_key: 'moving' }],
    );
    expect(res.comparable).toBe(true);
    if (!res.comparable) throw new Error('expected comparable');
    expect(res.rows).toHaveLength(1);
    expect(res.rows[0]!.amount).toBe(4000);
  });

  it("uses the supplier's OWN breakdown when they sent one line per RFQ item", () => {
    const res = buildQuoteCapAttribution(
      {
        total_amount: 5000,
        currency: EUR,
        quote_lines: [
          { label: 'Packing & transport', amount: 3500 },
          { label: 'Temp housing', amount: 1500 },
        ],
      },
      [{ service_key: 'moving' }, { service_key: 'temporary_housing' }],
    );
    expect(res.comparable).toBe(true);
    if (!res.comparable) throw new Error('expected comparable');
    expect(res.rows.map((r) => r.amount)).toEqual([3500, 1500]);
    // the supplier's line label is surfaced, so HR can see what each figure covers
    expect(res.rows[0]!.label).toContain('Packing & transport');
  });

  it('REFUSES to attribute a lump-sum quote across several services (no even split)', () => {
    const res = buildQuoteCapAttribution(
      { total_amount: 5000, currency: EUR, quote_lines: [] },
      [{ service_key: 'moving' }, { service_key: 'temporary_housing' }],
    );
    expect(res.comparable).toBe(false);
    if (res.comparable) throw new Error('expected NOT comparable');
    expect(res.reason).toMatch(/no breakdown/i);
    // the regression guard: 5000/2 = 2500 must never be produced
    expect(JSON.stringify(res)).not.toContain('2500');
  });

  it('REFUSES when the line count does not match the requested services (scope may differ)', () => {
    const res = buildQuoteCapAttribution(
      {
        total_amount: 3000,
        currency: EUR,
        quote_lines: [{ label: 'Packing only', amount: 3000 }],
      },
      [{ service_key: 'moving' }, { service_key: 'temporary_housing' }, { service_key: 'storage' }],
    );
    expect(res.comparable).toBe(false);
    if (res.comparable) throw new Error('expected NOT comparable');
    expect(res.reason).toMatch(/scope may not match/i);
  });

  it('refuses when there are no RFQ items, or the quote has no total', () => {
    expect(buildQuoteCapAttribution({ total_amount: 100, currency: EUR }, []).comparable).toBe(false);
    expect(
      buildQuoteCapAttribution({ total_amount: NaN, currency: EUR }, [{ service_key: 'moving' }]).comparable,
    ).toBe(false);
  });
});

describe('quoteRowsToCompareEstimates', () => {
  it('only sends rows that map to a policy benefit', () => {
    const res = buildQuoteCapAttribution({ total_amount: 4000, currency: EUR }, [{ service_key: 'moving' }]);
    if (!res.comparable) throw new Error('expected comparable');
    const estimates = quoteRowsToCompareEstimates(res.rows);
    estimates.forEach((e) => expect(e.benefit_key).toBeTruthy());
  });
});
