import { describe, it, expect } from 'vitest';
import { shouldApplyDestinationCurrency } from '../servicesCurrency';

describe('shouldApplyDestinationCurrency (AIQ-1327 regression)', () => {
  it('applies when there is no real policy currency, no saved choice, and state is the bare USD default', () => {
    expect(
      shouldApplyDestinationCurrency({
        hasRealPolicyCurrency: false,
        savedCurrency: null,
        currentCurrency: 'USD',
      })
    ).toBe(true);
  });

  // The bug: the policy-context endpoint returns currency:"USD" even when
  // has_policy is false. Callers MUST pass the has_policy-gated value, so a
  // non-policy USD must NOT block the destination default.
  it('still applies when a USD value exists but it is NOT from a real policy', () => {
    expect(
      shouldApplyDestinationCurrency({
        hasRealPolicyCurrency: false, // has_policy === false → not authoritative
        savedCurrency: null,
        currentCurrency: 'USD',
      })
    ).toBe(true);
  });

  it('does NOT apply when a real published-policy currency exists', () => {
    expect(
      shouldApplyDestinationCurrency({
        hasRealPolicyCurrency: true,
        savedCurrency: null,
        currentCurrency: 'USD',
      })
    ).toBe(false);
  });

  it('does NOT apply when the user has a saved currency', () => {
    expect(
      shouldApplyDestinationCurrency({
        hasRealPolicyCurrency: false,
        savedCurrency: 'USD',
        currentCurrency: 'USD',
      })
    ).toBe(false);
  });

  it('does NOT apply when state already holds a non-default currency (e.g. server sync)', () => {
    expect(
      shouldApplyDestinationCurrency({
        hasRealPolicyCurrency: false,
        savedCurrency: null,
        currentCurrency: 'EUR',
      })
    ).toBe(false);
  });
});
