import { describe, expect, it } from 'vitest';
import { formatEstimationFromUsd, formatServicesMoney } from '../servicesCurrency';

describe('servicesCurrency formatting', () => {
  it('shows an ISO currency code for symbol-formatted currencies', () => {
    expect(formatServicesMoney(1200, 'USD')).toMatch(/USD/);
    expect(formatServicesMoney(1200, 'CAD')).toMatch(/CAD/);
  });

  it('carries the currency code through recurring estimates', () => {
    expect(formatEstimationFromUsd(1000, 'monthly', 'EUR')).toMatch(/EUR\/mo$/);
    expect(formatEstimationFromUsd(1000, 'annual', 'GBP')).toMatch(/GBP\/yr$/);
  });
});
