import { describe, it, expect } from 'vitest';
import { countryFlagCode } from './countryFlagCode';

describe('countryFlagCode', () => {
  it('maps country names to ISO alpha-2 (lowercase)', () => {
    expect(countryFlagCode('Germany')).toBe('de');
    expect(countryFlagCode('France')).toBe('fr');
    expect(countryFlagCode('India')).toBe('in');
  });
  it('maps demonyms (nationalities) to ISO alpha-2', () => {
    expect(countryFlagCode('German')).toBe('de');
    expect(countryFlagCode('Indian')).toBe('in');
    expect(countryFlagCode('Polish')).toBe('pl');
  });
  it('accepts an existing ISO alpha-2 code', () => {
    expect(countryFlagCode('DE')).toBe('de');
  });
  it('accepts ISO codes that are not in the corridor name map', () => {
    expect(countryFlagCode('CZ')).toBe('cz');
    expect(countryFlagCode('LB')).toBe('lb');
  });
  it('maps the UK alias to GB for the flag sprite', () => {
    expect(countryFlagCode('UK')).toBe('gb');
  });
  it('is case- and whitespace-insensitive', () => {
    expect(countryFlagCode('  french ')).toBe('fr');
  });
  it('returns null for unknown input', () => {
    expect(countryFlagCode('Atlantis')).toBeNull();
    expect(countryFlagCode('')).toBeNull();
  });

  it('resolves ISO list names that were never in the corridor demonym map', () => {
    expect(countryFlagCode('Argentina')).toBe('ar');
    expect(countryFlagCode('Hong Kong')).toBe('hk');
    expect(countryFlagCode('Bahrain')).toBe('bh');
    expect(countryFlagCode('Czech Republic')).toBe('cz');
  });

  it('resolves admin catalog keys stored as full uppercase names', () => {
    expect(countryFlagCode('AUSTRALIA')).toBe('au');
    expect(countryFlagCode('SAUDI ARABIA')).toBe('sa');
    expect(countryFlagCode('CZECH REPUBLIC')).toBe('cz');
    expect(countryFlagCode('UNITED STATES')).toBe('us');
  });
});
