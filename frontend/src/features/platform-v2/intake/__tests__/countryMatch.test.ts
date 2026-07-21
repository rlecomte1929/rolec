import { describe, it, expect } from 'vitest';
import { matchCountry, matchCountryName, type CountryOption } from '../countryMatch';

// A trimmed stand-in for the intake COUNTRIES list (no current collisions).
const COUNTRIES: CountryOption[] = [
  { code: 'FR', name: 'France' },
  { code: 'DE', name: 'Germany' },
  { code: 'AU', name: 'Australia' },
  { code: 'US', name: 'United States' },
  { code: 'NO', name: 'Norway' },
];

describe('matchCountryName (mid-keystroke auto-commit)', () => {
  it('commits on a full name match (case-insensitive)', () => {
    expect(matchCountryName('France', COUNTRIES)?.code).toBe('FR');
    expect(matchCountryName('  norway ', COUNTRIES)?.code).toBe('NO');
  });

  it('does not commit on a partial / empty query', () => {
    expect(matchCountryName('fra', COUNTRIES)).toBeUndefined();
    expect(matchCountryName('nor', COUNTRIES)).toBeUndefined();
    expect(matchCountryName('', COUNTRIES)).toBeUndefined();
  });

  it('REGRESSION: never commits a bare CODE match mid-keystroke', () => {
    // Committing "no" (code NO) while typing rewrote the field to "Norway" and the
    // next keystroke appended ("Norwayr" → "No match"). Same for "fr" → "Franceance".
    expect(matchCountryName('no', COUNTRIES)).toBeUndefined();
    expect(matchCountryName('fr', COUNTRIES)).toBeUndefined();
  });
});

describe('matchCountry (blur-time commit)', () => {
  it('commits on a full name match (case-insensitive)', () => {
    expect(matchCountry('France', COUNTRIES)?.code).toBe('FR');
    expect(matchCountry('  germany ', COUNTRIES)?.code).toBe('DE');
  });

  it('commits on an unambiguous code match — incl. a code that prefixes its OWN name', () => {
    // "fr" is the prefix of "France", but France IS the code's country, so it commits.
    expect(matchCountry('fr', COUNTRIES)?.code).toBe('FR');
    expect(matchCountry('FR', COUNTRIES)?.code).toBe('FR');
    expect(matchCountry('no', COUNTRIES)?.code).toBe('NO');
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
