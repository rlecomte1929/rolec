import { describe, it, expect } from 'vitest';
import { matchCountry, type CountryOption } from '../countryMatch';

// A trimmed stand-in for the intake COUNTRIES list (no current collisions).
const COUNTRIES: CountryOption[] = [
  { code: 'FR', name: 'France' },
  { code: 'DE', name: 'Germany' },
  { code: 'AU', name: 'Australia' },
  { code: 'US', name: 'United States' },
];

describe('matchCountry', () => {
  it('commits on a full name match (case-insensitive)', () => {
    expect(matchCountry('France', COUNTRIES)?.code).toBe('FR');
    expect(matchCountry('  germany ', COUNTRIES)?.code).toBe('DE');
  });

  it('commits on an unambiguous code match that starts NO country name', () => {
    // "us" is the United States code and no country name starts with "us", so the
    // user cannot be mid-typing a name → it commits.
    expect(matchCountry('us', COUNTRIES)?.code).toBe('US');
    expect(matchCountry('US', COUNTRIES)?.code).toBe('US');
  });

  it('does NOT commit a code that prefixes a country name — the user may be mid-typing it (AIQ-1643)', () => {
    // "fr" is France's code but also the start of "France": committing here truncated
    // the word and the browser appended the rest → "Franceance". Wait for the full name.
    expect(matchCountry('fr', COUNTRIES)).toBeUndefined();
    expect(matchCountry('FR', COUNTRIES)).toBeUndefined();
    // The canonical field report: "Nor" → "Norwayr" (code NO commits at 2 chars).
    const withNorway: CountryOption[] = [...COUNTRIES, { code: 'NO', name: 'Norway' }];
    expect(matchCountry('no', withNorway)).toBeUndefined();
    expect(matchCountry('nor', withNorway)).toBeUndefined();
    // Once the full name is typed it resolves correctly — no corruption.
    expect(matchCountry('norway', withNorway)?.code).toBe('NO');
  });

  it('does not commit on a partial / empty query', () => {
    expect(matchCountry('fra', COUNTRIES)).toBeUndefined();
    expect(matchCountry('', COUNTRIES)).toBeUndefined();
    expect(matchCountry('   ', COUNTRIES)).toBeUndefined();
  });

  describe('code/name-prefix collision (Austria AT beside Australia AU)', () => {
    const WITH_AUSTRIA: CountryOption[] = [...COUNTRIES, { code: 'AT', name: 'Austria' }];

    it('does NOT prematurely commit Australia when "au" also starts "Austria"', () => {
      // "au" is Australia's code, but also the prefix of a different country's name.
      expect(matchCountry('au', WITH_AUSTRIA)).toBeUndefined();
    });

    it('commits the right country once the full name is typed', () => {
      expect(matchCountry('austria', WITH_AUSTRIA)?.code).toBe('AT');
      expect(matchCountry('australia', WITH_AUSTRIA)?.code).toBe('AU');
    });
  });
});
