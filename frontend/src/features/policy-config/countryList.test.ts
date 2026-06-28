import { describe, it, expect } from 'vitest';
import { COUNTRY_OPTIONS } from './countryList';
import { DESTINATION_COUNTRIES } from '../../utils/countries';

// AIQ-1341: identity fields (nationality, passport, country of incorporation) must
// source the full ISO list, while relocation-destination pickers keep the
// restricted list. These guards lock that contract so the destination allowlist
// can't silently leak back into identity fields (which blocked e.g. Lebanese users).
describe('country list contract (AIQ-1341)', () => {
  it('full COUNTRY_OPTIONS is the whole world and includes Lebanon', () => {
    expect(COUNTRY_OPTIONS.length).toBeGreaterThanOrEqual(170);
    const lebanon = COUNTRY_OPTIONS.find((c) => c.code === 'LB');
    expect(lebanon).toBeDefined();
    expect(lebanon?.name).toBe('Lebanon');
  });

  it('DESTINATION_COUNTRIES is the restricted relocation list without Lebanon', () => {
    expect(DESTINATION_COUNTRIES.length).toBeLessThan(60);
    expect(DESTINATION_COUNTRIES.some((c) => c.code === 'LB')).toBe(false);
  });

  it('the full identity list is strictly larger than the destination list', () => {
    expect(COUNTRY_OPTIONS.length).toBeGreaterThan(DESTINATION_COUNTRIES.length);
  });
});
