/**
 * The two silent defects in the employee -> HR over-budget request, pinned.
 *
 * Both were invisible: nothing threw, no test failed, and the UI looked right. They only
 * showed up as an amount HR could not trust and a button that never appeared.
 */
import { describe, it, expect } from 'vitest';
import {
  canonicalServiceKey,
  backendKeysForCanonical,
} from '../../services/serviceConfig';

describe('service-key vocabulary (one name per benefit)', () => {
  it('maps the estimate page backendKey to the canonical key', () => {
    // The estimate page groups shortlisted vendors by backendKey; the policy engine,
    // /budget-summary and the Benefit-comparison page all speak the canonical key. Filing a
    // request under the backendKey would give HR two rows for one benefit.
    expect(canonicalServiceKey('living_areas')).toBe('housing');
  });

  it('passes canonical and unknown keys through unchanged', () => {
    expect(canonicalServiceKey('housing')).toBe('housing');
    expect(canonicalServiceKey('movers')).toBe('movers');
    expect(canonicalServiceKey('not_a_service')).toBe('not_a_service');
  });

  it('resolves the backendKey a canonical cap must be aliased onto', () => {
    // This is the housing fix: /budget-summary emits a cap named 'housing', the page looks
    // it up as 'living_areas'. Without the alias the lookup is undefined -> 'not_capped'
    // -> the over-cap CTA can never render for housing.
    expect(backendKeysForCanonical('housing')).toContain('living_areas');
  });

  it('returns no alias when the canonical key IS the backend key', () => {
    // movers/schools need no aliasing; emitting one would be noise.
    expect(backendKeysForCanonical('movers')).toEqual([]);
  });

  it('round-trips: every alias maps back to its canonical key', () => {
    // Guards the pair against drifting apart if SERVICE_CONFIG changes.
    for (const canonical of ['housing', 'movers', 'schools']) {
      for (const backendKey of backendKeysForCanonical(canonical)) {
        expect(canonicalServiceKey(backendKey)).toBe(canonical);
      }
    }
  });
});
